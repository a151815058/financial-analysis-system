"""REQ_011：排程真實擷取邏輯（app/jobs.py）。

app/jobs.py 直接使用 app.db_session.SessionLocal 開 session（排程執行不在請求生命
週期內），故測試以獨立的 in-memory sqlite sessionmaker 取代，而非沿用 conftest.py
的 client/db_session fixture（那組是給走 FastAPI 依賴注入的 API 端點測試用的）。
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import jobs
from app.db_models import Base, Company, FinancialReport, JobRun, Prediction, PriceHistory
from app.ingestion import twse_price_client
from app.ingestion.mops_client import MopsFetchResult
from app.ingestion.normalizer import NormalizedFinancials
from app.prediction.factor_model import FactorModel


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


# ---------------------------------------------------------------------------
# REQ_013：track_job 執行狀態記錄（job_runs upsert）
# ---------------------------------------------------------------------------


def test_track_job_records_success(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    wrapped = jobs.track_job("demo_task", lambda: None)
    wrapped()

    session = session_factory()
    run = session.get(JobRun, "demo_task")
    assert run.status == "success"
    assert run.trigger_mode == "scheduled"
    assert run.detail is None
    session.close()


def test_track_job_records_failure_and_does_not_raise(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    def _boom():
        raise ValueError("external API unreachable")

    wrapped = jobs.track_job("demo_task", _boom)
    wrapped()  # 不應該往外拋例外，否則排程執行緒會中斷

    session = session_factory()
    run = session.get(JobRun, "demo_task")
    assert run.status == "failure"
    assert "external API unreachable" in run.detail
    session.close()


def test_track_job_records_manual_trigger_mode(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    wrapped = jobs.track_job("demo_task", lambda: None)
    wrapped(trigger_mode="manual")

    session = session_factory()
    run = session.get(JobRun, "demo_task")
    assert run.trigger_mode == "manual"
    session.close()


def test_track_job_upserts_single_row_per_task(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    wrapped = jobs.track_job("demo_task", lambda: None)
    wrapped()
    wrapped()

    session = session_factory()
    runs = session.execute(select(JobRun).where(JobRun.task_name == "demo_task")).scalars().all()
    assert len(runs) == 1
    session.close()


# ---------------------------------------------------------------------------
# REQ_004/005/006：weekly_predict（財報因子模型 + 時間序列模型 -> 每週預測）
# ---------------------------------------------------------------------------


def _synthetic_price_rows(company_id: int, n: int = 60, seed: int = 7) -> list[PriceHistory]:
    """比照 test_timeseries_model.py 的隨機漫步生成手法，確保 ARIMA 可正常收斂。"""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    prices = 100 + np.cumsum(rng.normal(0.1, 1.0, n))
    return [
        PriceHistory(company_id=company_id, trade_date=d.date(), close_price=float(p), source="TWSE")
        for d, p in zip(dates, prices, strict=True)
    ]


def _synthetic_factor_dataset(n: int = 60, seed: int = 42):
    rng = np.random.default_rng(seed)
    features_df = pd.DataFrame(
        {
            "revenue_yoy": rng.normal(5, 3, n),
            "eps_qoq": rng.normal(0, 2, n),
            "gross_margin": rng.normal(45, 5, n),
            "net_margin": rng.normal(20, 3, n),
            "debt_ratio": rng.normal(30, 5, n),
            "operating_cash_flow_yoy": rng.normal(5, 3, n),
            "pe_ratio": rng.normal(15, 2, n),
        }
    )
    weekly_return_pct = 0.3 * features_df["revenue_yoy"] + rng.normal(0, 1, n)
    return features_df, weekly_return_pct


def test_run_weekly_predict_no_companies_is_noop(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    jobs.run_weekly_predict()  # 不應拋例外

    session = session_factory()
    assert session.execute(select(Prediction)).scalars().all() == []
    session.close()


def test_run_weekly_predict_skips_company_with_insufficient_price_history(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.commit()
    company = session.query(Company).one()
    for row in _synthetic_price_rows(company.company_id, n=10):  # 少於 30 天門檻
        session.add(row)
    session.commit()
    session.close()

    jobs.run_weekly_predict()

    session = session_factory()
    assert session.execute(select(Prediction)).scalars().all() == []
    session.close()


def test_run_weekly_predict_degrades_to_timeseries_only_when_factor_data_insufficient(monkeypatch):
    """財報因子模型資料不足（無財報）時，應仍寫入僅時間序列模型之預測，並清楚標記 model_version。"""
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.commit()
    company = session.query(Company).one()
    for row in _synthetic_price_rows(company.company_id, n=60):
        session.add(row)
    session.commit()
    session.close()

    jobs.run_weekly_predict()

    session = session_factory()
    prediction = session.execute(select(Prediction)).scalar_one()
    assert prediction.model_version == f"{jobs.MODEL_VERSION}-ts-only"
    assert prediction.factor_model_direction is None
    assert prediction.ensemble_weight_factor == 0.0
    assert prediction.ensemble_weight_timeseries == 1.0
    assert prediction.timeseries_model_direction == prediction.direction
    session.close()


def test_run_weekly_predict_full_ensemble_when_factor_model_available(monkeypatch):
    """財報因子模型可訓練時，應寫入真正融合兩子模型之預測（非 -ts-only 降級版）。"""
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.commit()
    company = session.query(Company).one()
    for row in _synthetic_price_rows(company.company_id, n=60):
        session.add(row)
    session.commit()
    session.close()

    features_df, labels = _synthetic_factor_dataset()
    fitted_model = FactorModel().fit(features_df, labels)
    monkeypatch.setattr(jobs, "_train_pooled_factor_model", lambda session, companies: fitted_model)
    monkeypatch.setattr(
        jobs.prediction_features, "build_inference_features", lambda session, company: features_df.iloc[:1]
    )

    jobs.run_weekly_predict()

    session = session_factory()
    prediction = session.execute(select(Prediction)).scalar_one()
    assert prediction.model_version == jobs.MODEL_VERSION
    assert prediction.factor_model_direction is not None
    assert 0.0 < prediction.ensemble_weight_factor < 1.0
    session.close()


def test_run_weekly_predict_rerun_replaces_same_week_prediction(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.commit()
    company = session.query(Company).one()
    for row in _synthetic_price_rows(company.company_id, n=60):
        session.add(row)
    session.commit()
    session.close()

    jobs.run_weekly_predict()
    jobs.run_weekly_predict()

    session = session_factory()
    predictions = session.execute(select(Prediction)).scalars().all()
    assert len(predictions) == 1
    session.close()


def test_run_weekly_predict_isolates_per_company_failure(monkeypatch):
    """單一公司預測邏輯拋例外時，不應中斷其餘公司的預測（批次隔離）。"""
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.add(Company(ticker="AAPL", market="US", name="Apple Inc.", currency="USD"))
    session.commit()
    companies = {c.ticker: c for c in session.query(Company).all()}
    aapl_company_id = companies["AAPL"].company_id
    for row in _synthetic_price_rows(companies["2330"].company_id, n=60):
        session.add(row)
    for row in _synthetic_price_rows(aapl_company_id, n=60, seed=11):
        session.add(row)
    session.commit()
    session.close()

    real_predict = jobs._predict_company_timeseries

    def _flaky_predict(session, company):
        if company.ticker == "2330":
            raise RuntimeError("模擬 ARIMA 收斂失敗")
        return real_predict(session, company)

    monkeypatch.setattr(jobs, "_predict_company_timeseries", _flaky_predict)

    jobs.run_weekly_predict()  # 不應向外拋例外

    session = session_factory()
    predictions = session.execute(select(Prediction)).scalars().all()
    assert len(predictions) == 1
    assert predictions[0].company_id == aapl_company_id
    session.close()
