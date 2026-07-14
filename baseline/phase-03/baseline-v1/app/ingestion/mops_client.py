"""台股財務資料擷取（公開資訊觀測站 MOPS）— REQ_001。

MOPS 之公開查詢介面依報表類型（損益/資產負債/現金流量）分散於不同端點，且格式隨年度調整。
本模組將「HTTP 擷取」與「表格解析」拆為兩層：
  - fetch_quarterly_financials()：組裝查詢並取得原始 HTML
  - parse_financial_table()：從 HTML 表格中依關鍵字定位並萃取 7 項核心指標

拆分後可在不呼叫真實網路的情況下，以固定 HTML 片段驗證解析邏輯（見 tests/test_mops_client.py）。
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from io import StringIO

import pandas as pd

from app.config import settings
from app.ingestion.http_utils import ExternalSourceError, get_with_retry, run_batch_isolated
from app.ingestion.normalizer import NormalizedFinancials

# 財報項目關鍵字 -> NormalizedFinancials 欄位名稱
FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "revenue": ("營業收入合計", "營業收入"),
    "eps": ("基本每股盈餘", "每股盈餘"),
    "gross_margin": ("營業毛利率", "毛利率"),
    "net_margin": ("稅後淨利率", "淨利率"),
    "debt_ratio": ("負債比率", "負債占資產比率"),
    "operating_cash_flow": ("營業活動之淨現金流入", "營業活動現金流量"),
    "pe_ratio": ("本益比",),
}

_NUMERIC_RE = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")


@dataclass(frozen=True)
class MopsFetchResult:
    ticker: str
    fiscal_year: int
    fiscal_quarter: int
    metrics: NormalizedFinancials
    report_date: dt.date
    raw_source_ref: str


def _extract_number(cell_text: str) -> float | None:
    match = _NUMERIC_RE.search(cell_text.replace(" ", ""))
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def parse_financial_table(html: str) -> NormalizedFinancials:
    """從 MOPS 回傳的 HTML 表格中萃取 7 項核心財務指標。找不到的欄位保持 None（不可用 0 填補）。"""
    tables = pd.read_html(StringIO(html))
    values: dict[str, float | None] = {field: None for field in FIELD_KEYWORDS}

    for table in tables:
        for _, row in table.iterrows():
            row_text = " ".join(str(v) for v in row.values)
            for field, keywords in FIELD_KEYWORDS.items():
                if values[field] is not None:
                    continue
                if any(kw in row_text for kw in keywords):
                    number = _extract_number(row_text)
                    if number is not None:
                        values[field] = number

    return NormalizedFinancials(**values)


def fetch_quarterly_financials(ticker: str, fiscal_year: int, fiscal_quarter: int) -> MopsFetchResult:
    """擷取單一公司單一季度財報。逾時/暫時性錯誤由 get_with_retry 處理重試。"""
    query_url = f"{settings.mops_base_url}/server-java/t164sb03"
    params = {"co_id": ticker, "year": str(fiscal_year - 1911), "season": str(fiscal_quarter)}  # 民國年

    response = get_with_retry(query_url, params=params)
    metrics = parse_financial_table(response.text)

    missing = metrics.missing_fields()
    if len(missing) == len(FIELD_KEYWORDS):
        raise ExternalSourceError(
            f"MOPS 回應未包含任何可辨識欄位（ticker={ticker}, {fiscal_year}Q{fiscal_quarter}），"
            "可能為網站改版導致表格結構變更"
        )

    report_date = dt.date(fiscal_year, 3 * fiscal_quarter, 15)  # 概估公布日，實際以 MOPS 公告日為準
    return MopsFetchResult(
        ticker=ticker,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        metrics=metrics,
        report_date=report_date,
        raw_source_ref=f"{query_url}?co_id={ticker}&year={fiscal_year - 1911}&season={fiscal_quarter}",
    )


def fetch_batch(
    tickers: list[str], fiscal_year: int, fiscal_quarter: int
) -> tuple[list[MopsFetchResult], list[tuple[str, str]]]:
    """批次擷取多家公司財報。單一公司失敗不影響其餘公司（REQ_001 驗收條件）。"""
    results: list[MopsFetchResult] = []

    def _fetch_one(ticker: str) -> None:
        results.append(fetch_quarterly_financials(ticker, fiscal_year, fiscal_quarter))

    _, failed = run_batch_isolated(tickers, _fetch_one)
    return results, failed
