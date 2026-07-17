"""排程任務之真實擷取/預測邏輯（REQ_008/REQ_011/REQ_004~006）。取代 app/main.py 原本只記 log
的佔位函式。

涵蓋 4 個任務：3 個資料擷取（mops_ingest/sec_edgar_ingest/price_ingest）+ 1 個預測
（weekly_predict，本次新增）。model_retrain/weekly_backtest 兩個任務仍維持 app/main.py 之
stub，不在本次範圍——見 run_weekly_predict() 模組說明之「已知簡化」。
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable

import pandas as pd
from sqlalchemy import select

from app.db_models import Company, JobRun, Prediction, PriceHistory
from app.db_session import SessionLocal
from app.ingestion import alpha_vantage_client, mops_client, sec_edgar_client, twse_price_client
from app.ingestion.normalizer import upsert_financial_report, upsert_price_point
from app.prediction import ensemble
from app.prediction import features as prediction_features
from app.prediction.factor_model import FactorModel
from app.prediction.timeseries_model import TimeSeriesModel

logger = logging.getLogger(__name__)

MODEL_VERSION = "v1.0.0"


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
        tickers = list(session.execute(select(Company.ticker).where(Company.market == "TW")).scalars().all())
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


# ---------------------------------------------------------------------------
# weekly_predict（REQ_004/005/006）：財報因子模型 + 時間序列模型 -> 每週預測
# ---------------------------------------------------------------------------
#
# 已知簡化：REQ_004 驗收條件提到模型應「版本化模型檔案」，理想設計是 model_retrain（週日
# 22:00）負責訓練並持久化模型、weekly_predict（週一 01:00）僅載入既有模型做推論。本次僅
# 實作 weekly_predict，尚未實作獨立的模型持久化/版本管理，故採簡化設計：每次執行皆即時
# 重新訓練財報因子模型（不快取），推論與訓練合一。以目前資料量（每次訓練僅需毫秒等級）
# 這不構成效能問題；若日後資料量成長或需要真正的模型版本控管，才需要另外實作
# model_retrain 將訓練與推論拆開。


def _this_week_monday(today: dt.date) -> dt.date:
    return today - dt.timedelta(days=today.weekday())


def _train_pooled_factor_model(session, companies: list[Company]) -> FactorModel | None:
    """跨公司彙總訓練財報因子模型；歷史樣本不足 10 筆（FactorModel 之統計穩定性門檻）時回傳 None。"""
    features_df, labels = prediction_features.build_training_dataset(session, companies)
    if features_df.empty:
        logger.info("weekly_predict：目前累積之財報歷史尚無法算出任何訓練樣本，財報因子模型略過")
        return None
    try:
        return FactorModel().fit(features_df, labels)
    except ValueError as exc:
        logger.info("weekly_predict：財報因子模型訓練樣本不足（%d 筆），略過：%s", len(features_df), exc)
        return None


def _predict_company_timeseries(session, company: Company):
    rows = session.execute(
        select(PriceHistory.trade_date, PriceHistory.close_price)
        .where(PriceHistory.company_id == company.company_id)
        .order_by(PriceHistory.trade_date.asc())
    ).all()
    if not rows:
        return None

    series = pd.Series([float(r[1]) for r in rows], index=pd.DatetimeIndex([r[0] for r in rows]))
    try:
        model = TimeSeriesModel().fit(series)
    except ValueError:
        return None
    return model.predict_next_week()


def _replace_prediction_for_week(
    session, company: Company, base_week_start: dt.date, factor_result, ts_result
) -> None:
    """刪除該公司當週既有預測（若有，如手動重觸發）後寫入最新一筆，維持「每公司每週一筆」語意。"""
    existing = (
        session.execute(
            select(Prediction).where(
                Prediction.company_id == company.company_id,
                Prediction.base_week_start_date == base_week_start,
            )
        )
        .scalars()
        .all()
    )
    for row in existing:
        session.delete(row)
    if existing:
        # 沒有這行，SQLAlchemy flush 預設先送出 INSERT 再送 DELETE，會在資料庫端誤觸
        # (company_id, base_week_start_date, model_version) 唯一鍵衝突；顯式 flush
        # 讓刪除先落地，避免重觸發（如 /admin 手動重跑）時炸掉。
        session.flush()

    if factor_result is not None:
        combined = ensemble.combine(factor_result, ts_result)
        session.add(
            Prediction(
                company_id=company.company_id,
                base_week_start_date=base_week_start,
                direction=combined.direction,
                range_lower_pct=combined.range_lower_pct,
                range_upper_pct=combined.range_upper_pct,
                confidence_score=combined.confidence_score,
                factor_model_direction=combined.factor_model.direction,
                factor_model_range_lower_pct=combined.factor_model.range_lower_pct,
                factor_model_range_upper_pct=combined.factor_model.range_upper_pct,
                timeseries_model_direction=combined.timeseries_model.direction,
                timeseries_model_range_lower_pct=combined.timeseries_model.range_lower_pct,
                timeseries_model_range_upper_pct=combined.timeseries_model.range_upper_pct,
                ensemble_weight_factor=combined.weight_factor,
                ensemble_weight_timeseries=combined.weight_timeseries,
                model_version=MODEL_VERSION,
            )
        )
        return

    # 財報因子模型資料不足時的優雅降級（使用者確認採用）：僅用時間序列模型出預測，
    # factor_model_* 留空、ensemble_weight_factor=0，並於 model_version 加註 -ts-only，
    # 以利前端/稽核區分「真正雙模型融合」與「暫時單模型」兩種預測，不偽裝成完整 REQ_006 融合結果。
    session.add(
        Prediction(
            company_id=company.company_id,
            base_week_start_date=base_week_start,
            direction=ts_result.direction,
            range_lower_pct=ts_result.range_lower_pct,
            range_upper_pct=ts_result.range_upper_pct,
            confidence_score=ts_result.confidence_score,
            factor_model_direction=None,
            factor_model_range_lower_pct=None,
            factor_model_range_upper_pct=None,
            timeseries_model_direction=ts_result.direction,
            timeseries_model_range_lower_pct=ts_result.range_lower_pct,
            timeseries_model_range_upper_pct=ts_result.range_upper_pct,
            ensemble_weight_factor=0.0,
            ensemble_weight_timeseries=1.0,
            model_version=f"{MODEL_VERSION}-ts-only",
        )
    )


def run_weekly_predict() -> None:
    session = SessionLocal()
    try:
        companies = session.execute(select(Company)).scalars().all()
        if not companies:
            logger.info("weekly_predict：無追蹤公司，略過")
            return

        factor_model = _train_pooled_factor_model(session, companies)
        base_week_start = _this_week_monday(dt.date.today())

        produced = 0
        skipped: list[str] = []
        for company in companies:
            label = f"{company.market}:{company.ticker}"
            try:
                ts_result = _predict_company_timeseries(session, company)
                if ts_result is None:
                    skipped.append(f"{label}（股價資料不足，需至少 30 個交易日）")
                    continue

                factor_result = None
                if factor_model is not None:
                    inference_features = prediction_features.build_inference_features(session, company)
                    if inference_features is not None:
                        factor_result = factor_model.predict(inference_features)[0]

                _replace_prediction_for_week(session, company, base_week_start, factor_result, ts_result)
                produced += 1
            except Exception as exc:  # noqa: BLE001 - 批次隔離：單一公司預測失敗不應中斷其餘公司
                logger.exception("weekly_predict：%s 預測失敗", label)
                skipped.append(f"{label}（{exc}）")

        session.commit()
        logger.info(
            "weekly_predict：完成 %d 家公司之預測（財報因子模型%s可用）",
            produced,
            "" if factor_model is not None else "不",
        )
        if skipped:
            logger.warning("weekly_predict：%d 家公司略過：%s", len(skipped), skipped)
    finally:
        session.close()
