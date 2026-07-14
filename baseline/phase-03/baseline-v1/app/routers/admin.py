"""管理員排程觸發端點（REQ_008，需 admin scope）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.audit import record as record_audit
from app.auth import AuthContext, require_admin_scope
from app.db_session import get_session
from app.routers.companies import _client_ip
from app.schemas import IngestTriggerRequest, IngestTriggerResponse

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/ingest/trigger", response_model=IngestTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_ingest(
    payload: IngestTriggerRequest,
    request: Request,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_admin_scope),
) -> IngestTriggerResponse:
    # 實際排程任務由 app/scheduler.py 之 APScheduler job store 執行；此端點僅負責
    # 將任務排入佇列並記錄稽核日誌，符合 Generator「只執行、不擴大範圍」原則。
    record_audit(
        session,
        api_key_id=auth.api_key_id,
        action=f"admin.ingest.trigger.{payload.task}",
        result="SUCCESS",
        source_ip=_client_ip(request),
        detail={"task": payload.task},
    )
    return IngestTriggerResponse(task=payload.task, status="accepted")
