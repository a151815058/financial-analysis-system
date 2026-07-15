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


def _duration_days(entry: dict) -> int | None:
    start, end = entry.get("start"), entry.get("end")
    if not start or not end:
        return None
    try:
        return (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days
    except ValueError:
        return None


def _find_value_for_period(
    facts_json: dict, tag_candidates: tuple[str, ...], fiscal_year: int, fiscal_quarter: int
) -> tuple[float | None, str | None]:
    """在指定 fy/fp 下尋找對應數值。

    同一 fy/fp 底下，10-Q 常同時申報「單季」與「年初至今累計」兩種期間長度的數值
    （例如 Q2 同時揭露 3 個月與 6 個月兩欄），若不加篩選會不確定地取到累計數字並誤植
    為單季數字。優先取期間長度落在單季範圍（80~100 天）者；若候選皆有 period 資訊卻
    沒有一筆落在單季範圍（如部分公司現金流量表僅申報年初至今累計），寧可視為缺漏也不
    誤標為單季。無 start/end 者（即時性資產負債表項目）不受此限制，直接採用。
    """
    us_gaap = facts_json.get("facts", {}).get("us-gaap", {})
    fiscal_period = f"Q{fiscal_quarter}"
    for tag in tag_candidates:
        tag_data = us_gaap.get(tag)
        if not tag_data:
            continue
        for unit_values in tag_data.get("units", {}).values():
            candidates = [
                e for e in unit_values if e.get("fy") == fiscal_year and e.get("fp") == fiscal_period
            ]
            if not candidates:
                continue
            durations = [(_duration_days(e), e) for e in candidates]
            quarter_length = [e for d, e in durations if d is not None and 80 <= d <= 100]
            if quarter_length:
                return float(quarter_length[-1]["val"]), tag
            if any(d is not None for d, _ in durations):
                continue
            return float(candidates[0]["val"]), tag
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


# ---------------------------------------------------------------------------
# Ticker → CIK 自動查詢（REQ_011：新增美股公司時，未提供 CIK 之自動補全）
# ---------------------------------------------------------------------------

TICKER_TO_CIK_URL = "https://www.sec.gov/files/company_tickers.json"

_ticker_cik_cache: dict[str, str] | None = None


def _load_ticker_cik_map() -> dict[str, str]:
    """下載並快取 SEC 官方 ticker→CIK 對照表（固定白名單 URL，模組層級快取避免重複下載）。"""
    global _ticker_cik_cache
    if _ticker_cik_cache is None:
        headers = {"User-Agent": settings.sec_edgar_user_agent}
        payload = get_with_retry(TICKER_TO_CIK_URL, headers=headers).json()
        _ticker_cik_cache = {
            str(entry["ticker"]).upper(): str(entry["cik_str"]).zfill(10) for entry in payload.values()
        }
    return _ticker_cik_cache


def lookup_cik(ticker: str) -> str | None:
    """依 ticker 查詢 CIK；查詢失敗（網路/格式異常）視為查無結果，交由呼叫端要求使用者手動輸入。"""
    try:
        cik_map = _load_ticker_cik_map()
    except ExternalSourceError:
        return None
    return cik_map.get(ticker.upper())
