"""預測結果與回測查詢端點（REQ_007/REQ_009）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record as record_audit
from app.auth import OptionalReadAccessContext, optional_read_access
from app.db_models import Company, Prediction, PredictionBacktest
from app.db_session import get_session
from app.routers.companies import _client_ip
from app.schemas import BacktestResponse, PredictionOut, SubModelResult

router = APIRouter(prefix="/api/v1/companies", tags=["predictions"])


def _get_company_or_404(session: Session, ticker: str, market: str) -> Company:
    company = session.execute(
        select(Company).where(Company.market == market, Company.ticker == ticker)
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


def _to_prediction_out(ticker: str, market: str, p: Prediction) -> PredictionOut:
    return PredictionOut(
        ticker=ticker,
        market=market,
        base_week_start_date=p.base_week_start_date,
        direction=p.direction,
        range_lower_pct=float(p.range_lower_pct),
        range_upper_pct=float(p.range_upper_pct),
        confidence_score=float(p.confidence_score),
        sub_models={
            "factor_model": SubModelResult(
                direction=p.factor_model_direction,
                range_pct=(
                    (float(p.factor_model_range_lower_pct), float(p.factor_model_range_upper_pct))
                    if p.factor_model_range_lower_pct is not None
                    else None
                ),
            ),
            "timeseries_model": SubModelResult(
                direction=p.timeseries_model_direction,
                range_pct=(
                    (float(p.timeseries_model_range_lower_pct), float(p.timeseries_model_range_upper_pct))
                    if p.timeseries_model_range_lower_pct is not None
                    else None
                ),
            ),
        },
        model_version=p.model_version,
    )


@router.get("/{ticker}/predictions/latest", response_model=PredictionOut)
def get_latest_prediction(
    request: Request,
    ticker: str,
    market: str = Query(pattern="^(TW|US)$"),
    session: Session = Depends(get_session),
    auth: OptionalReadAccessContext = Depends(optional_read_access),
) -> PredictionOut:
    company = _get_company_or_404(session, ticker, market)
    prediction = session.execute(
        select(Prediction)
        .where(Prediction.company_id == company.company_id)
        .order_by(Prediction.base_week_start_date.desc())
        .limit(1)
    ).scalar_one_or_none()

    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No prediction available yet")

    record_audit(
        session,
        api_key_id=auth.api_key_id,
        action="predictions.latest",
        resource=f"{market}:{ticker}",
        result="SUCCESS",
        source_ip=_client_ip(request),
        detail={"auth_method": auth.method},
    )
    return _to_prediction_out(ticker, market, prediction)


@router.get("/{ticker}/predictions/history", response_model=list[PredictionOut])
def get_prediction_history(
    request: Request,
    ticker: str,
    market: str = Query(pattern="^(TW|US)$"),
    weeks: int = Query(default=12, ge=1, le=104),
    session: Session = Depends(get_session),
    auth: OptionalReadAccessContext = Depends(optional_read_access),
) -> list[PredictionOut]:
    company = _get_company_or_404(session, ticker, market)
    predictions = (
        session.execute(
            select(Prediction)
            .where(Prediction.company_id == company.company_id)
            .order_by(Prediction.base_week_start_date.desc())
            .limit(weeks)
        )
        .scalars()
        .all()
    )

    record_audit(
        session,
        api_key_id=auth.api_key_id,
        action="predictions.history",
        resource=f"{market}:{ticker}",
        result="SUCCESS",
        source_ip=_client_ip(request),
        detail={"auth_method": auth.method},
    )
    return [_to_prediction_out(ticker, market, p) for p in predictions]


@router.get("/{ticker}/backtest", response_model=BacktestResponse)
def get_backtest(
    request: Request,
    ticker: str,
    market: str = Query(pattern="^(TW|US)$"),
    weeks: int = Query(default=12, ge=1, le=104),
    session: Session = Depends(get_session),
    auth: OptionalReadAccessContext = Depends(optional_read_access),
) -> BacktestResponse:
    company = _get_company_or_404(session, ticker, market)
    records = (
        session.execute(
            select(PredictionBacktest)
            .join(Prediction, Prediction.prediction_id == PredictionBacktest.prediction_id)
            .where(Prediction.company_id == company.company_id, PredictionBacktest.direction_hit.is_not(None))
            .order_by(Prediction.base_week_start_date.desc())
            .limit(weeks)
        )
        .scalars()
        .all()
    )

    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No backtest data available yet")

    n = len(records)
    directional_accuracy = round(sum(1 for r in records if r.direction_hit) / n, 3)
    range_hit_rate = round(sum(1 for r in records if r.range_hit) / n, 3)

    record_audit(
        session,
        api_key_id=auth.api_key_id,
        action="predictions.backtest",
        resource=f"{market}:{ticker}",
        result="SUCCESS",
        source_ip=_client_ip(request),
        detail={"auth_method": auth.method},
    )
    return BacktestResponse(
        ticker=ticker,
        market=market,
        window_weeks=n,
        directional_accuracy=directional_accuracy,
        range_hit_rate=range_hit_rate,
    )
