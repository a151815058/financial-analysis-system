"""REQ_013：GET /api/v1/admin/jobs 排程狀態查詢（含最新一次執行結果）。"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db_models import AuditLog, JobRun

EXPECTED_TASKS = {
    "mops_ingest",
    "sec_edgar_ingest",
    "price_ingest",
    "weekly_predict",
    "model_retrain",
    "weekly_backtest",
}


def test_list_jobs_returns_all_six_tasks_with_next_run_time(client, admin_api_key):
    response = client.get("/api/v1/admin/jobs", headers={"X-API-Key": admin_api_key})
    assert response.status_code == 200
    body = response.json()
    assert {job["id"] for job in body} == EXPECTED_TASKS
    assert all(job["next_run_time"] is not None for job in body)
    assert all(job["last_run"] is None for job in body)  # 尚未有任何執行紀錄


def test_list_jobs_includes_last_run_status(client, admin_api_key, db_session):
    started = dt.datetime(2026, 7, 20, 0, 0, tzinfo=dt.UTC)
    db_session.add(
        JobRun(
            task_name="mops_ingest",
            status="failure",
            trigger_mode="manual",
            started_at=started,
            finished_at=started + dt.timedelta(seconds=5),
            detail="TWSE OpenAPI 逾時",
        )
    )
    db_session.commit()

    response = client.get("/api/v1/admin/jobs", headers={"X-API-Key": admin_api_key})
    assert response.status_code == 200
    job = next(j for j in response.json() if j["id"] == "mops_ingest")
    assert job["last_run"]["status"] == "failure"
    assert job["last_run"]["trigger_mode"] == "manual"
    assert job["last_run"]["detail"] == "TWSE OpenAPI 逾時"


def test_list_jobs_requires_admin_scope(client, read_api_key):
    response = client.get("/api/v1/admin/jobs", headers={"X-API-Key": read_api_key})
    assert response.status_code == 403


def test_list_jobs_accepts_session_login_without_api_key(client, admin_user):
    """REQ_014：/admin 頁面改走 session 登入後，不帶 X-API-Key 也應能查詢排程狀態。"""
    username, password = admin_user
    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200

    response = client.get("/api/v1/admin/jobs")  # 不帶 X-API-Key，僅靠 session cookie
    assert response.status_code == 200
    assert {job["id"] for job in response.json()} == EXPECTED_TASKS


def test_list_jobs_rejects_when_neither_session_nor_api_key(client):
    response = client.get("/api/v1/admin/jobs")
    assert response.status_code == 401


def test_trigger_ingest_accepts_session_login_without_api_key(client, admin_user, db_session):
    username, password = admin_user
    client.post("/api/v1/auth/login", json={"username": username, "password": password})

    response = client.post("/api/v1/admin/ingest/trigger", json={"task": "model_retrain"})
    assert response.status_code == 202

    log = db_session.execute(
        select(AuditLog).where(AuditLog.action == "admin.ingest.trigger.model_retrain")
    ).scalar_one()
    assert log.api_key_id is None
    assert log.detail["auth_method"] == "session"
