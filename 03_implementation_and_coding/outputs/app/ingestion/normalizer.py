"""跨市場財務指標正規化與版本化（REQ_003）。

設計重點：
- 7 項核心指標缺漏時明確標記為 None，不以 0 填補（避免模型誤讀為真實數值）。
- 同一 (company, fiscal_year, fiscal_quarter) 若財報更正重新公布，保留歷史版本，
  新版 data_version = 舊版最大值 + 1，並將舊版 is_latest_version 改為 False。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db_models import Company, FinancialReport, PriceHistory

CORE_METRIC_FIELDS = (
    "revenue",
    "eps",
    "gross_margin",
    "net_margin",
    "debt_ratio",
    "operating_cash_flow",
    "pe_ratio",
)


@dataclass(frozen=True)
class NormalizedFinancials:
    revenue: float | None = None
    eps: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None
    debt_ratio: float | None = None
    operating_cash_flow: float | None = None
    pe_ratio: float | None = None

    def missing_fields(self) -> list[str]:
        return [f for f in CORE_METRIC_FIELDS if getattr(self, f) is None]


def get_or_create_company(
    session: Session,
    *,
    ticker: str,
    market: str,
    name: str,
    currency: str,
    industry: str | None = None,
    cik: str | None = None,
) -> Company:
    company = session.execute(
        select(Company).where(Company.market == market, Company.ticker == ticker)
    ).scalar_one_or_none()
    if company is None:
        company = Company(
            ticker=ticker, market=market, name=name, currency=currency, industry=industry, cik=cik
        )
        session.add(company)
        session.flush()
    return company


def upsert_financial_report(
    session: Session,
    *,
    company: Company,
    fiscal_year: int,
    fiscal_quarter: int,
    report_date,
    metrics: NormalizedFinancials,
    currency: str,
    source: str,
    raw_source_ref: str | None = None,
) -> FinancialReport:
    """寫入正規化財報資料，若同期間已有資料則建立新版本（財報更正）。"""
    existing_versions = (
        session.execute(
            select(FinancialReport).where(
                FinancialReport.company_id == company.company_id,
                FinancialReport.fiscal_year == fiscal_year,
                FinancialReport.fiscal_quarter == fiscal_quarter,
            )
        )
        .scalars()
        .all()
    )

    next_version = 1
    if existing_versions:
        next_version = max(r.data_version for r in existing_versions) + 1
        for r in existing_versions:
            if r.is_latest_version:
                r.is_latest_version = False

    report = FinancialReport(
        company_id=company.company_id,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        report_date=report_date,
        revenue=metrics.revenue,
        eps=metrics.eps,
        gross_margin=metrics.gross_margin,
        net_margin=metrics.net_margin,
        debt_ratio=metrics.debt_ratio,
        operating_cash_flow=metrics.operating_cash_flow,
        pe_ratio=metrics.pe_ratio,
        currency=currency,
        source=source,
        data_version=next_version,
        is_latest_version=True,
        raw_source_ref=raw_source_ref,
    )
    session.add(report)
    session.flush()
    return report


def upsert_price_point(
    session: Session,
    *,
    company: Company,
    trade_date,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    source: str,
) -> PriceHistory:
    """寫入單日股價，同一 (company, trade_date) 已存在則覆寫（股價無版本化需求，與財報不同）。"""
    existing = session.execute(
        select(PriceHistory).where(
            PriceHistory.company_id == company.company_id, PriceHistory.trade_date == trade_date
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.open_price = open_price
        existing.high_price = high_price
        existing.low_price = low_price
        existing.close_price = close_price
        existing.volume = volume
        existing.source = source
        session.flush()
        return existing

    point = PriceHistory(
        company_id=company.company_id,
        trade_date=trade_date,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume,
        source=source,
    )
    session.add(point)
    session.flush()
    return point
