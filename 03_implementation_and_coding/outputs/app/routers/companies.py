"""公司/財務指標/股價查詢端點（REQ_007）。"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record as record_audit
from app.auth import AuthContext, require_api_key
from app.db_models import Company, FinancialReport, PriceHistory
from app.db_session import get_session
from app.schemas import CompanyOut, FinancialsResponse, PricesResponse


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


def _get_company_or_404(session: Session, ticker: str, market: str) -> Company:
    company = session.execute(
        select(Company).where(Company.market == market, Company.ticker == ticker)
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("", response_model=list[CompanyOut])
def list_companies(
    request: Request,
    market: str | None = Query(default=None, pattern="^(TW|US)$"),
    industry: str | None = Query(default=None),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_api_key),
) -> list[Company]:
    stmt = select(Company)
    if market:
        stmt = stmt.where(Company.market == market)
    if industry:
        stmt = stmt.where(Company.industry == industry)
    companies = session.execute(stmt).scalars().all()
    record_audit(
        session,
        api_key_id=auth.api_key_id,
        action="companies.list",
        result="SUCCESS",
        source_ip=_client_ip(request),
    )
    return list(companies)


@router.get("/{ticker}/financials", response_model=FinancialsResponse)
def get_financials(
    request: Request,
    ticker: str,
    market: str = Query(pattern="^(TW|US)$"),
    quarters: int = Query(default=8, ge=1, le=40),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_api_key),
) -> FinancialsResponse:
    company = _get_company_or_404(session, ticker, market)
    reports = (
        session.execute(
            select(FinancialReport)
            .where(
                FinancialReport.company_id == company.company_id, FinancialReport.is_latest_version.is_(True)
            )
            .order_by(FinancialReport.fiscal_year.desc(), FinancialReport.fiscal_quarter.desc())
            .limit(quarters)
        )
        .scalars()
        .all()
    )

    record_audit(
        session,
        api_key_id=auth.api_key_id,
        action="companies.financials",
        resource=f"{market}:{ticker}",
        result="SUCCESS",
        source_ip=_client_ip(request),
    )
    return FinancialsResponse(ticker=ticker, market=market, reports=list(reports))


@router.get("/{ticker}/prices", response_model=PricesResponse)
def get_prices(
    request: Request,
    ticker: str,
    market: str = Query(pattern="^(TW|US)$"),
    date_from: dt.date | None = Query(default=None, alias="from"),
    date_to: dt.date | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_api_key),
) -> PricesResponse:
    company = _get_company_or_404(session, ticker, market)
    date_to = date_to or dt.date.today()
    date_from = date_from or (date_to - dt.timedelta(days=180))

    prices = (
        session.execute(
            select(PriceHistory)
            .where(
                PriceHistory.company_id == company.company_id,
                PriceHistory.trade_date >= date_from,
                PriceHistory.trade_date <= date_to,
            )
            .order_by(PriceHistory.trade_date.asc())
        )
        .scalars()
        .all()
    )

    record_audit(
        session,
        api_key_id=auth.api_key_id,
        action="companies.prices",
        resource=f"{market}:{ticker}",
        result="SUCCESS",
        source_ip=_client_ip(request),
    )
    return PricesResponse(ticker=ticker, market=market, prices=list(prices))
