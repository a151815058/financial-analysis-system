"""驗證 OI-002 之解決方案：us-gaap 標籤備援對應邏輯。"""

from __future__ import annotations

import pytest

from app.ingestion.sec_edgar_client import fetch_batch, parse_company_facts


def _facts(tag: str, fy: int, fp: str, val: float) -> dict:
    return {"facts": {"us-gaap": {tag: {"units": {"USD": [{"fy": fy, "fp": fp, "val": val}]}}}}}


def _facts_multi(tag: str, entries: list[dict]) -> dict:
    return {"facts": {"us-gaap": {tag: {"units": {"USD": entries}}}}}


def _merge(*facts_dicts: dict) -> dict:
    merged: dict = {"facts": {"us-gaap": {}}}
    for d in facts_dicts:
        merged["facts"]["us-gaap"].update(d["facts"]["us-gaap"])
    return merged


def test_primary_tag_is_used_when_present():
    facts = _facts("Revenues", 2026, "Q1", 1000.0)
    metrics = parse_company_facts(facts, 2026, 1)
    assert metrics.revenue == 1000.0


def test_falls_back_to_secondary_tag_when_primary_missing():
    # 公司未使用 Revenues 標籤，改用 RevenueFromContractWithCustomerExcludingAssessedTax
    facts = _facts("RevenueFromContractWithCustomerExcludingAssessedTax", 2026, "Q1", 2000.0)
    metrics = parse_company_facts(facts, 2026, 1)
    assert metrics.revenue == 2000.0


def test_derived_ratio_computed_from_two_tags():
    facts = _merge(
        _facts("GrossProfit", 2026, "Q1", 400.0),
        _facts("Revenues", 2026, "Q1", 1000.0),
    )
    metrics = parse_company_facts(facts, 2026, 1)
    assert metrics.gross_margin == 40.0


def test_missing_period_leaves_field_none_not_zero():
    facts = _facts("Revenues", 2025, "Q4", 1000.0)  # 不同期間，查詢 2026Q1 應查無資料
    metrics = parse_company_facts(facts, 2026, 1)
    assert metrics.revenue is None


def test_prefers_discrete_quarter_over_ytd_cumulative_duration():
    # Q2 10-Q 常同時申報「單季（約91天）」與「年初至今累計（約182天）」兩欄，
    # 應優先取單季數字，不可誤取累計數字
    facts = _facts_multi(
        "Revenues",
        [
            {"fy": 2026, "fp": "Q2", "start": "2025-09-28", "end": "2026-03-28", "val": 254940.0},  # 累計
            {"fy": 2026, "fp": "Q2", "start": "2025-12-28", "end": "2026-03-28", "val": 111184.0},  # 單季
        ],
    )
    metrics = parse_company_facts(facts, 2026, 2)
    assert metrics.revenue == 111184.0


def test_cumulative_only_period_left_none_not_mislabeled():
    # 現金流量表常僅申報年初至今累計數字，找不到單季區間時應視為缺漏，不可誤標為單季
    facts = _facts_multi(
        "NetCashProvidedByUsedInOperatingActivities",
        [{"fy": 2026, "fp": "Q2", "start": "2025-09-28", "end": "2026-03-28", "val": 999999.0}],
    )
    metrics = parse_company_facts(facts, 2026, 2)
    assert metrics.operating_cash_flow is None


def test_instant_value_without_start_end_still_returned():
    # 資產負債表項目為即時性數值，本就沒有 start，不應被單季篩選邏輯排除
    facts = _merge(
        _facts("Liabilities", 2026, "Q2", 2728560.0),
        _facts("Assets", 2026, "Q2", 8660949.0),
    )
    metrics = parse_company_facts(facts, 2026, 2)
    assert metrics.debt_ratio == pytest.approx(31.503, abs=0.01)


def test_fetch_batch_isolates_single_company_failure(monkeypatch):
    good_facts = _facts("Revenues", 2026, "Q1", 1000.0)

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, headers=None, **kwargs):
        if "0000320193" in url:  # AAPL CIK -> 正常回應
            return FakeResponse(good_facts)
        raise ConnectionError("simulated network failure")

    monkeypatch.setattr("app.ingestion.sec_edgar_client.get_with_retry", fake_get)

    results, failed = fetch_batch([("0000320193", "AAPL"), ("0000000000", "BAD")], 2026, 1)

    assert len(results) == 1 and results[0].ticker == "AAPL"
    assert len(failed) == 1 and failed[0][0] == ("0000000000", "BAD")
