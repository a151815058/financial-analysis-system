"""REQ_011：排程真實擷取邏輯（app/jobs.py）。

app/jobs.py 直接使用 app.db_session.SessionLocal 開 session（排程執行不在請求生命
週期內），故測試以獨立的 in-memory sqlite sessionmaker 取代，而非沿用 conftest.py
的 client/db_session fixture（那組是給走 FastAPI 依賴注入的 API 端點測試用的）。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import jobs
from app.db_models import Base, Company, FinancialReport, PriceHistory
from app.ingestion import twse_price_client
from app.ingestion.mops_client import MopsFetchResult
from app.ingestion.normalizer import NormalizedFinancials


def _make_session_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_run_mops_ingest_persists_financial_report(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.commit()
    session.close()

    fake_result = MopsFetchResult(
        ticker="2330",
        fiscal_year=2026,
        fiscal_quarter=1,
        metrics=NormalizedFinancials(
            revenue=100.0,
            eps=1.0,
            gross_margin=50.0,
            net_margin=30.0,
            debt_ratio=20.0,
            operating_cash_flow=None,
            pe_ratio=15.0,
        ),
        report_date=dt.date(2026, 4, 15),
        raw_source_ref="test",
    )
    monkeypatch.setattr(
        "app.jobs.mops_client.fetch_batch", lambda tickers, year, quarter: ([fake_result], [])
    )

    jobs.run_mops_ingest()

    session = session_factory()
    report = session.execute(select(FinancialReport)).scalar_one()
    assert report.revenue == 100.0
    assert report.source == "MOPS"
    session.close()


def test_run_mops_ingest_skips_fetch_when_no_tw_companies(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    called = []
    monkeypatch.setattr("app.jobs.mops_client.fetch_batch", lambda *a, **k: called.append(1))

    jobs.run_mops_ingest()
    assert called == []


def test_run_price_ingest_persists_tw_price(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.commit()
    session.close()

    fake_point = twse_price_client.PricePoint(
        trade_date=dt.date(2026, 7, 10), open=100.0, high=101.0, low=99.0, close=100.5, volume=1000
    )
    monkeypatch.setattr(
        "app.jobs.twse_price_client.fetch_batch",
        lambda tickers, start, end: ({"2330": [fake_point]}, []),
    )

    jobs.run_price_ingest()

    session = session_factory()
    price = session.execute(select(PriceHistory)).scalar_one()
    assert price.close_price == 100.5
    assert price.source == "TWSE"
    session.close()
