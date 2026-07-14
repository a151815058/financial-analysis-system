from __future__ import annotations

import pytest

from app.ingestion.alpha_vantage_client import fetch_batch, fetch_daily_prices
from app.ingestion.http_utils import ExternalSourceError

SAMPLE_PAYLOAD = {
    "Time Series (Daily)": {
        "2026-07-10": {
            "1. open": "100.0",
            "2. high": "105.0",
            "3. low": "99.0",
            "4. close": "103.0",
            "5. volume": "1000000",
        },
        "2026-07-09": {
            "1. open": "98.0",
            "2. high": "101.0",
            "3. low": "97.5",
            "4. close": "100.0",
            "5. volume": "900000",
        },
    }
}


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_fetch_daily_prices_parses_and_sorts_ascending(monkeypatch):
    monkeypatch.setattr(
        "app.ingestion.alpha_vantage_client.get_with_retry", lambda *a, **k: FakeResponse(SAMPLE_PAYLOAD)
    )
    points = fetch_daily_prices("AAPL")
    assert len(points) == 2
    assert points[0].trade_date < points[1].trade_date
    assert points[-1].close == 103.0


def test_fetch_daily_prices_raises_on_rate_limit_note(monkeypatch):
    monkeypatch.setattr(
        "app.ingestion.alpha_vantage_client.get_with_retry",
        lambda *a, **k: FakeResponse({"Note": "rate limit exceeded"}),
    )
    with pytest.raises(ExternalSourceError):
        fetch_daily_prices("AAPL")


def test_fetch_batch_isolates_single_ticker_failure(monkeypatch):
    def fake_get(url, params=None, **kwargs):
        if params["symbol"] == "GOOD":
            return FakeResponse(SAMPLE_PAYLOAD)
        return FakeResponse({"Error Message": "invalid symbol"})

    monkeypatch.setattr("app.ingestion.alpha_vantage_client.get_with_retry", fake_get)

    results, failed = fetch_batch(["GOOD", "BAD"])
    assert "GOOD" in results and len(results["GOOD"]) == 2
    assert len(failed) == 1 and failed[0][0] == "BAD"
