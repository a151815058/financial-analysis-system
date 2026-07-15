"""排程任務之真實擷取邏輯（REQ_008/REQ_011）。取代 app/main.py 原本只記 log 的佔位函式。

僅涵蓋 3 個資料擷取任務（mops_ingest/sec_edgar_ingest/price_ingest）；weekly_predict/
model_retrain/weekly_backtest 三個模型類任務仍維持 app/main.py 之 stub，不在本次範圍。
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable

from sqlalchemy import select

from app.db_models import Company, JobRun
from app.db_session import SessionLocal
from app.ingestion import alpha_vantage_client, mops_client, sec_edgar_client, twse_price_client
from app.ingestion.normalizer import upsert_financial_report, upsert_price_point

logger = logging.getLogger(__name__)


def _record_job_run(
    task_name: str, status: str, trigger_mode: str, started_at: dt.datetime, detail: str | None
) -> None:
    """REQ_013：將任務最新一次執行結果 upsert 至 job_runs（每個任務僅保留最新一筆）。"""
    session = SessionLocal()
    try:
        run = session.get(JobRun, task_name)
        finished_at = dt.datetime.now(dt.UTC)
        if run is None:
            run = JobRun(
                task_name=task_name,
                status=status,
                trigger_mode=trigger_mode,
                started_at=started_at,
                finished_at=finished_at,
                detail=detail,
            )
            session.add(run)
        else:
            run.status = status
            run.trigger_mode = trigger_mode
            run.started_at = started_at
            run.finished_at = finished_at
            run.detail = detail
        session.commit()
    finally:
        session.close()


def track_job(task_name: str, fn: Callable[[], None]) -> Callable[..., None]:
    """REQ_013：包裝任務函式，執行完成後將成功/失敗結果記錄至 job_runs，供 /admin 頁面查詢。

    APScheduler 依排程觸發時不帶參數（trigger_mode 預設 'scheduled'）；手動觸發端點
    （app/routers/admin.py）呼叫時會帶入 kwargs={"trigger_mode": "manual"}。
    """

    def _wrapped(trigger_mode: str = "scheduled") -> None:
        started_at = dt.datetime.now(dt.UTC)
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - 需捕捉以記錄失敗狀態，不讓排程執行緒中斷後失去紀錄
            logger.exception("排程任務 %s 執行失敗", task_name)
            _record_job_run(task_name, "failure", trigger_mode, started_at, str(exc)[:1000])
            return
        _record_job_run(task_name, "success", trigger_mode, started_at, None)

    return _wrapped


def _last_completed_fiscal_quarter(today: dt.date) -> tuple[int, int]:
    """啟發式估算「最近一個已公布」的財報季度：以當前日曆季往前推一季。

    已知限制：TWSE OpenAPI / SEC EDGAR 免費端點僅提供其資料集當下的最新一期（見
    mops_client.py / sec_edgar_client.py 模組說明），若此估算與實際不符，該批次的
    擷取會在 fetch_batch 中被記錄為失敗（批次隔離，不影響其他公司，亦不會靜默寫入錯誤期別資料）。
    """
    quarter = (today.month - 1) // 3 + 1
    if quarter == 1:
        return today.year - 1, 4
    return today.year, quarter - 1


def run_mops_ingest() -> None:
    session = SessionLocal()
    try:
        tickers = list(
            session.execute(select(Company.ticker).where(Company.market == "TW")).scalars().all()
        )
        if not tickers:
            logger.info("mops_ingest：無台股追蹤公司，略過")
            return

        year, quarter = _last_completed_fiscal_quarter(dt.date.today())
        results, failed = mops_client.fetch_batch(tickers, year, quarter)

        for result in results:
            company = session.execute(
                select(Company).where(Company.market == "TW", Company.ticker == result.ticker)
            ).scalar_one()
            upsert_financial_report(
                session,
                company=company,
                fiscal_year=result.fiscal_year,
                fiscal_quarter=result.fiscal_quarter,
                report_date=result.report_date,
                metrics=result.metrics,
                currency="TWD",
                source="MOPS",
                raw_source_ref=result.raw_source_ref,
            )
        session.commit()
        if failed:
            logger.warning("mops_ingest：%d 檔擷取失敗：%s", len(failed), failed)
    finally:
        session.close()


def run_sec_edgar_ingest() -> None:
    session = SessionLocal()
    try:
        companies = (
            session.execute(select(Company).where(Company.market == "US", Company.cik.is_not(None)))
            .scalars()
            .all()
        )
        if not companies:
            logger.info("sec_edgar_ingest：無已登記 CIK 之美股公司，略過")
            return

        year, quarter = _last_completed_fiscal_quarter(dt.date.today())
        pairs = [(c.cik, c.ticker) for c in companies]
        results, failed = sec_edgar_client.fetch_batch(pairs, year, quarter)

        for result in results:
            company = session.execute(
                select(Company).where(Company.market == "US", Company.ticker == result.ticker)
            ).scalar_one()
            upsert_financial_report(
                session,
                company=company,
                fiscal_year=result.fiscal_year,
                fiscal_quarter=result.fiscal_quarter,
                report_date=result.report_date,
                metrics=result.metrics,
                currency="USD",
                source="SEC_EDGAR",
                raw_source_ref=result.raw_source_ref,
            )
        session.commit()
        if failed:
            logger.warning("sec_edgar_ingest：%d 檔擷取失敗：%s", len(failed), failed)
    finally:
        session.close()


def run_price_ingest() -> None:
    session = SessionLocal()
    try:
        companies = session.execute(select(Company)).scalars().all()
        if not companies:
            logger.info("price_ingest：無追蹤公司，略過")
            return

        today = dt.date.today()
        tw_companies = {c.ticker: c for c in companies if c.market == "TW"}
        us_companies = {c.ticker: c for c in companies if c.market == "US"}

        if tw_companies:
            tw_prices, tw_failed = twse_price_client.fetch_batch(
                list(tw_companies), today - dt.timedelta(days=14), today
            )
            for ticker, points in tw_prices.items():
                company = tw_companies[ticker]
                for p in points:
                    upsert_price_point(
                        session,
                        company=company,
                        trade_date=p.trade_date,
                        open_price=p.open,
                        high_price=p.high,
                        low_price=p.low,
                        close_price=p.close,
                        volume=p.volume,
                        source="TWSE",
                    )
            if tw_failed:
                logger.warning("price_ingest（TW）：%d 檔擷取失敗：%s", len(tw_failed), tw_failed)

        if us_companies:
            us_prices, us_failed = alpha_vantage_client.fetch_batch(list(us_companies))
            for ticker, points in us_prices.items():
                company = us_companies[ticker]
                for p in points:
                    upsert_price_point(
                        session,
                        company=company,
                        trade_date=p.trade_date,
                        open_price=p.open,
                        high_price=p.high,
                        low_price=p.low,
                        close_price=p.close,
                        volume=p.volume,
                        source="ALPHA_VANTAGE",
                    )
            if us_failed:
                logger.warning("price_ingest（US）：%d 檔擷取失敗：%s", len(us_failed), us_failed)

        session.commit()
    finally:
        session.close()
