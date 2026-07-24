"""排程機制（REQ_008）：財報/股價擷取、模型重訓、回測任務之定期觸發。

實際任務函式（ingest_mops/ingest_sec_edgar/...）留待與資料庫協調層整合時實作，
本模組僅負責宣告排程時間與任務註冊介面，供 Phase 04 以整合測試驗證實際觸發行為。
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def build_scheduler(job_functions: dict[str, callable]) -> BackgroundScheduler:
    """依 job_functions 字典註冊排程任務。key 需對應 IngestTriggerRequest.task 之允許值。"""
    scheduler = BackgroundScheduler(timezone="Asia/Taipei")

    if "mops_ingest" in job_functions:
        # 每週一 00:00（台股財報多於平日公布，週一彙整前一週更新）
        scheduler.add_job(
            job_functions["mops_ingest"], CronTrigger(day_of_week="mon", hour=0, minute=0), id="mops_ingest"
        )
    if "sec_edgar_ingest" in job_functions:
        scheduler.add_job(
            job_functions["sec_edgar_ingest"],
            CronTrigger(day_of_week="mon", hour=0, minute=10),
            id="sec_edgar_ingest",
        )
    if "price_ingest" in job_functions:
        # 股價擷取改為每日執行（原僅每週一，財報擷取仍維持每週一次）；
        # Alpha Vantage 免費層級速率限制（5 次/分鐘），排定於財報擷取時段之後
        scheduler.add_job(
            job_functions["price_ingest"],
            CronTrigger(hour=0, minute=30),
            id="price_ingest",
        )
    if "weekly_predict" in job_functions:
        scheduler.add_job(
            job_functions["weekly_predict"],
            CronTrigger(day_of_week="mon", hour=1, minute=0),
            id="weekly_predict",
        )
    if "model_retrain" in job_functions:
        scheduler.add_job(
            job_functions["model_retrain"],
            CronTrigger(day_of_week="sun", hour=22, minute=0),
            id="model_retrain",
        )
    if "weekly_backtest" in job_functions:
        scheduler.add_job(
            job_functions["weekly_backtest"],
            CronTrigger(day_of_week="mon", hour=1, minute=30),
            id="weekly_backtest",
        )

    return scheduler
