"""/admin 頁面帳號密碼登入（REQ_014，session cookie）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password, require_session_login, verify_password
from app.db_models import AdminUser
from app.db_session import get_session
from app.schemas import ChangePasswordRequest, LoginRequest, MeOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=MeOut)
def login(payload: LoginRequest, request: Request, session: Session = Depends(get_session)) -> MeOut:
    user = session.execute(
        select(AdminUser).where(AdminUser.username == payload.username)
    ).scalar_one_or_none()

    # 帳號不存在與密碼錯誤一律回同一句訊息，不洩漏帳號是否存在（比照 API Key 驗證作法）。
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="帳號或密碼錯誤")

    request.session["admin_user_id"] = user.user_id
    request.session["username"] = user.username
    return MeOut(username=user.username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> None:
    request.session.clear()


@router.get("/me", response_model=MeOut)
def me(request: Request) -> MeOut:
    username = request.session.get("username")
    if not username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="尚未登入")
    return MeOut(username=username)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    session: Session = Depends(get_session),
    admin_user_id: int = Depends(require_session_login),
) -> None:
    user = session.get(AdminUser, admin_user_id)
    if user is None or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="現有密碼錯誤")

    user.password_hash = hash_password(payload.new_password)
    session.commit()
