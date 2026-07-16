"""管理員排程觸發端點（REQ_008，需 admin scope 之 session 登入或 API Key）。"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit import record as record_audit
from app.auth import AdminAccessContext, require_admin_access
from app.db_models import JobRun
from app.db_session import get_session
from app.routers.companies import _client_ip
from app.schemas import IngestTriggerRequest, IngestTriggerResponse, JobStatusOut

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/ingest/trigger", response_model=IngestTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_ingest(
    payload: IngestTriggerRequest,
    request: Request,
    session: Session = Depends(get_session),
    auth: AdminAccessContext = Depends(require_admin_access),
) -> IngestTriggerResponse:
    # 實際排程任務由 app/scheduler.py 之 APScheduler job store 執行；此端點負責將
    # 對應任務排入該 job store 立即執行一次（不阻塞本次請求），並記錄稽核日誌。
    scheduler = request.app.state.scheduler
    job = scheduler.get_job(payload.task)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"排程中查無任務 {payload.task}")

    scheduler.add_job(
        job.func,
        id=f"{payload.task}_manual_{uuid.uuid4().hex[:8]}",
        next_run_time=dt.datetime.now(),
        kwargs={"trigger_mode": "manual"},
    )

    record_audit(
        session,
        api_key_id=auth.api_key_id,
        action=f"admin.ingest.trigger.{payload.task}",
        result="SUCCESS",
        source_ip=_client_ip(request),
        detail={"task": payload.task, "mode": "manual", "auth_method": auth.method},
    )
    return IngestTriggerResponse(task=payload.task, status="accepted")


@router.get("/jobs", response_model=list[JobStatusOut])
def list_jobs(
    request: Request,
    session: Session = Depends(get_session),
    auth: AdminAccessContext = Depends(require_admin_access),
) -> list[dict]:
    """列出目前排程中的任務、下次執行時間，以及最新一次執行狀況（REQ_013）。"""
    scheduler = request.app.state.scheduler
    jobs = [job for job in scheduler.get_jobs() if "_manual_" not in job.id]
    return [
        {
            "id": job.id,
            "next_run_time": job.next_run_time,
            "last_run": session.get(JobRun, job.id),
        }
        for job in jobs
    ]
