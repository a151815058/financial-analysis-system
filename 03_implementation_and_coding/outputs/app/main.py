"""FastAPI 應用進入點。對應 02_system_design/outputs/api_spec.md。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db_session import init_db
from app.jobs import run_mops_ingest, run_price_ingest, run_sec_edgar_ingest, run_weekly_predict, track_job
from app.routers import admin, auth, companies, predictions
from app.scheduler import build_scheduler

STATIC_DIR = Path(__file__).parent / "static"

DISCLAIMER = "本系統輸出僅供分析參考，不構成投資建議。過往預測準確率不代表未來績效。"

logger = logging.getLogger(__name__)


def _stub_job(task_name: str):
    """佔位任務函式：實際擷取/訓練/回測邏輯待與資料庫協調層整合時實作（見 scheduler.py 模組說明）。"""

    def _run() -> None:
        logger.warning("排程任務 %s 已觸發，但實作尚未串接資料庫協調層，本次僅記錄未執行", task_name)

    return _run


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    job_functions = {
        # REQ_011：真實擷取邏輯（app/jobs.py），會依 companies 表實際內容打外部 API
        # REQ_013：以 track_job 包裝，執行結果 upsert 至 job_runs，供 /admin 頁面查詢
        "mops_ingest": track_job("mops_ingest", run_mops_ingest),
        "sec_edgar_ingest": track_job("sec_edgar_ingest", run_sec_edgar_ingest),
        "price_ingest": track_job("price_ingest", run_price_ingest),
        # REQ_004/005/006：財報因子模型 + 時間序列模型 -> 每週預測（見 app/jobs.py 模組說明之已知簡化）
        "weekly_predict": track_job("weekly_predict", run_weekly_predict),
        # model_retrain/weekly_backtest 仍待實作，維持佔位函式
        "model_retrain": track_job("model_retrain", _stub_job("model_retrain")),
        "weekly_backtest": track_job("weekly_backtest", _stub_job("weekly_backtest")),
    }
    scheduler = build_scheduler(job_functions)
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="各公司各季度財務分析與股價預測系統 API",
    version="0.1.0",
    description=DISCLAIMER,
    lifespan=lifespan,
)

# REQ_014：/admin 頁面帳號密碼登入用之簽章 session cookie（Starlette 內建，免建 session 資料表）。
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie="fas_admin_session",
    max_age=8 * 3600,
    https_only=settings.session_cookie_secure,
    same_site="lax",
)

app.include_router(companies.router)
app.include_router(predictions.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", tags=["system"], include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "disclaimer": DISCLAIMER}


@app.get("/dashboard", tags=["system"])
def dashboard() -> FileResponse:
    """內部分析儀表板（文字 + 圖表），呼叫既有 API 端點呈現財務指標/股價/預測結果。"""
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/admin", tags=["system"])
def admin_page() -> FileResponse:
    """排程執行狀況頁面（REQ_013），與 /dashboard 分開。REQ_014：頁面本身改為帳號密碼登入
    （session cookie），頁面靜態檔案不需驗證，驗證發生在頁面對 /api/v1/auth、/api/v1/admin 的呼叫。
    """
    return FileResponse(STATIC_DIR / "admin.html")
