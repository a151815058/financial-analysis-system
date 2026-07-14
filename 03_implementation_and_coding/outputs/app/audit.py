"""事件日誌模組（🔒 構面 2：事件日誌與可歸責性）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db_models import AuditLog


def record(
    session: Session,
    *,
    api_key_id: int | None,
    action: str,
    resource: str | None = None,
    result: str = "SUCCESS",
    source_ip: str | None = None,
    detail: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        api_key_id=api_key_id,
        action=action,
        resource=resource,
        result=result,
        source_ip=source_ip,
        detail=detail,
    )
    session.add(entry)
    session.commit()
    return entry
