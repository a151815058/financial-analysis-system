"""REQ_011：排程真實擷取邏輯（app/jobs.py）。

app/jobs.py 直接使用 app.db_session.SessionLocal 開 session（排程執行不在請求生命
週期內），故測試以獨立的 in-memory sqlite sessionmaker 取代，而非沿用 conftest.py
的 client/db_session fixture（那組是給走 FastAPI 依賴注入的 API 端點測試用的）。
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import jobs
from app.db_models import (
    Base,
    Company,
    FinancialReport,
    JobRun,
    Prediction,
    PredictionBacktest,
    PriceHistory,
    TrainedModel,
)
from app.ingestion import twse_price_client
from app.ingestion.mops_client import MopsFetchResult
from app.ingestion.normalizer import NormalizedFinancials
from app.prediction import model_registry
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


# ---------------------------------------------------------------------------
# REQ_009：weekly_backtest（拿歷史預測比對實際股價，評分方向/區間命中率）
# ---------------------------------------------------------------------------


def _weekdays_after(start: dt.date, n: int) -> list[dt.date]:
    """從 start 之後（不含）依序取 n 個平日日期（略過週六日），模擬真實交易日序列。"""
    dates: list[dt.date] = []
    current = start
    while len(dates) < n:
        current = current + dt.timedelta(days=1)
        if current.weekday() < 5:
            dates.append(current)
    return dates


def _seed_gradable_prediction(
    session_factory,
    *,
    ticker: str = "2330",
    market: str = "TW",
    base_week_start: dt.date = dt.date(2026, 3, 2),
    baseline_close: float = 100.0,
    target_close: float = 104.0,
    direction: str = "UP",
    range_lower_pct: float = 2.0,
    range_upper_pct: float = 6.0,
    n_target_days: int = 5,
):
    """建立一家公司 + 一筆基準收盤價 + n_target_days 筆後續交易日收盤價（僅最後一筆採
    target_close，其餘用內插值）+ 一筆對應的 Prediction，回傳 (company_id, prediction_id)。"""
    session = session_factory()
    session.add(Company(ticker=ticker, market=market, name=f"{ticker} Inc.", currency="TWD" if market == "TW" else "USD"))
    session.commit()
    company = session.query(Company).filter_by(ticker=ticker, market=market).one()

    session.add(
        PriceHistory(company_id=company.company_id, trade_date=base_week_start, close_price=baseline_close, source="TWSE")
    )
    target_dates = _weekdays_after(base_week_start, n_target_days)
    for i, d in enumerate(target_dates):
        is_last = i == len(target_dates) - 1
        close = target_close if is_last else baseline_close + (target_close - baseline_close) * (i + 1) / len(target_dates)
        session.add(PriceHistory(company_id=company.company_id, trade_date=d, close_price=close, source="TWSE"))

    session.add(
        Prediction(
            company_id=company.company_id,
            base_week_start_date=base_week_start,
            direction=direction,
            range_lower_pct=range_lower_pct,
            range_upper_pct=range_upper_pct,
            confidence_score=0.8,
            model_version="v-test",
        )
    )
    session.commit()
    prediction = session.query(Prediction).filter_by(company_id=company.company_id).one()
    prediction_id = prediction.prediction_id
    company_id = company.company_id
    session.close()
    return company_id, prediction_id


def test_run_weekly_backtest_no_pending_predictions_is_noop(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    jobs.run_weekly_backtest()  # 不應拋例外

    session = session_factory()
    assert session.execute(select(PredictionBacktest)).scalars().all() == []
    session.close()


def test_run_weekly_backtest_direction_and_range_hit(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    _, prediction_id = _seed_gradable_prediction(
        session_factory, target_close=104.0, direction="UP", range_lower_pct=2.0, range_upper_pct=6.0
    )

    jobs.run_weekly_backtest()

    session = session_factory()
    backtest = session.execute(
        select(PredictionBacktest).where(PredictionBacktest.prediction_id == prediction_id)
    ).scalar_one()
    assert backtest.actual_direction == "UP"
    assert backtest.direction_hit is True
    assert backtest.range_hit is True
    assert backtest.actual_return_pct == pytest.approx(4.0, abs=0.01)
    session.close()


def test_run_weekly_backtest_direction_miss(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    _, prediction_id = _seed_gradable_prediction(
        session_factory, target_close=95.0, direction="UP", range_lower_pct=2.0, range_upper_pct=6.0
    )

    jobs.run_weekly_backtest()

    session = session_factory()
    backtest = session.execute(
        select(PredictionBacktest).where(PredictionBacktest.prediction_id == prediction_id)
    ).scalar_one()
    assert backtest.actual_direction == "DOWN"
    assert backtest.direction_hit is False
    session.close()


def test_run_weekly_backtest_direction_hit_range_miss(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    _, prediction_id = _seed_gradable_prediction(
        session_factory, target_close=115.0, direction="UP", range_lower_pct=2.0, range_upper_pct=6.0
    )

    jobs.run_weekly_backtest()

    session = session_factory()
    backtest = session.execute(
        select(PredictionBacktest).where(PredictionBacktest.prediction_id == prediction_id)
    ).scalar_one()
    assert backtest.direction_hit is True
    assert backtest.range_hit is False
    session.close()


def test_run_weekly_backtest_skips_when_target_price_not_yet_available(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    _seed_gradable_prediction(session_factory, n_target_days=3)  # 不足 5 個交易日

    jobs.run_weekly_backtest()  # 不應拋例外

    session = session_factory()
    assert session.execute(select(PredictionBacktest)).scalars().all() == []
    session.close()


def test_run_weekly_backtest_skips_when_baseline_price_missing(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.commit()
    company = session.query(Company).one()
    # 無任何 PriceHistory，基準價回溯視窗內找不到資料
    session.add(
        Prediction(
            company_id=company.company_id,
            base_week_start_date=dt.date(2026, 3, 2),
            direction="UP",
            range_lower_pct=2.0,
            range_upper_pct=6.0,
            confidence_score=0.8,
            model_version="v-test",
        )
    )
    session.commit()
    session.close()

    jobs.run_weekly_backtest()  # 不應拋例外

    session = session_factory()
    assert session.execute(select(PredictionBacktest)).scalars().all() == []
    session.close()


def test_run_weekly_backtest_does_not_regrade_existing_backtest(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    _, prediction_id = _seed_gradable_prediction(session_factory, target_close=104.0, direction="UP")

    session = session_factory()
    session.add(
        PredictionBacktest(
            prediction_id=prediction_id,
            actual_direction="FLAT",
            actual_return_pct=0.0,
            direction_hit=False,
            range_hit=False,
        )
    )
    session.commit()
    session.close()

    jobs.run_weekly_backtest()

    session = session_factory()
    backtests = session.execute(select(PredictionBacktest)).scalars().all()
    assert len(backtests) == 1
    assert backtests[0].actual_direction == "FLAT"
    assert backtests[0].direction_hit is False
    session.close()


def test_run_weekly_backtest_isolates_per_prediction_failure(monkeypatch):
    """單一預測評分過程拋例外時，不應中斷其餘預測的評分（批次隔離）。"""
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    flaky_company_id, _ = _seed_gradable_prediction(session_factory, ticker="2330", market="TW", target_close=104.0)
    _, healthy_prediction_id = _seed_gradable_prediction(
        session_factory, ticker="AAPL", market="US", target_close=104.0
    )

    real_baseline = jobs._nearest_baseline_price

    def _flaky_baseline(session, company_id, base_week_start):
        if company_id == flaky_company_id:
            raise RuntimeError("模擬股價查詢失敗")
        return real_baseline(session, company_id, base_week_start)

    monkeypatch.setattr(jobs, "_nearest_baseline_price", _flaky_baseline)

    jobs.run_weekly_backtest()  # 不應向外拋例外

    session = session_factory()
    backtests = session.execute(select(PredictionBacktest)).scalars().all()
    assert len(backtests) == 1
    assert backtests[0].prediction_id == healthy_prediction_id
    session.close()


# ---------------------------------------------------------------------------
# REQ_004：model_retrain（訓練財報因子模型並持久化，取代每次即時重訓）
# ---------------------------------------------------------------------------


def test_run_model_retrain_no_companies_is_noop(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    jobs.run_model_retrain()  # 不應拋例外

    session = session_factory()
    assert session.execute(select(TrainedModel)).scalars().all() == []
    session.close()


def test_run_model_retrain_insufficient_samples_preserves_existing_model(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.add(
        TrainedModel(
            model_name="factor_model",
            model_version="sentinel-v1",
            trained_at=dt.datetime(2020, 1, 1, tzinfo=dt.UTC),
            sample_size=42,
            artifact=b"sentinel-bytes",
        )
    )
    session.commit()
    session.close()

    jobs.run_model_retrain()  # 真實財報樣本數為 0，遠低於 10 筆訓練門檻

    session = session_factory()
    row = session.get(TrainedModel, "factor_model")
    assert row.model_version == "sentinel-v1"
    assert row.artifact == b"sentinel-bytes"
    session.close()


def test_run_model_retrain_persists_model_when_sufficient_samples(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.commit()
    session.close()

    features_df, labels = _synthetic_factor_dataset()
    monkeypatch.setattr(
        jobs.prediction_features, "build_training_dataset", lambda session, companies: (features_df, labels)
    )

    jobs.run_model_retrain()

    session = session_factory()
    rows = session.execute(select(TrainedModel)).scalars().all()
    assert len(rows) == 1
    assert rows[0].sample_size == len(features_df)
    loaded = model_registry.load_factor_model(session)
    assert loaded is not None
    loaded.predict(features_df.iloc[:1])  # 還原後仍可正常推論，不拋例外
    session.close()


def test_run_model_retrain_rerun_upserts_single_row(monkeypatch):
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.commit()
    session.close()

    features_df, labels = _synthetic_factor_dataset()
    monkeypatch.setattr(
        jobs.prediction_features, "build_training_dataset", lambda session, companies: (features_df, labels)
    )

    jobs.run_model_retrain()
    session = session_factory()
    first_trained_at = session.get(TrainedModel, "factor_model").trained_at
    session.close()

    jobs.run_model_retrain()

    session = session_factory()
    rows = session.execute(select(TrainedModel)).scalars().all()
    assert len(rows) == 1
    assert rows[0].trained_at >= first_trained_at
    session.close()


def test_run_weekly_predict_uses_persisted_model_when_available(monkeypatch):
    """已有持久化模型時，weekly_predict 應優先載入使用，不應 fallback 呼叫即時訓練。"""
    session_factory = _make_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)

    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.commit()
    company = session.query(Company).one()
    for row in _synthetic_price_rows(company.company_id, n=60):
        session.add(row)
    session.commit()

    features_df, labels = _synthetic_factor_dataset()
    fitted_model = FactorModel().fit(features_df, labels)
    model_registry.save_factor_model(
        session,
        fitted_model,
        version="persisted-v1",
        sample_size=len(features_df),
        trained_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
    )
    session.commit()
    session.close()

    def _boom(session, companies):
        raise AssertionError("不應呼叫即時訓練 fallback，因為已有持久化模型可用")

    monkeypatch.setattr(jobs, "_train_pooled_factor_model", _boom)
    monkeypatch.setattr(
        jobs.prediction_features, "build_inference_features", lambda session, company: features_df.iloc[:1]
    )

    jobs.run_weekly_predict()  # 不應拋例外（尤其不應觸發 _boom）

    session = session_factory()
    prediction = session.execute(select(Prediction)).scalar_one()
    assert prediction.factor_model_direction is not None
    session.close()
