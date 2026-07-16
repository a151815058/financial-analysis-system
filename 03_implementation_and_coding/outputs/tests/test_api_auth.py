"""REQ_014：/admin 頁面帳號密碼登入（session cookie）。"""

from __future__ import annotations

from app.auth import hash_password, verify_password


def test_hash_password_roundtrip():
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed)
    assert not verify_password("wrong-password", hashed)


def test_login_success_returns_username_and_sets_session(client, admin_user):
    username, password = admin_user
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    assert response.json() == {"username": username}


def test_login_wrong_password_returns_401(client, admin_user):
    username, _ = admin_user
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "帳號或密碼錯誤"


def test_login_unknown_username_returns_same_message(client, admin_user):
    response = client.post(
        "/api/v1/auth/login", json={"username": "no-such-user", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "帳號或密碼錯誤"


def test_me_requires_login(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_after_login_returns_username(client, admin_user):
    username, password = admin_user
    client.post("/api/v1/auth/login", json={"username": username, "password": password})
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json() == {"username": username}


def test_logout_clears_session(client, admin_user):
    username, password = admin_user
    client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert client.get("/api/v1/auth/me").status_code == 200

    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_change_password_requires_login(client):
    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "x", "new_password": "new-password-123"},
    )
    assert response.status_code == 401


def test_change_password_wrong_current_password_returns_401(client, admin_user):
    username, password = admin_user
    client.post("/api/v1/auth/login", json={"username": username, "password": password})
    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "not-the-real-password", "new_password": "new-password-123"},
    )
    assert response.status_code == 401


def test_change_password_success_allows_login_with_new_password(client, admin_user):
    username, password = admin_user
    client.post("/api/v1/auth/login", json={"username": username, "password": password})
    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": password, "new_password": "brand-new-password-456"},
    )
    assert response.status_code == 204

    client.post("/api/v1/auth/logout")
    old_login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "brand-new-password-456"}
    )
    assert new_login.status_code == 200
