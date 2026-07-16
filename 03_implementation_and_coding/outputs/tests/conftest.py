from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import db_session as db_session_module
from app.auth import hash_api_key, hash_password
from app.db_models import AdminUser, ApiKey, Base
from app.db_session import get_session
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _dispose_default_engine():
    """app.main 啟動時會透過 lifespan 呼叫 init_db()，使用 app/db_session.py 的預設
    模組級 engine（非測試用 in-memory engine）。測試全部結束後釋放其連線，避免
    ResourceWarning: unclosed database。"""
    yield
    db_session_module.engine.dispose()


@pytest.fixture()
def db_session():
    # StaticPool 讓 in-memory SQLite 在整個測試期間共用同一連線，
    # 否則每次 checkout 會拿到全新的空白 in-memory 資料庫。
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def read_api_key(db_session) -> str:
    raw_key = "test-read-key-123456"
    db_session.add(ApiKey(key_hash=hash_api_key(raw_key), owner="tester", scope="read"))
    db_session.commit()
    return raw_key


@pytest.fixture()
def admin_api_key(db_session) -> str:
    raw_key = "test-admin-key-123456"
    db_session.add(ApiKey(key_hash=hash_api_key(raw_key), owner="tester-admin", scope="admin"))
    db_session.commit()
    return raw_key


@pytest.fixture()
def admin_user(db_session) -> tuple[str, str]:
    """REQ_014：/admin 帳號密碼登入測試用之後台帳號，回傳 (username, plaintext_secret)。"""
    username = "tester-admin-user"
    plaintext_secret = "correct-horse-battery-staple"
    db_session.add(AdminUser(username=username, password_hash=hash_password(plaintext_secret)))
    db_session.commit()
    return username, plaintext_secret


@pytest.fixture()
def client(db_session):
    def _override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
