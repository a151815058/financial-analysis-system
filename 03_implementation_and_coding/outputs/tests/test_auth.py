from __future__ import annotations

from app.auth import hash_api_key


def test_hash_api_key_is_deterministic():
    assert hash_api_key("abc123") == hash_api_key("abc123")


def test_hash_api_key_differs_for_different_keys():
    assert hash_api_key("abc123") != hash_api_key("abc124")


def test_missing_api_key_and_session_is_anonymous_public_read(client):
    """REQ_015：查詢類端點改為公開瀏覽，不帶任何憑證也應放行。"""
    response = client.get("/api/v1/companies")
    assert response.status_code == 200


def test_invalid_api_key_returns_401(client):
    """主動附上的 X-API-Key 若無效，仍視為錯誤，不會被當成匿名請求靜默放行。"""
    response = client.get("/api/v1/companies", headers={"X-API-Key": "not-a-real-key"})
    assert response.status_code == 401


def test_valid_read_key_returns_200(client, read_api_key):
    response = client.get("/api/v1/companies", headers={"X-API-Key": read_api_key})
    assert response.status_code == 200


def test_read_scope_cannot_call_admin_endpoint(client, read_api_key):
    response = client.post(
        "/api/v1/admin/ingest/trigger",
        json={"task": "mops_ingest"},
        headers={"X-API-Key": read_api_key},
    )
    assert response.status_code == 403


def test_admin_scope_can_call_admin_endpoint(client, admin_api_key):
    response = client.post(
        "/api/v1/admin/ingest/trigger",
        json={"task": "mops_ingest"},
        headers={"X-API-Key": admin_api_key},
    )
    assert response.status_code == 202
