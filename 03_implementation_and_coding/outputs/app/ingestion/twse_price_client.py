"""台股股價資料擷取（證券交易所 TWSE STOCK_DAY）— REQ_005，新增台股股價來源。

TWSE STOCK_DAY 端點以「月」為查詢單位（date 參數任一日期即可取得該整月資料），
故擷取歷史區間需逐月請求；此設計與 mops_client 之逐季查詢、alpha_vantage_client
之逐檔查詢一致。對外部公開服務僅標示 User-Agent 供對方識別來源，並沿用 settings
之逾時/重試設定，不額外提高頻率造成負擔（見 formal_requirements.md 業務規則：
僅使用公開合法資料來源，不得違反其使用條款）。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.config import settings
from app.ingestion.http_utils import ExternalSourceError, get_with_retry, run_batch_isolated

TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
_NO_DATA_MARKERS = ("查詢無資料", "沒有符合條件的資料")


@dataclass(frozen=True)
class PricePoint:
    trade_date: dt.date
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None


def _roc_to_date(roc_date_str: str) -> dt.date:
    """轉換民國年日期字串（如 '114/07/01'）為西元日期。"""
    year_roc, month, day = roc_date_str.split("/")
    return dt.date(int(year_roc) + 1911, int(month), int(day))


def _parse_number(value: str) -> float | None:
    cleaned = value.replace(",", "").strip()
    if not cleaned or cleaned in {"--", "-", "X"}:
        return None
    return float(cleaned)


def fetch_monthly_prices(ticker: str, year: int, month: int) -> list[PricePoint]:
    """擷取單一股票單一月份之日頻股價。TWSE STOCK_DAY 以月為查詢單位。"""
    query_date = dt.date(year, month, 1).strftime("%Y%m%d")
    params = {"response": "json", "date": query_date, "stockNo": ticker}
    headers = {"User-Agent": settings.sec_edgar_user_agent}

    response = get_with_retry(TWSE_STOCK_DAY_URL, params=params, headers=headers)
    payload = response.json()

    stat = payload.get("stat", "")
    if stat != "OK":
        if any(marker in stat for marker in _NO_DATA_MARKERS) or not payload.get("data"):
            return []  # 該月無交易資料（如未來月份、上市前月份）
        raise ExternalSourceError(f"TWSE STOCK_DAY 錯誤（{ticker}, {year}-{month:02d}）：{stat}")

    points: list[PricePoint] = []
    for row in payload["data"]:
        date_str, volume_str, _turnover, open_str, high_str, low_str, close_str, *_rest = row
        close = _parse_number(close_str)
        if close is None:
            continue
        volume_value = _parse_number(volume_str)
        points.append(
            PricePoint(
                trade_date=_roc_to_date(date_str),
                open=_parse_number(open_str),
                high=_parse_number(high_str),
                low=_parse_number(low_str),
                close=close,
                volume=int(volume_value) if volume_value is not None else None,
            )
        )
    return sorted(points, key=lambda p: p.trade_date)


def fetch_price_range(ticker: str, start_date: dt.date, end_date: dt.date) -> list[PricePoint]:
    """擷取指定日期區間之股價（逐月呼叫 fetch_monthly_prices 後篩選區間並排序）。"""
    if start_date > end_date:
        raise ValueError("start_date 不可晚於 end_date")

    points: list[PricePoint] = []
    year, month = start_date.year, start_date.month
    while (year, month) <= (end_date.year, end_date.month):
        points.extend(fetch_monthly_prices(ticker, year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1

    return sorted(
        (p for p in points if start_date <= p.trade_date <= end_date),
        key=lambda p: p.trade_date,
    )


def fetch_batch(
    tickers: list[str], start_date: dt.date, end_date: dt.date
) -> tuple[dict[str, list[PricePoint]], list[tuple[str, str]]]:
    """批次擷取多檔股價；單一股票失敗不影響其餘股票（與 mops/alpha_vantage 一致的批次隔離原則）。"""
    results: dict[str, list[PricePoint]] = {}

    def _fetch_one(ticker: str) -> None:
        results[ticker] = fetch_price_range(ticker, start_date, end_date)

    _, failed = run_batch_isolated(tickers, _fetch_one)
    return results, failed
