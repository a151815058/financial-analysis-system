from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_api_key
from app.db_models import ApiKey, Base
from app.db_session import get_session
from app.main import app


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
def client(db_session):
    def _override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
