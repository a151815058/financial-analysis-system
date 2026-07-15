"""Pydantic 請求/回應 Schema（對應 02_system_design/outputs/api_spec.md）。"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Market = Literal["TW", "US"]
Direction = Literal["UP", "DOWN", "FLAT"]


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    market: Market
    name: str
    industry: str | None = None
    currency: str


class CompanyCreateRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    market: Market
    name: str = Field(min_length=1, max_length=200)
    industry: str | None = Field(default=None, max_length=100)
    cik: str | None = Field(default=None, min_length=1, max_length=10)


class FinancialReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fiscal_year: int
    fiscal_quarter: int
    report_date: dt.date
    revenue: float | None = None
    eps: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None
    debt_ratio: float | None = None
    operating_cash_flow: float | None = None
    pe_ratio: float | None = None
    currency: str
    source: Literal["MOPS", "SEC_EDGAR"]
    is_latest_version: bool


class FinancialsResponse(BaseModel):
    ticker: str
    market: Market
    reports: list[FinancialReportOut]


class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trade_date: dt.date
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    close_price: float
    volume: int | None = None


class PricesResponse(BaseModel):
    ticker: str
    market: Market
    prices: list[PriceOut]


class SubModelResult(BaseModel):
    direction: Direction | None = None
    range_pct: tuple[float, float] | None = None


class PredictionOut(BaseModel):
    ticker: str
    market: Market
    base_week_start_date: dt.date
    direction: Direction
    range_lower_pct: float
    range_upper_pct: float
    confidence_score: float = Field(ge=0, le=1)
    sub_models: dict[str, SubModelResult]
    model_version: str


class BacktestResponse(BaseModel):
    ticker: str
    market: Market
    window_weeks: int
    directional_accuracy: float
    range_hit_rate: float


class IngestTriggerRequest(BaseModel):
    task: Literal[
        "mops_ingest", "sec_edgar_ingest", "price_ingest", "model_retrain", "weekly_predict", "weekly_backtest"
    ]


class IngestTriggerResponse(BaseModel):
    task: str
    status: Literal["accepted"]
