"""股價資料擷取（Alpha Vantage）— REQ_002/REQ_005，解決 OI-001。

OI-001 決議：美股/市場資料 API 選定 Alpha Vantage。免費層級速率限制較嚴（每分鐘 5 次），
故 app/scheduler.py 排程需將請求分散於時間軸，而非同時大量呼叫。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.config import settings
from app.ingestion.http_utils import ExternalSourceError, get_with_retry, run_batch_isolated

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"


@dataclass(frozen=True)
class PricePoint:
    trade_date: dt.date
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None


def fetch_daily_prices(ticker: str, outputsize: str = "compact") -> list[PricePoint]:
    """擷取日頻股價。outputsize='compact' 取最近 100 個交易日，'full' 取完整歷史。"""
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "outputsize": outputsize,
        "apikey": settings.alpha_vantage_api_key,
    }
    response = get_with_retry(ALPHA_VANTAGE_BASE_URL, params=params)
    payload = response.json()

    if "Error Message" in payload:
        raise ExternalSourceError(f"Alpha Vantage 錯誤（{ticker}）：{payload['Error Message']}")
    if "Note" in payload:
        # 速率限制訊息，視為可重試之暫時性錯誤
        raise ExternalSourceError(f"Alpha Vantage 速率限制（{ticker}）：{payload['Note']}")

    series = payload.get("Time Series (Daily)")
    if not series:
        raise ExternalSourceError(f"Alpha Vantage 回應缺少 Time Series (Daily)（{ticker}）")

    points: list[PricePoint] = []
    for date_str, values in series.items():
        points.append(
            PricePoint(
                trade_date=dt.date.fromisoformat(date_str),
                open=_safe_float(values.get("1. open")),
                high=_safe_float(values.get("2. high")),
                low=_safe_float(values.get("3. low")),
                close=float(values["4. close"]),
                volume=_safe_int(values.get("5. volume")),
            )
        )
    return sorted(points, key=lambda p: p.trade_date)


def _safe_float(value: str | None) -> float | None:
    return float(value) if value is not None else None


def _safe_int(value: str | None) -> int | None:
    return int(value) if value is not None else None


def fetch_batch(
    tickers: list[str], outputsize: str = "compact"
) -> tuple[dict[str, list[PricePoint]], list[tuple[str, str]]]:
    """批次擷取多檔股價；單一股票失敗不影響其餘股票（與 REQ_001/002 一致的批次隔離原則）。"""
    results: dict[str, list[PricePoint]] = {}

    def _fetch_one(ticker: str) -> None:
        results[ticker] = fetch_daily_prices(ticker, outputsize=outputsize)

    _, failed = run_batch_isolated(tickers, _fetch_one)
    return results, failed
