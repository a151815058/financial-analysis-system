"""FastAPI 應用進入點。對應 02_system_design/outputs/api_spec.md。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db_session import init_db
from app.routers import admin, companies, predictions

DISCLAIMER = "本系統輸出僅供分析參考，不構成投資建議。過往預測準確率不代表未來績效。"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="各公司各季度財務分析與股價預測系統 API",
    version="0.1.0",
    description=DISCLAIMER,
    lifespan=lifespan,
)

app.include_router(companies.router)
app.include_router(predictions.router)
app.include_router(admin.router)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "disclaimer": DISCLAIMER}
