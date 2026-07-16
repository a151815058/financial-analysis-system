"""API Key 驗證與 scope 檢查（REQ_SEC_001，🔒 構面 1/4：存取控制、識別與鑑別）。
REQ_014：另外新增 /admin 頁面帳號密碼登入用之 session 驗證與密碼雜湊。

安全設計：
- API Key 明文只在使用者建立當下出現一次，資料庫僅存 SHA-256 雜湊值。
- 密碼明文從不落地儲存，資料庫僅存 bcrypt 雜湊值。
- 驗證失敗一律回傳 401/403，不洩漏金鑰/帳號是否存在等內部細節。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

import bcrypt
from fastapi import Depends, Header, HTTPException, Request, status
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


# ---------------------------------------------------------------------------
# REQ_014：/admin 頁面帳號密碼登入（session cookie）
# ---------------------------------------------------------------------------


def hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(raw_password.encode("utf-8"), password_hash.encode("utf-8"))


def require_session_login(request: Request) -> int:
    """僅接受 session 登入（給登出、變更密碼等帳號本人操作使用，不接受 API Key）。"""
    admin_user_id = request.session.get("admin_user_id")
    if not admin_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="請先登入")
    return admin_user_id


@dataclass(frozen=True)
class AdminAccessContext:
    method: Literal["session", "apikey"]
    api_key_id: int | None
    admin_user_id: int | None


def require_admin_access(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: Session = Depends(get_session),
) -> AdminAccessContext:
    """給 /api/v1/admin/* 端點用：session 登入或 admin scope 之 API Key 擇一即可。

    /admin 頁面本身（REQ_014）改用帳號密碼登入的 session cookie；既有以 API Key 呼叫這些
    端點的程式化/腳本呼叫端（REQ_008 原始設計）不受影響，仍可繼續使用。
    """
    admin_user_id = request.session.get("admin_user_id")
    if admin_user_id:
        return AdminAccessContext(method="session", api_key_id=None, admin_user_id=admin_user_id)

    if x_api_key:
        # 有帶 API Key 時，沿用既有 require_api_key/require_admin_scope 之 401/403 語意：
        # 金鑰本身無效 → 401；金鑰有效但非 admin scope → 403。
        key_hash = hash_api_key(x_api_key)
        record = session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        ).scalar_one_or_none()
        if record is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")
        if record.scope != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin scope required")
        return AdminAccessContext(method="apikey", api_key_id=record.api_key_id, admin_user_id=None)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="需登入（/admin 頁面）或提供 admin scope 之 API Key",
    )


# ---------------------------------------------------------------------------
# REQ_015：/dashboard 查詢類端點改為公開瀏覽（不需登入/API Key），新增公司等寫入
# 操作仍需登入或 admin scope 之 API Key（見 require_admin_access）。
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OptionalReadAccessContext:
    method: Literal["session", "apikey", "anonymous"]
    api_key_id: int | None
    admin_user_id: int | None


def optional_read_access(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: Session = Depends(get_session),
) -> OptionalReadAccessContext:
    """給 /dashboard 所呼叫的查詢端點用：不要求任何驗證即可存取（公開瀏覽）。

    若請求仍附帶 session 登入或 X-API-Key，會辨識並記錄在稽核日誌的 auth_method
    （沿用既有 API Key 呼叫端的可歸責性）；但兩者皆缺席時不再視為錯誤，一律視為
    匿名瀏覽放行。唯獨主動附上的 X-API-Key 若無效/已撤銷仍視為錯誤（401），避免
    誤植金鑰卻被靜默當成匿名請求而難以察覺。
    """
    admin_user_id = request.session.get("admin_user_id")
    if admin_user_id:
        return OptionalReadAccessContext(method="session", api_key_id=None, admin_user_id=admin_user_id)

    if x_api_key:
        key_hash = hash_api_key(x_api_key)
        record = session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        ).scalar_one_or_none()
        if record is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")
        return OptionalReadAccessContext(method="apikey", api_key_id=record.api_key_id, admin_user_id=None)

    return OptionalReadAccessContext(method="anonymous", api_key_id=None, admin_user_id=None)
