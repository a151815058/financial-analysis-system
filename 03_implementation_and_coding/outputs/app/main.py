"""FastAPI 應用進入點。對應 02_system_design/outputs/api_spec.md。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db_session import init_db
from app.jobs import run_mops_ingest, run_price_ingest, run_sec_edgar_ingest
from app.routers import admin, companies, predictions
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
        "mops_ingest": run_mops_ingest,
        "sec_edgar_ingest": run_sec_edgar_ingest,
        "price_ingest": run_price_ingest,
        # 模型類任務仍待與預測/回測管線整合，維持佔位函式（不在 REQ_011 範圍）
        "weekly_predict": _stub_job("weekly_predict"),
        "model_retrain": _stub_job("model_retrain"),
        "weekly_backtest": _stub_job("weekly_backtest"),
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

app.include_router(companies.router)
app.include_router(predictions.router)
app.include_router(admin.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "disclaimer": DISCLAIMER}


@app.get("/dashboard", tags=["system"])
def dashboard() -> FileResponse:
    """內部分析儀表板（文字 + 圖表），呼叫既有 API 端點呈現財務指標/股價/預測結果。"""
    return FileResponse(STATIC_DIR / "dashboard.html")
