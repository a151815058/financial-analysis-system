"""美股財務資料擷取（SEC EDGAR Company Facts API）— REQ_002，解決 OI-002。

OI-002 決議：美股財報改用 SEC EDGAR 官方 Company Facts JSON API
(`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`)，而非爬取 10-Q/10-K
文件本身。該 API 直接提供 us-gaap XBRL 標籤化數值，格式穩定、免解析非結構化文件。

欄位對應採「備援 tag 清單」設計：不同公司/年度可能使用不同但語意相同的 us-gaap 標籤
（例如新舊會計準則下 Revenues vs RevenueFromContractWithCustomerExcludingAssessedTax），
依序嘗試直到取得數值，避免因單一公司改用不同標籤而擷取失敗。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.config import settings
from app.ingestion.http_utils import ExternalSourceError, get_with_retry, run_batch_isolated
from app.ingestion.normalizer import CORE_METRIC_FIELDS, NormalizedFinancials

# us-gaap 標籤備援清單（依優先順序嘗試）
DIRECT_TAG_CANDIDATES: dict[str, tuple[str, ...]] = {
    "revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"),
    "eps": ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"),
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
}
# 需由兩個 tag 相除計算之衍生指標： (分子候選, 分母候選)
DERIVED_RATIO_TAGS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "gross_margin": (("GrossProfit",), DIRECT_TAG_CANDIDATES["revenue"]),
    "net_margin": (("NetIncomeLoss",), DIRECT_TAG_CANDIDATES["revenue"]),
    "debt_ratio": (("Liabilities",), ("Assets",)),
}
# pe_ratio 無法直接由 XBRL 取得，須結合股價資料計算，於 ingestion 協調層處理（見 compute_pe_ratio）


@dataclass(frozen=True)
class SecEdgarFetchResult:
    ticker: str
    fiscal_year: int
    fiscal_quarter: int
    metrics: NormalizedFinancials
    report_date: dt.date
    raw_source_ref: str


def _company_facts_url(cik: str) -> str:
    padded = cik.zfill(10)
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json"


def _find_value_for_period(
    facts_json: dict, tag_candidates: tuple[str, ...], fiscal_year: int, fiscal_quarter: int
) -> tuple[float | None, str | None]:
    us_gaap = facts_json.get("facts", {}).get("us-gaap", {})
    fiscal_period = f"Q{fiscal_quarter}"
    for tag in tag_candidates:
        tag_data = us_gaap.get(tag)
        if not tag_data:
            continue
        for unit_values in tag_data.get("units", {}).values():
            for entry in unit_values:
                if entry.get("fy") == fiscal_year and entry.get("fp") == fiscal_period:
                    return float(entry["val"]), tag
    return None, None


def _derive_ratio(
    facts_json: dict,
    numerator_candidates: tuple[str, ...],
    denominator_candidates: tuple[str, ...],
    fiscal_year: int,
    fiscal_quarter: int,
) -> float | None:
    numerator, _ = _find_value_for_period(facts_json, numerator_candidates, fiscal_year, fiscal_quarter)
    denominator, _ = _find_value_for_period(facts_json, denominator_candidates, fiscal_year, fiscal_quarter)
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator * 100, 3)


def parse_company_facts(facts_json: dict, fiscal_year: int, fiscal_quarter: int) -> NormalizedFinancials:
    values: dict[str, float | None] = {}
    for field, candidates in DIRECT_TAG_CANDIDATES.items():
        value, _ = _find_value_for_period(facts_json, candidates, fiscal_year, fiscal_quarter)
        values[field] = value

    for field, (num_candidates, denom_candidates) in DERIVED_RATIO_TAGS.items():
        values[field] = _derive_ratio(
            facts_json, num_candidates, denom_candidates, fiscal_year, fiscal_quarter
        )

    values.setdefault("pe_ratio", None)  # 待結合股價資料於協調層計算
    return NormalizedFinancials(**values)


def fetch_quarterly_financials(
    cik: str, ticker: str, fiscal_year: int, fiscal_quarter: int
) -> SecEdgarFetchResult:
    url = _company_facts_url(cik)
    headers = {"User-Agent": settings.sec_edgar_user_agent}
    response = get_with_retry(url, headers=headers)
    facts_json = response.json()

    metrics = parse_company_facts(facts_json, fiscal_year, fiscal_quarter)
    if len(metrics.missing_fields()) == len(CORE_METRIC_FIELDS):
        raise ExternalSourceError(
            f"SEC EDGAR 回應未包含 {ticker} 於 {fiscal_year}Q{fiscal_quarter} 之任何可辨識 us-gaap 標籤"
        )

    report_date = dt.date(fiscal_year, min(3 * fiscal_quarter + 1, 12), 1)  # 概估，實際應解析 filed date
    return SecEdgarFetchResult(
        ticker=ticker,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        metrics=metrics,
        report_date=report_date,
        raw_source_ref=url,
    )


def fetch_batch(
    companies: list[tuple[str, str]], fiscal_year: int, fiscal_quarter: int
) -> tuple[list[SecEdgarFetchResult], list[tuple[tuple[str, str], str]]]:
    """批次擷取，companies 為 (cik, ticker) 列表；單一公司失敗不影響其餘公司。"""
    results: list[SecEdgarFetchResult] = []

    def _fetch_one(item: tuple[str, str]) -> None:
        cik, ticker = item
        results.append(fetch_quarterly_financials(cik, ticker, fiscal_year, fiscal_quarter))

    _, failed = run_batch_isolated(companies, _fetch_one)
    return results, failed


def compute_pe_ratio(price_at_report_date: float | None, ttm_eps: float | None) -> float | None:
    """PE 需結合股價（Alpha Vantage）與近四季 EPS 加總計算，於 ingestion 協調層呼叫。"""
    if not price_at_report_date or not ttm_eps or ttm_eps == 0:
        return None
    return round(price_at_report_date / ttm_eps, 3)
