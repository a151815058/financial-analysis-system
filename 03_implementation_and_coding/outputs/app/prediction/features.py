"""財報因子模型特徵工程（REQ_004）：由財報歷史衍生 YoY/QoQ 特徵，並比對股價算出訓練標籤。

財報因子模型（factor_model.py）本身是通用的統計模型，不認識「財報」這個領域概念；本模組
負責把 `financial_reports`/`price_history` 兩張表轉成 factor_model 看得懂的
(features, weekly_return_pct) 格式，供 app/jobs.py::run_weekly_predict 呼叫。

訓練樣本改採「跨公司彙總（cross-sectional）」而非每家公司各自訓練：財報一季才更新一次，
單一公司要湊到 FactorModel 要求的 10 筆門檻需要 2.5 年以上歷史，彙總全部追蹤公司的財報
可以更快達到統計上可訓練的樣本數，長期而言也更符合分位數迴歸對更大樣本數的統計假設。
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db_models import Company, FinancialReport, PriceHistory
from app.prediction.timeseries_model import TRADING_DAYS_PER_WEEK

FEATURE_COLUMNS = [
    "revenue_yoy",
    "eps_qoq",
    "gross_margin",
    "net_margin",
    "debt_ratio",
    "operating_cash_flow_yoy",
    "pe_ratio",
]


def _pct_change(curr: float | None, prev: float | None) -> float | None:
    if curr is None or prev is None or float(prev) == 0:
        return None
    return (float(curr) - float(prev)) / abs(float(prev)) * 100


def _prior_reports(
    by_period: dict[tuple[int, int], FinancialReport], report: FinancialReport
) -> tuple[FinancialReport | None, FinancialReport | None]:
    prior_year = by_period.get((report.fiscal_year - 1, report.fiscal_quarter))
    if report.fiscal_quarter == 1:
        prior_quarter = by_period.get((report.fiscal_year - 1, 4))
    else:
        prior_quarter = by_period.get((report.fiscal_year, report.fiscal_quarter - 1))
    return prior_year, prior_quarter


def compute_derived_features(
    report: FinancialReport,
    prior_year_report: FinancialReport | None,
    prior_quarter_report: FinancialReport | None,
) -> dict[str, float] | None:
    """單筆財報 -> 衍生特徵 dict；缺乏足夠前期資料（無法算 YoY/QoQ）或核心欄位為空時回傳 None。"""
    revenue_yoy = _pct_change(report.revenue, prior_year_report.revenue if prior_year_report else None)
    eps_qoq = _pct_change(report.eps, prior_quarter_report.eps if prior_quarter_report else None)
    ocf_yoy = _pct_change(
        report.operating_cash_flow, prior_year_report.operating_cash_flow if prior_year_report else None
    )
    if revenue_yoy is None or eps_qoq is None or ocf_yoy is None:
        return None
    if None in (report.gross_margin, report.net_margin, report.debt_ratio, report.pe_ratio):
        return None

    return {
        "revenue_yoy": revenue_yoy,
        "eps_qoq": eps_qoq,
        "gross_margin": float(report.gross_margin),
        "net_margin": float(report.net_margin),
        "debt_ratio": float(report.debt_ratio),
        "operating_cash_flow_yoy": ocf_yoy,
        "pe_ratio": float(report.pe_ratio),
    }


def compute_future_weekly_return_pct(
    session: Session, company_id: int, report_date: dt.date, trading_days: int = TRADING_DAYS_PER_WEEK
) -> float | None:
    """財報公布日起算，未來第 `trading_days` 個交易日的報酬率（訓練標籤）；資料不足回傳 None。"""
    rows = session.execute(
        select(PriceHistory.trade_date, PriceHistory.close_price)
        .where(PriceHistory.company_id == company_id, PriceHistory.trade_date >= report_date)
        .order_by(PriceHistory.trade_date.asc())
        .limit(trading_days + 1)
    ).all()
    if len(rows) < trading_days + 1:
        return None

    base_price = float(rows[0][1])
    future_price = float(rows[trading_days][1])
    if base_price == 0:
        return None
    return (future_price - base_price) / base_price * 100


def _company_reports_by_period(
    session: Session, company_id: int
) -> tuple[list[FinancialReport], dict[tuple[int, int], FinancialReport]]:
    reports = (
        session.execute(
            select(FinancialReport)
            .where(FinancialReport.company_id == company_id, FinancialReport.is_latest_version.is_(True))
            .order_by(FinancialReport.fiscal_year.asc(), FinancialReport.fiscal_quarter.asc())
        )
        .scalars()
        .all()
    )
    by_period = {(r.fiscal_year, r.fiscal_quarter): r for r in reports}
    return list(reports), by_period


def build_training_dataset(session: Session, companies: list[Company]) -> tuple[pd.DataFrame, pd.Series]:
    """跨公司彙總歷史財報，組成 FactorModel.fit() 可用的 (features, weekly_return_pct)。"""
    feature_rows: list[dict[str, float]] = []
    labels: list[float] = []

    for company in companies:
        reports, by_period = _company_reports_by_period(session, company.company_id)
        for report in reports:
            prior_year, prior_quarter = _prior_reports(by_period, report)
            feat = compute_derived_features(report, prior_year, prior_quarter)
            if feat is None:
                continue
            label = compute_future_weekly_return_pct(session, company.company_id, report.report_date)
            if label is None:
                continue
            feature_rows.append(feat)
            labels.append(label)

    if not feature_rows:
        return pd.DataFrame(columns=FEATURE_COLUMNS), pd.Series(dtype=float)
    return pd.DataFrame(feature_rows, columns=FEATURE_COLUMNS), pd.Series(labels)


def build_inference_features(session: Session, company: Company) -> pd.DataFrame | None:
    """單一公司最新一筆財報 -> 一列特徵，供 FactorModel.predict() 對「這一週」做推論。"""
    reports, by_period = _company_reports_by_period(session, company.company_id)
    if not reports:
        return None

    latest = reports[-1]
    prior_year, prior_quarter = _prior_reports(by_period, latest)
    feat = compute_derived_features(latest, prior_year, prior_quarter)
    if feat is None:
        return None
    return pd.DataFrame([feat], columns=FEATURE_COLUMNS)
