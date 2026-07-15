from __future__ import annotations

import datetime as dt

import pytest

from app.ingestion.http_utils import ExternalSourceError
from app.ingestion.twse_price_client import fetch_batch, fetch_monthly_prices, fetch_price_range

SAMPLE_PAYLOAD = {
    "stat": "OK",
    "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數"],
    "data": [
        ["115/07/02", "24,922,111", "10,395,338,336", "417.00", "420.00", "415.00", "417.50", "-1.00", "23,124"],
        ["115/07/01", "18,331,204", "7,650,112,900", "415.00", "418.00", "413.50", "418.00", "+2.00", "19,882"],
    ],
}

NO_DATA_PAYLOAD = {"stat": "很抱歉，沒有符合條件的資料!"}


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_fetch_monthly_prices_parses_roc_date_and_sorts_ascending(monkeypatch):
    monkeypatch.setattr(
        "app.ingestion.twse_price_client.get_with_retry", lambda *a, **k: FakeResponse(SAMPLE_PAYLOAD)
    )
    points = fetch_monthly_prices("2330", 2026, 7)
    assert len(points) == 2
    assert points[0].trade_date == dt.date(2026, 7, 1)
    assert points[1].trade_date == dt.date(2026, 7, 2)
    assert points[0].close == 418.0
    assert points[0].volume == 18331204


def test_fetch_monthly_prices_returns_empty_on_no_data(monkeypatch):
    monkeypatch.setattr(
        "app.ingestion.twse_price_client.get_with_retry", lambda *a, **k: FakeResponse(NO_DATA_PAYLOAD)
    )
    assert fetch_monthly_prices("2330", 1990, 1) == []


def test_fetch_monthly_prices_raises_on_unexpected_error_stat(monkeypatch):
    monkeypatch.setattr(
        "app.ingestion.twse_price_client.get_with_retry",
        lambda *a, **k: FakeResponse({"stat": "查詢過於頻繁，請稍後再試", "data": [["x"]]}),
    )
    with pytest.raises(ExternalSourceError):
        fetch_monthly_prices("2330", 2026, 7)


def test_fetch_price_range_filters_to_requested_window(monkeypatch):
    monkeypatch.setattr(
        "app.ingestion.twse_price_client.get_with_retry", lambda *a, **k: FakeResponse(SAMPLE_PAYLOAD)
    )
    points = fetch_price_range("2330", dt.date(2026, 7, 2), dt.date(2026, 7, 2))
    assert len(points) == 1
    assert points[0].trade_date == dt.date(2026, 7, 2)


def test_fetch_batch_isolates_single_ticker_failure(monkeypatch):
    def fake_get(url, params=None, **kwargs):
        if params["stockNo"] == "GOOD":
            return FakeResponse(SAMPLE_PAYLOAD)
        return FakeResponse({"stat": "查詢過於頻繁，請稍後再試", "data": [["x"]]})

    monkeypatch.setattr("app.ingestion.twse_price_client.get_with_retry", fake_get)

    results, failed = fetch_batch(["GOOD", "BAD"], dt.date(2026, 7, 1), dt.date(2026, 7, 31))
    assert "GOOD" in results and len(results["GOOD"]) == 2
    assert len(failed) == 1 and failed[0][0] == "BAD"
