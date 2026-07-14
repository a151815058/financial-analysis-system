"""Phase 04 系統整合測試 (System / E2E Test)

與 Phase 03 的 `03_implementation_and_coding/outputs/tests/` 不同：Phase 03 使用 FastAPI
`TestClient`（in-process，呼叫直接進 ASGI app，不經過真實網路與獨立 process）；本檔案
實際以子行程啟動 `uvicorn`，透過真實 HTTP 呼叫驗證整個部署路徑（`run.bat`/`start.sh`
所啟動的服務）可正常運作，驗證項目涵蓋 REQ_001~REQ_009、REQ_SEC_001。

執行方式：
    cd 03_implementation_and_coding/outputs
    python -m pytest ../../../04_testing/outputs/test_api.py -v
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

APP_DIR = Path(__file__).resolve().parents[2] / "03_implementation_and_coding" / "outputs"
sys.path.insert(0, str(APP_DIR))

from app.db_models import ApiKey, Base, Company, FinancialReport, PriceHistory, Prediction  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def e2e_server(tmp_path_factory):
    """啟動真實 uvicorn 子行程，指向獨立的 SQLite 測試資料庫，並預先灌入種子資料。"""
    db_path = tmp_path_factory.mktemp("e2e_db") / "e2e_test.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    company = Company(ticker="2330", market="TW", name="台積電", currency="TWD", industry="半導體")
    session.add(company)
    session.flush()

    session.add(
        FinancialReport(
            company_id=company.company_id,
            fiscal_year=2026,
            fiscal_quarter=1,
            report_date=dt.date(2026, 4, 15),
            revenue=592_000_000_000,
            eps=9.87,
            gross_margin=55.2,
            net_margin=40.1,
            debt_ratio=32.5,
            operating_cash_flow=350_000_000_000,
            pe_ratio=18.3,
            currency="TWD",
            source="MOPS",
            data_version=1,
            is_latest_version=True,
        )
    )
    session.add(
        PriceHistory(
            company_id=company.company_id, trade_date=dt.date(2026, 7, 10), close_price=103.0, source="TWSE"
        )
    )
    session.add(
        Prediction(
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
            model_version="v1.0.0-e2e",
        )
    )
    read_key, admin_key = "e2e-read-key-0001", "e2e-admin-key-0001"
    session.add(ApiKey(key_hash=_hash_key(read_key), owner="e2e-tester", scope="read"))
    session.add(ApiKey(key_hash=_hash_key(admin_key), owner="e2e-admin", scope="admin"))
    session.commit()
    session.close()

    port = _free_port()
    env = dict(os.environ, DATABASE_URL=db_url)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(APP_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    started = False
    while time.time() < deadline:
        try:
            if requests.get(f"{base_url}/health", timeout=1).status_code == 200:
                started = True
                break
        except requests.ConnectionError:
            time.sleep(0.3)

    if not started:
        proc.terminate()
        output = proc.stdout.read().decode("utf-8", errors="replace") if proc.stdout else ""
        pytest.fail(f"uvicorn 未能於逾時內啟動完成，輸出：\n{output}")

    yield {"base_url": base_url, "read_key": read_key, "admin_key": admin_key}

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_health_check_returns_200(e2e_server):
    response = requests.get(f"{e2e_server['base_url']}/health", timeout=5)
    assert response.status_code == 200
    assert "免責" not in response.json()["disclaimer"]  # 確認欄位存在且非中斷字串
    assert "僅供分析參考" in response.json()["disclaimer"]


def test_missing_api_key_rejected_over_real_http(e2e_server):
    response = requests.get(f"{e2e_server['base_url']}/api/v1/companies", timeout=5)
    assert response.status_code == 401


def test_list_companies_real_http_roundtrip(e2e_server):
    response = requests.get(
        f"{e2e_server['base_url']}/api/v1/companies",
        headers={"X-API-Key": e2e_server["read_key"]},
        timeout=5,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["ticker"] == "2330"


def test_get_financials_real_http_roundtrip(e2e_server):
    response = requests.get(
        f"{e2e_server['base_url']}/api/v1/companies/2330/financials",
        params={"market": "TW"},
        headers={"X-API-Key": e2e_server["read_key"]},
        timeout=5,
    )
    assert response.status_code == 200
    reports = response.json()["reports"]
    assert len(reports) == 1
    assert reports[0]["eps"] == 9.87


def test_get_latest_prediction_real_http_roundtrip(e2e_server):
    response = requests.get(
        f"{e2e_server['base_url']}/api/v1/companies/2330/predictions/latest",
        params={"market": "TW"},
        headers={"X-API-Key": e2e_server["read_key"]},
        timeout=5,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["direction"] == "UP"
    assert body["sub_models"]["factor_model"]["direction"] == "UP"


def test_get_backtest_returns_404_when_no_data_yet(e2e_server):
    response = requests.get(
        f"{e2e_server['base_url']}/api/v1/companies/2330/backtest",
        params={"market": "TW"},
        headers={"X-API-Key": e2e_server["read_key"]},
        timeout=5,
    )
    assert response.status_code == 404  # REQ_009：尚無回測資料時應明確回報，非靜默回傳空結果


def test_read_scope_cannot_trigger_admin_endpoint_real_http(e2e_server):
    response = requests.post(
        f"{e2e_server['base_url']}/api/v1/admin/ingest/trigger",
        json={"task": "mops_ingest"},
        headers={"X-API-Key": e2e_server["read_key"]},
        timeout=5,
    )
    assert response.status_code == 403


def test_admin_scope_can_trigger_ingest_real_http(e2e_server):
    response = requests.post(
        f"{e2e_server['base_url']}/api/v1/admin/ingest/trigger",
        json={"task": "mops_ingest"},
        headers={"X-API-Key": e2e_server["admin_key"]},
        timeout=5,
    )
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_unknown_company_returns_404_not_500(e2e_server):
    response = requests.get(
        f"{e2e_server['base_url']}/api/v1/companies/9999/financials",
        params={"market": "TW"},
        headers={"X-API-Key": e2e_server["read_key"]},
        timeout=5,
    )
    assert response.status_code == 404
