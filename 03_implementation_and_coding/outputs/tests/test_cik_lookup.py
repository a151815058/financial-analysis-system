"""REQ_011：美股新增公司時之 SEC ticker→CIK 自動查詢。REQ_012：ticker/名稱模糊搜尋。"""

from __future__ import annotations

from app.ingestion.http_utils import ExternalSourceError
from app.ingestion.sec_edgar_client import lookup_cik, search_companies


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


TICKERS_JSON = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp."},
}


def _reset_cache(monkeypatch):
    monkeypatch.setattr("app.ingestion.sec_edgar_client._ticker_directory_cache", None)


def test_lookup_cik_finds_known_ticker(monkeypatch):
    _reset_cache(monkeypatch)
    monkeypatch.setattr(
        "app.ingestion.sec_edgar_client.get_with_retry", lambda *a, **k: FakeResponse(TICKERS_JSON)
    )
    assert lookup_cik("AAPL") == "0000320193"
    assert lookup_cik("msft") == "0000789019"  # 大小寫不敏感


def test_lookup_cik_returns_none_for_unknown_ticker(monkeypatch):
    _reset_cache(monkeypatch)
    monkeypatch.setattr(
        "app.ingestion.sec_edgar_client.get_with_retry", lambda *a, **k: FakeResponse(TICKERS_JSON)
    )
    assert lookup_cik("NOSUCHTICKER") is None


def test_lookup_cik_returns_none_on_network_failure(monkeypatch):
    _reset_cache(monkeypatch)

    def _raise(*a, **k):
        raise ExternalSourceError("boom")

    monkeypatch.setattr("app.ingestion.sec_edgar_client.get_with_retry", _raise)
    assert lookup_cik("AAPL") is None


def test_lookup_cik_caches_after_first_successful_call(monkeypatch):
    _reset_cache(monkeypatch)
    calls = []

    def _get(*a, **k):
        calls.append(1)
        return FakeResponse(TICKERS_JSON)

    monkeypatch.setattr("app.ingestion.sec_edgar_client.get_with_retry", _get)
    lookup_cik("AAPL")
    lookup_cik("MSFT")
    assert len(calls) == 1


def test_search_companies_matches_by_ticker_substring(monkeypatch):
    _reset_cache(monkeypatch)
    monkeypatch.setattr(
        "app.ingestion.sec_edgar_client.get_with_retry", lambda *a, **k: FakeResponse(TICKERS_JSON)
    )
    results = search_companies("APL")
    assert [r["ticker"] for r in results] == ["AAPL"]
    assert results[0]["market"] == "US"


def test_search_companies_matches_by_name_substring_case_insensitive(monkeypatch):
    _reset_cache(monkeypatch)
    monkeypatch.setattr(
        "app.ingestion.sec_edgar_client.get_with_retry", lambda *a, **k: FakeResponse(TICKERS_JSON)
    )
    results = search_companies("microsoft")
    assert [r["ticker"] for r in results] == ["MSFT"]


def test_search_companies_returns_empty_list_for_blank_query(monkeypatch):
    _reset_cache(monkeypatch)
    assert search_companies("   ") == []


def test_search_companies_returns_empty_list_on_network_failure(monkeypatch):
    _reset_cache(monkeypatch)

    def _raise(*a, **k):
        raise ExternalSourceError("boom")

    monkeypatch.setattr("app.ingestion.sec_edgar_client.get_with_retry", _raise)
    assert search_companies("AAPL") == []
