from __future__ import annotations

from app.ingestion.mops_client import fetch_batch, fetch_quarterly_financials, parse_financial_table

SAMPLE_HTML = """
<table>
  <tr><th>項目</th><th>金額</th></tr>
  <tr><td>營業收入合計</td><td>592,000,000</td></tr>
  <tr><td>基本每股盈餘</td><td>9.87</td></tr>
  <tr><td>營業毛利率</td><td>55.2</td></tr>
  <tr><td>稅後淨利率</td><td>40.1</td></tr>
  <tr><td>負債比率</td><td>32.5</td></tr>
  <tr><td>營業活動之淨現金流入</td><td>350,000,000</td></tr>
  <tr><td>本益比</td><td>18.3</td></tr>
</table>
"""

INCOMPLETE_HTML = "<table><tr><th>項目</th><th>金額</th></tr><tr><td>不相關項目</td><td>123</td></tr></table>"


def test_parse_financial_table_extracts_all_known_fields():
    metrics = parse_financial_table(SAMPLE_HTML)
    assert metrics.revenue == 592_000_000
    assert metrics.eps == 9.87
    assert metrics.gross_margin == 55.2
    assert metrics.net_margin == 40.1
    assert metrics.debt_ratio == 32.5
    assert metrics.operating_cash_flow == 350_000_000
    assert metrics.pe_ratio == 18.3


def test_parse_financial_table_missing_fields_stay_none():
    metrics = parse_financial_table(INCOMPLETE_HTML)
    assert metrics.missing_fields() == list(metrics.missing_fields())  # 型別檢查
    assert metrics.revenue is None


def test_fetch_quarterly_financials_uses_parsed_table(monkeypatch):
    class FakeResponse:
        text = SAMPLE_HTML

    monkeypatch.setattr("app.ingestion.mops_client.get_with_retry", lambda *a, **k: FakeResponse())

    result = fetch_quarterly_financials("2330", 2026, 1)
    assert result.ticker == "2330"
    assert result.metrics.revenue == 592_000_000
    assert result.fiscal_year == 2026 and result.fiscal_quarter == 1


def test_fetch_batch_isolates_single_ticker_failure(monkeypatch):
    class FakeResponse:
        def __init__(self, text):
            self.text = text

    responses = {"2330": FakeResponse(SAMPLE_HTML), "9999": FakeResponse(INCOMPLETE_HTML)}

    def fake_get(url, params=None, **kwargs):
        return responses[params["co_id"]]

    monkeypatch.setattr("app.ingestion.mops_client.get_with_retry", fake_get)

    results, failed = fetch_batch(["2330", "9999"], 2026, 1)

    assert len(results) == 1
    assert results[0].ticker == "2330"
    assert len(failed) == 1
    assert failed[0][0] == "9999"
