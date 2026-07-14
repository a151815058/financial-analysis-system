"""API Key 驗證與 scope 檢查（REQ_SEC_001，🔒 構面 1/4：存取控制、識別與鑑別）。

安全設計：
- API Key 明文只在使用者建立當下出現一次，資料庫僅存 SHA-256 雜湊值。
- 驗證失敗一律回傳 401/403，不洩漏金鑰是否存在等內部細節。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db_models import ApiKey
from app.db_session import get_session


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthContext:
    api_key_id: int
    scope: str


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: Session = Depends(get_session),
) -> AuthContext:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")

    key_hash = hash_api_key(x_api_key)
    record = session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
    ).scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")

    return AuthContext(api_key_id=record.api_key_id, scope=record.scope)


def require_admin_scope(auth: AuthContext = Depends(require_api_key)) -> AuthContext:
    if auth.scope != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin scope required")
    return auth
