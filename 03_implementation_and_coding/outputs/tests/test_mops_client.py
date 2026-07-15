from __future__ import annotations

import pytest

from app.ingestion.http_utils import ExternalSourceError
from app.ingestion.mops_client import fetch_batch, fetch_quarterly_financials

INCOME_ROW = {
    "年度": "115",
    "季別": "1",
    "公司代號": "2330",
    "公司名稱": "台積電",
    "營業收入": "1134103440.00",
    "營業毛利（毛損）淨額": "751295421.00",
    "本期淨利（淨損）": "572801304.00",
    "基本每股盈餘（元）": "22.08",
}

BALANCE_ROW = {
    "年度": "115",
    "季別": "1",
    "公司代號": "2330",
    "資產總額": "8660949685.00",
    "負債總額": "2728560764.00",
}

PER_ROW = {"Date": "1150714", "Code": "2330", "Name": "台積電", "PEratio": "32.54"}


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _fake_get(income=None, balance=None, per=None):
    income_rows = income if income is not None else [INCOME_ROW]
    balance_rows = balance if balance is not None else [BALANCE_ROW]
    per_rows = per if per is not None else [PER_ROW]

    def _get(url, params=None, **kwargs):
        if "t187ap06" in url:
            return FakeResponse(income_rows)
        if "t187ap07" in url:
            return FakeResponse(balance_rows)
        if "BWIBBU" in url:
            return FakeResponse(per_rows)
        raise AssertionError(f"unexpected url: {url}")

    return _get


def test_fetch_quarterly_financials_merges_three_endpoints(monkeypatch):
    monkeypatch.setattr("app.ingestion.mops_client.get_with_retry", _fake_get())

    result = fetch_quarterly_financials("2330", 2026, 1)

    assert result.ticker == "2330"
    assert result.fiscal_year == 2026 and result.fiscal_quarter == 1
    assert result.metrics.revenue == 1134103440.0
    assert result.metrics.eps == 22.08
    assert result.metrics.gross_margin == pytest.approx(66.253, abs=0.01)
    assert result.metrics.net_margin == pytest.approx(50.503, abs=0.01)
    assert result.metrics.debt_ratio == pytest.approx(31.501, abs=0.01)
    assert result.metrics.pe_ratio == 32.54
    # 現金流量表無免費資料來源，誠實標記為缺漏而非以 0 填補
    assert result.metrics.operating_cash_flow is None


def test_fetch_quarterly_financials_raises_when_company_not_found(monkeypatch):
    monkeypatch.setattr("app.ingestion.mops_client.get_with_retry", _fake_get(income=[]))

    with pytest.raises(ExternalSourceError):
        fetch_quarterly_financials("9999", 2026, 1)


def test_fetch_quarterly_financials_raises_when_period_mismatched(monkeypatch):
    stale_row = {**INCOME_ROW, "季別": "4", "年度": "114"}
    monkeypatch.setattr("app.ingestion.mops_client.get_with_retry", _fake_get(income=[stale_row]))

    with pytest.raises(ExternalSourceError):
        fetch_quarterly_financials("2330", 2026, 1)


def test_fetch_quarterly_financials_tolerates_missing_balance_row(monkeypatch):
    monkeypatch.setattr("app.ingestion.mops_client.get_with_retry", _fake_get(balance=[]))

    result = fetch_quarterly_financials("2330", 2026, 1)
    assert result.metrics.debt_ratio is None
    assert result.metrics.revenue == 1134103440.0


def test_fetch_batch_isolates_single_ticker_failure(monkeypatch):
    def _get(url, params=None, **kwargs):
        if "t187ap06" in url:
            return FakeResponse([INCOME_ROW])
        if "t187ap07" in url:
            return FakeResponse([BALANCE_ROW])
        if "BWIBBU" in url:
            return FakeResponse([PER_ROW])
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.ingestion.mops_client.get_with_retry", _get)

    results, failed = fetch_batch(["2330", "9999"], 2026, 1)

    assert len(results) == 1
    assert results[0].ticker == "2330"
    assert len(failed) == 1
    assert failed[0][0] == "9999"
