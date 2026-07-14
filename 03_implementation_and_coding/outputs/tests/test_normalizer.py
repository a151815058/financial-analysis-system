from __future__ import annotations

import datetime as dt

from app.ingestion.normalizer import NormalizedFinancials, get_or_create_company, upsert_financial_report


def test_get_or_create_company_is_idempotent(db_session):
    c1 = get_or_create_company(db_session, ticker="2330", market="TW", name="台積電", currency="TWD")
    c2 = get_or_create_company(db_session, ticker="2330", market="TW", name="台積電", currency="TWD")
    assert c1.company_id == c2.company_id


def test_upsert_creates_version_1_for_new_period(db_session):
    company = get_or_create_company(db_session, ticker="2330", market="TW", name="台積電", currency="TWD")
    metrics = NormalizedFinancials(
        revenue=100.0,
        eps=1.5,
        gross_margin=50.0,
        net_margin=30.0,
        debt_ratio=20.0,
        operating_cash_flow=80.0,
        pe_ratio=15.0,
    )
    report = upsert_financial_report(
        db_session,
        company=company,
        fiscal_year=2026,
        fiscal_quarter=1,
        report_date=dt.date(2026, 4, 15),
        metrics=metrics,
        currency="TWD",
        source="MOPS",
    )
    assert report.data_version == 1
    assert report.is_latest_version is True


def test_upsert_creates_new_version_on_restatement_and_demotes_old(db_session):
    company = get_or_create_company(db_session, ticker="2330", market="TW", name="台積電", currency="TWD")
    metrics_v1 = NormalizedFinancials(revenue=100.0)
    metrics_v2 = NormalizedFinancials(revenue=105.0)  # 財報更正後修正數值

    report_v1 = upsert_financial_report(
        db_session,
        company=company,
        fiscal_year=2026,
        fiscal_quarter=1,
        report_date=dt.date(2026, 4, 15),
        metrics=metrics_v1,
        currency="TWD",
        source="MOPS",
    )
    report_v2 = upsert_financial_report(
        db_session,
        company=company,
        fiscal_year=2026,
        fiscal_quarter=1,
        report_date=dt.date(2026, 5, 1),
        metrics=metrics_v2,
        currency="TWD",
        source="MOPS",
    )

    db_session.refresh(report_v1)
    assert report_v1.is_latest_version is False
    assert report_v2.data_version == 2
    assert report_v2.is_latest_version is True
    assert float(report_v2.revenue) == 105.0


def test_missing_fields_reports_none_not_zero():
    metrics = NormalizedFinancials(revenue=100.0)
    missing = metrics.missing_fields()
    assert "eps" in missing
    assert "revenue" not in missing
