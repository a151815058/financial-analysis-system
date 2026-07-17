from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db_models import Base, Company, FinancialReport, PriceHistory
from app.prediction import features


def _make_session_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _report(company_id: int, year: int, quarter: int, **overrides) -> FinancialReport:
    defaults = dict(
        company_id=company_id,
        fiscal_year=year,
        fiscal_quarter=quarter,
        report_date=dt.date(year, quarter * 3, 15),
        revenue=100.0,
        eps=1.0,
        gross_margin=40.0,
        net_margin=20.0,
        debt_ratio=30.0,
        operating_cash_flow=50.0,
        pe_ratio=15.0,
        currency="TWD",
        source="MOPS",
    )
    defaults.update(overrides)
    return FinancialReport(**defaults)


def _make_company(session_factory) -> tuple:
    session = session_factory()
    session.add(Company(ticker="2330", market="TW", name="台積電", currency="TWD"))
    session.commit()
    company = session.query(Company).one()
    session.close()
    return company


# ---------------------------------------------------------------------------
# compute_derived_features
# ---------------------------------------------------------------------------


def test_compute_derived_features_none_without_prior_year():
    report = _report(1, 2026, 2)
    prior_quarter = _report(1, 2026, 1)
    assert features.compute_derived_features(report, None, prior_quarter) is None


def test_compute_derived_features_none_without_prior_quarter():
    report = _report(1, 2026, 2)
    prior_year = _report(1, 2025, 2)
    assert features.compute_derived_features(report, prior_year, None) is None


def test_compute_derived_features_none_when_core_metric_missing():
    report = _report(1, 2026, 2, pe_ratio=None)
    prior_year = _report(1, 2025, 2)
    prior_quarter = _report(1, 2026, 1)
    assert features.compute_derived_features(report, prior_year, prior_quarter) is None


def test_compute_derived_features_computes_yoy_qoq():
    report = _report(1, 2026, 2, revenue=110.0, eps=1.2, operating_cash_flow=55.0)
    prior_year = _report(1, 2025, 2, revenue=100.0, operating_cash_flow=50.0)
    prior_quarter = _report(1, 2026, 1, eps=1.0)

    feat = features.compute_derived_features(report, prior_year, prior_quarter)
    assert feat is not None
    assert feat["revenue_yoy"] == pytest.approx(10.0)
    assert feat["eps_qoq"] == pytest.approx(20.0)
    assert feat["operating_cash_flow_yoy"] == pytest.approx(10.0)
    assert feat["gross_margin"] == 40.0
    assert set(feat.keys()) == set(features.FEATURE_COLUMNS)


# ---------------------------------------------------------------------------
# compute_future_weekly_return_pct
# ---------------------------------------------------------------------------


def test_compute_future_weekly_return_pct_none_when_not_enough_future_prices():
    session_factory = _make_session_factory()
    session = session_factory()
    company = _make_company(session_factory)
    session.add(company)
    session.commit()

    base = dt.date(2026, 4, 15)
    for i in range(4):  # 只有 4 天，需要 6 天（base + 5 個交易日）
        session.add(
            PriceHistory(
                company_id=company.company_id,
                trade_date=base + dt.timedelta(days=i),
                close_price=100 + i,
                source="TWSE",
            )
        )
    session.commit()

    assert features.compute_future_weekly_return_pct(session, company.company_id, base) is None
    session.close()


def test_compute_future_weekly_return_pct_computes_return():
    session_factory = _make_session_factory()
    session = session_factory()
    company = _make_company(session_factory)
    session.add(company)
    session.commit()

    base = dt.date(2026, 4, 15)
    closes = [100, 101, 102, 103, 104, 110]
    for i, close in enumerate(closes):
        session.add(
            PriceHistory(
                company_id=company.company_id,
                trade_date=base + dt.timedelta(days=i),
                close_price=close,
                source="TWSE",
            )
        )
    session.commit()

    result = features.compute_future_weekly_return_pct(session, company.company_id, base)
    assert result == pytest.approx((110 - 100) / 100 * 100)
    session.close()


# ---------------------------------------------------------------------------
# build_inference_features / build_training_dataset
# ---------------------------------------------------------------------------


def test_build_inference_features_none_when_no_reports():
    session_factory = _make_session_factory()
    session = session_factory()
    company = _make_company(session_factory)
    session.add(company)
    session.commit()

    assert features.build_inference_features(session, company) is None
    session.close()


def test_build_inference_features_uses_latest_report_with_enough_history():
    session_factory = _make_session_factory()
    session = session_factory()
    company = _make_company(session_factory)
    session.add(company)
    session.commit()

    session.add_all(
        [
            _report(company.company_id, 2025, 2, revenue=100.0),
            _report(company.company_id, 2026, 1, eps=1.0),
            _report(company.company_id, 2026, 2, revenue=110.0, eps=1.2),
        ]
    )
    session.commit()

    result = features.build_inference_features(session, company)
    assert result is not None
    assert len(result) == 1
    assert list(result.columns) == features.FEATURE_COLUMNS
    session.close()


def test_build_training_dataset_empty_when_no_reports():
    session_factory = _make_session_factory()
    session = session_factory()
    company = _make_company(session_factory)
    session.add(company)
    session.commit()

    features_df, labels = features.build_training_dataset(session, [company])
    assert features_df.empty
    assert labels.empty
    session.close()


def test_build_training_dataset_pools_multiple_trainable_quarters():
    session_factory = _make_session_factory()
    session = session_factory()
    company = _make_company(session_factory)
    session.add(company)
    session.commit()

    # 5 個連續季度：第一筆（2025Q2）當基準，之後每季皆有前一年同季+前一季可比對 -> 4 筆可訓練樣本
    reports = [
        _report(company.company_id, 2025, 2, revenue=90.0, eps=0.8),
        _report(company.company_id, 2025, 3, revenue=95.0, eps=0.9),
        _report(company.company_id, 2025, 4, revenue=100.0, eps=1.0),
        _report(company.company_id, 2026, 1, revenue=105.0, eps=1.1),
        _report(company.company_id, 2026, 2, revenue=110.0, eps=1.2),
        _report(company.company_id, 2026, 3, revenue=115.0, eps=1.3),
    ]
    session.add_all(reports)
    session.commit()

    # 每筆財報公布日後都補滿 6 天股價，讓 compute_future_weekly_return_pct 有得算
    for report in reports:
        for i in range(6):
            session.add(
                PriceHistory(
                    company_id=company.company_id,
                    trade_date=report.report_date + dt.timedelta(days=i),
                    close_price=100 + i,
                    source="TWSE",
                )
            )
    session.commit()

    features_df, labels = features.build_training_dataset(session, [company])
    # 前 4 季（index 0~3）缺前一年同季資料，無法算 YoY；index 4~5（2026Q2/Q3）才同時有
    # prior_year(2025Q2/Q3) 與 prior_quarter(2026Q1/Q2) -> 2 筆可訓練樣本
    assert len(features_df) == 2
    assert len(labels) == 2
    assert list(features_df.columns) == features.FEATURE_COLUMNS
    session.close()
