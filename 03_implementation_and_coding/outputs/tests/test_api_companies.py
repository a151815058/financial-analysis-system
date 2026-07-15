from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db_models import AuditLog, Company, FinancialReport, PriceHistory


def _seed_company(db_session) -> Company:
    company = Company(ticker="2330", market="TW", name="台積電", currency="TWD", industry="半導體")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


def test_list_companies_empty(client, read_api_key):
    response = client.get("/api/v1/companies", headers={"X-API-Key": read_api_key})
    assert response.status_code == 200
    assert response.json() == []


def test_list_companies_records_source_ip_in_audit_log(client, read_api_key, db_session):
    response = client.get("/api/v1/companies", headers={"X-API-Key": read_api_key})
    assert response.status_code == 200

    log = db_session.execute(select(AuditLog).where(AuditLog.action == "companies.list")).scalar_one()
    assert log.source_ip is not None


def test_list_companies_filters_by_market(client, read_api_key, db_session):
    _seed_company(db_session)
    response = client.get("/api/v1/companies", params={"market": "TW"}, headers={"X-API-Key": read_api_key})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["ticker"] == "2330"


def test_get_financials_returns_404_for_unknown_company(client, read_api_key):
    response = client.get(
        "/api/v1/companies/9999/financials", params={"market": "TW"}, headers={"X-API-Key": read_api_key}
    )
    assert response.status_code == 404


def test_get_financials_returns_latest_version_only(client, read_api_key, db_session):
    company = _seed_company(db_session)
    db_session.add_all(
        [
            FinancialReport(
                company_id=company.company_id,
                fiscal_year=2026,
                fiscal_quarter=1,
                report_date=dt.date(2026, 4, 15),
                revenue=100.0,
                currency="TWD",
                source="MOPS",
                data_version=1,
                is_latest_version=False,
            ),
            FinancialReport(
                company_id=company.company_id,
                fiscal_year=2026,
                fiscal_quarter=1,
                report_date=dt.date(2026, 5, 1),
                revenue=105.0,
                currency="TWD",
                source="MOPS",
                data_version=2,
                is_latest_version=True,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/companies/2330/financials", params={"market": "TW"}, headers={"X-API-Key": read_api_key}
    )
    assert response.status_code == 200
    reports = response.json()["reports"]
    assert len(reports) == 1
    assert reports[0]["revenue"] == 105.0


def test_create_company_tw_succeeds_with_admin_key(client, admin_api_key, db_session):
    response = client.post(
        "/api/v1/companies",
        json={"market": "TW", "ticker": "2317", "name": "鴻海", "industry": "電子零組件"},
        headers={"X-API-Key": admin_api_key},
    )
    assert response.status_code == 201
    body = response.json()
    assert body == {
        "ticker": "2317",
        "market": "TW",
        "name": "鴻海",
        "industry": "電子零組件",
        "currency": "TWD",
    }

    log = db_session.execute(select(AuditLog).where(AuditLog.action == "companies.create")).scalar_one()
    assert log.result == "SUCCESS"


def test_create_company_us_auto_looks_up_cik(client, admin_api_key, monkeypatch, db_session):
    monkeypatch.setattr("app.routers.companies.lookup_cik", lambda ticker: "0000789019")

    response = client.post(
        "/api/v1/companies",
        json={"market": "US", "ticker": "MSFT", "name": "Microsoft Corp."},
        headers={"X-API-Key": admin_api_key},
    )
    assert response.status_code == 201
    assert response.json()["currency"] == "USD"

    company = db_session.execute(
        select(Company).where(Company.market == "US", Company.ticker == "MSFT")
    ).scalar_one()
    assert company.cik == "0000789019"


def test_create_company_us_without_resolvable_cik_returns_422(client, admin_api_key, monkeypatch):
    monkeypatch.setattr("app.routers.companies.lookup_cik", lambda ticker: None)

    response = client.post(
        "/api/v1/companies",
        json={"market": "US", "ticker": "NOSUCH", "name": "Unknown Corp."},
        headers={"X-API-Key": admin_api_key},
    )
    assert response.status_code == 422


def test_create_company_us_with_manual_cik_skips_lookup(client, admin_api_key, monkeypatch):
    def _fail_if_called(ticker):
        raise AssertionError("lookup_cik should not be called when cik is provided manually")

    monkeypatch.setattr("app.routers.companies.lookup_cik", _fail_if_called)

    response = client.post(
        "/api/v1/companies",
        json={"market": "US", "ticker": "AAPL", "name": "Apple Inc.", "cik": "0000320193"},
        headers={"X-API-Key": admin_api_key},
    )
    assert response.status_code == 201
    assert response.json()["ticker"] == "AAPL"


def test_create_company_duplicate_returns_409(client, admin_api_key, db_session):
    _seed_company(db_session)
    response = client.post(
        "/api/v1/companies",
        json={"market": "TW", "ticker": "2330", "name": "台積電"},
        headers={"X-API-Key": admin_api_key},
    )
    assert response.status_code == 409


def test_create_company_requires_admin_scope(client, read_api_key):
    response = client.post(
        "/api/v1/companies",
        json={"market": "TW", "ticker": "2317", "name": "鴻海"},
        headers={"X-API-Key": read_api_key},
    )
    assert response.status_code == 403


def test_get_prices_returns_range(client, read_api_key, db_session):
    company = _seed_company(db_session)
    db_session.add(
        PriceHistory(
            company_id=company.company_id,
            trade_date=dt.date(2026, 7, 10),
            close_price=103.0,
            source="TWSE",
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/companies/2330/prices", params={"market": "TW"}, headers={"X-API-Key": read_api_key}
    )
    assert response.status_code == 200
    prices = response.json()["prices"]
    assert len(prices) == 1
    assert prices[0]["close_price"] == 103.0
