"""SQLAlchemy ORM 模型（T-02）。對應 02_system_design/outputs/db_schema.sql 之 7 張資料表。"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("market", "ticker", name="uq_companies_market_ticker"),)

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    market: Mapped[str] = mapped_column(String(2), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    cik: Mapped[str | None] = mapped_column(String(10))  # SEC EDGAR CIK，US 公司排程擷取用；NULL=尚未登記
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    financial_reports: Mapped[list[FinancialReport]] = relationship(back_populates="company")
    price_history: Mapped[list[PriceHistory]] = relationship(back_populates="company")
    predictions: Mapped[list[Prediction]] = relationship(back_populates="company")

    __table_args__ = (
        CheckConstraint("market IN ('TW', 'US')", name="ck_companies_market"),
        CheckConstraint("currency IN ('TWD', 'USD')", name="ck_companies_currency"),
        UniqueConstraint("market", "ticker", name="uq_companies_market_ticker"),
    )


class FinancialReport(Base):
    __tablename__ = "financial_reports"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_quarter",
            "data_version",
            name="uq_financial_reports_period_version",
        ),
        CheckConstraint("fiscal_quarter BETWEEN 1 AND 4", name="ck_financial_reports_quarter"),
        CheckConstraint("source IN ('MOPS', 'SEC_EDGAR')", name="ck_financial_reports_source"),
    )

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.company_id"), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    report_date: Mapped[dt.date] = mapped_column(nullable=False)
    revenue: Mapped[float | None] = mapped_column(Numeric(20, 2))
    eps: Mapped[float | None] = mapped_column(Numeric(10, 4))
    gross_margin: Mapped[float | None] = mapped_column(Numeric(6, 3))
    net_margin: Mapped[float | None] = mapped_column(Numeric(6, 3))
    debt_ratio: Mapped[float | None] = mapped_column(Numeric(6, 3))
    operating_cash_flow: Mapped[float | None] = mapped_column(Numeric(20, 2))
    pe_ratio: Mapped[float | None] = mapped_column(Numeric(10, 3))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    data_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_latest_version: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    raw_source_ref: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[Company] = relationship(back_populates="financial_reports")


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (UniqueConstraint("company_id", "trade_date", name="uq_price_history_company_date"),)

    price_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.company_id"), nullable=False)
    trade_date: Mapped[dt.date] = mapped_column(nullable=False)
    open_price: Mapped[float | None] = mapped_column(Numeric(14, 4))
    high_price: Mapped[float | None] = mapped_column(Numeric(14, 4))
    low_price: Mapped[float | None] = mapped_column(Numeric(14, 4))
    close_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    volume: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[Company] = relationship(back_populates="price_history")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "base_week_start_date",
            "model_version",
            name="uq_predictions_company_week_version",
        ),
        CheckConstraint("direction IN ('UP', 'DOWN', 'FLAT')", name="ck_predictions_direction"),
    )

    prediction_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.company_id"), nullable=False)
    base_week_start_date: Mapped[dt.date] = mapped_column(nullable=False)
    direction: Mapped[str] = mapped_column(String(4), nullable=False)
    range_lower_pct: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    range_upper_pct: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    factor_model_direction: Mapped[str | None] = mapped_column(String(4))
    factor_model_range_lower_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    factor_model_range_upper_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    timeseries_model_direction: Mapped[str | None] = mapped_column(String(4))
    timeseries_model_range_lower_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    timeseries_model_range_upper_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    ensemble_weight_factor: Mapped[float | None] = mapped_column(Numeric(4, 3))
    ensemble_weight_timeseries: Mapped[float | None] = mapped_column(Numeric(4, 3))
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[Company] = relationship(back_populates="predictions")
    backtest: Mapped[PredictionBacktest | None] = relationship(back_populates="prediction")


class PredictionBacktest(Base):
    __tablename__ = "prediction_backtests"
    __table_args__ = (UniqueConstraint("prediction_id", name="uq_prediction_backtests_prediction"),)

    backtest_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.prediction_id"), nullable=False)
    actual_direction: Mapped[str | None] = mapped_column(String(4))
    actual_return_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    direction_hit: Mapped[bool | None] = mapped_column(Boolean)
    range_hit: Mapped[bool | None] = mapped_column(Boolean)
    evaluated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    prediction: Mapped[Prediction] = relationship(back_populates="backtest")


class ApiKey(Base):
    __tablename__ = "api_keys"

    api_key_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="read")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("scope IN ('read', 'admin')", name="ck_api_keys_scope"),)


class AdminUser(Base):
    """`/admin` 頁面帳號密碼登入用之後台管理者帳號（REQ_014），與 api_keys 分開管理。"""

    __tablename__ = "admin_users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobRun(Base):
    """排程任務最新一次執行狀況（REQ_013）。每個 task_name 僅保留最新一筆，執行時 upsert 覆寫。"""

    __tablename__ = "job_runs"
    __table_args__ = (
        CheckConstraint("status IN ('success', 'failure')", name="ck_job_runs_status"),
        CheckConstraint("trigger_mode IN ('scheduled', 'manual')", name="ck_job_runs_trigger_mode"),
    )

    task_name: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    trigger_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(1000))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (CheckConstraint("result IN ('SUCCESS', 'FAILURE')", name="ck_audit_logs_result"),)

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_key_id: Mapped[int | None] = mapped_column(ForeignKey("api_keys.api_key_id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(200))
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(45))  # IPv4/IPv6，🔒 構面 2 項次 19
    detail: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
