from __future__ import annotations

import datetime as dt

from app.db_models import Company, Prediction, PredictionBacktest


def _seed_company_with_prediction(db_session) -> Company:
    company = Company(ticker="2330", market="TW", name="台積電", currency="TWD")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    prediction = Prediction(
        company_id=company.company_id,
        base_week_start_date=dt.date(2026, 7, 13),
        direction="UP",
        range_lower_pct=2.0,
        range_upper_pct=5.0,
        confidence_score=0.72,
        factor_model_direction="UP",
        factor_model_range_lower_pct=1.5,
        factor_model_range_upper_pct=4.0,
        timeseries_model_direction="UP",
        timeseries_model_range_lower_pct=2.5,
        timeseries_model_range_upper_pct=6.0,
        ensemble_weight_factor=0.6,
        ensemble_weight_timeseries=0.4,
        model_version="v1.0.0-test",
    )
    db_session.add(prediction)
    db_session.commit()
    db_session.refresh(prediction)
    return company, prediction


def test_get_latest_prediction_returns_submodel_detail(client, read_api_key, db_session):
    _seed_company_with_prediction(db_session)

    response = client.get(
        "/api/v1/companies/2330/predictions/latest",
        params={"market": "TW"},
        headers={"X-API-Key": read_api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["direction"] == "UP"
    assert body["sub_models"]["factor_model"]["direction"] == "UP"
    assert body["sub_models"]["timeseries_model"]["range_pct"] == [2.5, 6.0]


def test_get_latest_prediction_accepts_session_login_without_api_key(client, admin_user, db_session):
    """REQ_015：/dashboard 改用登入 session，預測端點需同時接受 session 與既有 API Key。"""
    _seed_company_with_prediction(db_session)
    username, password = admin_user
    client.post("/api/v1/auth/login", json={"username": username, "password": password})

    response = client.get("/api/v1/companies/2330/predictions/latest", params={"market": "TW"})
    assert response.status_code == 200


def test_get_latest_prediction_404_when_none_exists(client, read_api_key, db_session):
    db_session.add(Company(ticker="2317", market="TW", name="鴻海", currency="TWD"))
    db_session.commit()

    response = client.get(
        "/api/v1/companies/2317/predictions/latest",
        params={"market": "TW"},
        headers={"X-API-Key": read_api_key},
    )
    assert response.status_code == 404


def test_get_backtest_computes_accuracy(client, read_api_key, db_session):
    company, prediction = _seed_company_with_prediction(db_session)
    db_session.add(
        PredictionBacktest(
            prediction_id=prediction.prediction_id,
            actual_direction="UP",
            actual_return_pct=3.5,
            direction_hit=True,
            range_hit=True,
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/companies/2330/backtest", params={"market": "TW"}, headers={"X-API-Key": read_api_key}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["directional_accuracy"] == 1.0
    assert body["range_hit_rate"] == 1.0
