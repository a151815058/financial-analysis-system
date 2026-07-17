"""公司/財務指標/股價查詢端點（REQ_007）。"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record as record_audit
from app.auth import AdminAccessContext, OptionalReadAccessContext, optional_read_access, require_admin_access
from app.db_models import Company, FinancialReport, PriceHistory
from app.db_session import get_session
from app.ingestion.mops_client import search_companies as search_tw_companies
from app.ingestion.sec_edgar_client import lookup_cik
from app.ingestion.sec_edgar_client import search_companies as search_us_companies
from app.schemas import (
    CompanyCreateRequest,
    CompanyOut,
    CompanySearchResult,
    FinancialsResponse,
    PricesResponse,
)

CURRENCY_BY_MARKET = {"TW": "TWD", "US": "USD"}


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


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreateRequest,
    request: Request,
    session: Session = Depends(get_session),
    auth: AdminAccessContext = Depends(require_admin_access),
) -> Company:
    """新增追蹤公司（REQ_011）。美股未提供 cik 時自動以 SEC ticker→CIK 對照表查詢。"""
    existing = session.execute(
        select(Company).where(Company.market == payload.market, Company.ticker == payload.ticker)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"{payload.market}:{payload.ticker} 已存在於追蹤清單"
        )

    cik = payload.cik
    if payload.market == "US" and not cik:
        cik = lookup_cik(payload.ticker)
        if cik is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"SEC 查無 {payload.ticker} 對應之 CIK，請於 cik 欄位手動提供",
            )

    company = Company(
        ticker=payload.ticker,
        market=payload.market,
        name=payload.name,
        industry=payload.industry,
        currency=CURRENCY_BY_MARKET[payload.market],
        cik=cik,
    )
    session.add(company)
    session.commit()
    session.refresh(company)

    record_audit(
        session,
        api_key_id=auth.api_key_id,
        action="companies.create",
        resource=f"{payload.market}:{payload.ticker}",
        result="SUCCESS",
        source_ip=_client_ip(request),
        detail={"ticker": payload.ticker, "market": payload.market, "cik": cik, "auth_method": auth.method},
    )
    return company


@router.get("/search", response_model=list[CompanySearchResult])
def search_companies(
    market: str = Query(pattern="^(TW|US)$"),
    q: str = Query(min_length=1, max_length=100),
    auth: OptionalReadAccessContext = Depends(optional_read_access),
) -> list[dict]:
    """REQ_012：依代碼或名稱模糊查詢，供新增公司 UI 之搜尋建議使用（不需 admin scope，僅查詢無副作用）。"""
    if market == "TW":
        return search_tw_companies(q)
    return search_us_companies(q)


@router.get("", response_model=list[CompanyOut])
def list_companies(
    request: Request,
    market: str | None = Query(default=None, pattern="^(TW|US)$"),
    industry: str | None = Query(default=None),
    session: Session = Depends(get_session),
    auth: OptionalReadAccessContext = Depends(optional_read_access),
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
        detail={"auth_method": auth.method},
    )
    return list(companies)


@router.get("/{ticker}/financials", response_model=FinancialsResponse)
def get_financials(
    request: Request,
    ticker: str,
    market: str = Query(pattern="^(TW|US)$"),
    quarters: int = Query(default=8, ge=1, le=40),
    session: Session = Depends(get_session),
    auth: OptionalReadAccessContext = Depends(optional_read_access),
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
        detail={"auth_method": auth.method},
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
    auth: OptionalReadAccessContext = Depends(optional_read_access),
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
        detail={"auth_method": auth.method},
    )
    return PricesResponse(ticker=ticker, market=market, prices=list(prices))
