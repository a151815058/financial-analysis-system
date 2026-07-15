"""台股財務資料擷取（源自 MOPS 公開申報資料）— REQ_001。

原設計假設單一 HTML 查詢端點（mopsov.twse.com.tw/server-java/t164sb03）可一次取得 7 項
核心指標，實際呼叫回傳 404（端點已失效，或原設計假設本身即有誤）。改採臺灣證券交易所
OpenAPI（openapi.twse.com.tw）之結構化 JSON 端點 —— 該資料為 TWSE 依 MOPS 申報內容整理
之公開資料鏡像，故仍標記 source='MOPS'。

7 項指標無法從單一端點取得，需分別查詢 3 個端點後合併：
  - 綜合損益表（opendata/t187ap06_L_ci）：營業收入、基本每股盈餘，並據以計算毛利率/淨利率
  - 資產負債表（opendata/t187ap07_L_ci）：資產總額/負債總額，據以計算負債比率
  - 個股日本益比（exchangeReport/BWIBBU_ALL）：本益比（僅為「查詢當下」最新值，非財報
    基準日當時的本益比，此為免費公開資料之已知限制，非本模組刻意混淆期別）

已知限制（誠實揭露，缺漏一律保持 None，不以估算值或 0 填補）：
  - 上述 OpenAPI 端點僅提供「最新一期」財報，不支援任意歷史季度查詢；若請求之
    fiscal_year/fiscal_quarter 與資料集當前期別不符，視為錯誤而非靜默回傳錯誤期別資料。
  - 現金流量表（operating_cash_flow）在本免費端點中無對應資料來源，固定回傳 None。
  - 僅涵蓋上市（L）一般業（ci）公司；金融/證券期貨/保險/金控/異業別公司需改查對應端點
    （t187ap06_L_basi/bd/ins/fh/mim 等），本模組暫未支援。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.ingestion.http_utils import ExternalSourceError, get_with_retry, run_batch_isolated
from app.ingestion.normalizer import NormalizedFinancials

TWSE_OPENAPI_BASE_URL = "https://openapi.twse.com.tw/v1"
INCOME_STATEMENT_URL = f"{TWSE_OPENAPI_BASE_URL}/opendata/t187ap06_L_ci"
BALANCE_SHEET_URL = f"{TWSE_OPENAPI_BASE_URL}/opendata/t187ap07_L_ci"
PE_RATIO_URL = f"{TWSE_OPENAPI_BASE_URL}/exchangeReport/BWIBBU_ALL"


@dataclass(frozen=True)
class MopsFetchResult:
    ticker: str
    fiscal_year: int
    fiscal_quarter: int
    metrics: NormalizedFinancials
    report_date: dt.date
    raw_source_ref: str


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    return float(cleaned) if cleaned else None


def _find_by_code(rows: list[dict], ticker: str, code_field: str) -> dict | None:
    return next((row for row in rows if row.get(code_field) == ticker), None)


def fetch_quarterly_financials(ticker: str, fiscal_year: int, fiscal_quarter: int) -> MopsFetchResult:
    """擷取單一公司單一季度財報。三個 TWSE OpenAPI 端點分別查詢後合併為 7 項核心指標。"""
    roc_year = str(fiscal_year - 1911)

    income_rows = get_with_retry(INCOME_STATEMENT_URL).json()
    income_row = _find_by_code(income_rows, ticker, "公司代號")
    if income_row is None:
        raise ExternalSourceError(
            f"TWSE 綜合損益表查無公司代號 {ticker}（可能為上櫃/興櫃或非一般業別，"
            "本端點僅涵蓋上市一般業）"
        )
    if income_row.get("年度") != roc_year or income_row.get("季別") != str(fiscal_quarter):
        actual_period = f"{income_row.get('年度')}Q{income_row.get('季別')}"
        raise ExternalSourceError(
            f"TWSE OpenAPI 免費端點僅提供最新一期財報（{actual_period}），"
            f"與要求之 {fiscal_year}Q{fiscal_quarter} 不符，不支援任意歷史季度查詢"
        )

    balance_rows = get_with_retry(BALANCE_SHEET_URL).json()
    balance_row = _find_by_code(balance_rows, ticker, "公司代號")

    per_rows = get_with_retry(PE_RATIO_URL).json()
    per_row = _find_by_code(per_rows, ticker, "Code")

    revenue = _to_float(income_row.get("營業收入"))
    gross_profit = _to_float(income_row.get("營業毛利（毛損）淨額"))
    net_income = _to_float(income_row.get("本期淨利（淨損）"))
    eps = _to_float(income_row.get("基本每股盈餘（元）"))

    gross_margin = round(gross_profit / revenue * 100, 3) if gross_profit is not None and revenue else None
    net_margin = round(net_income / revenue * 100, 3) if net_income is not None and revenue else None

    debt_ratio = None
    if balance_row is not None:
        total_assets = _to_float(balance_row.get("資產總額"))
        total_liabilities = _to_float(balance_row.get("負債總額"))
        if total_assets:
            debt_ratio = round(total_liabilities / total_assets * 100, 3)

    pe_ratio = _to_float(per_row.get("PEratio")) if per_row is not None else None

    metrics = NormalizedFinancials(
        revenue=revenue,
        eps=eps,
        gross_margin=gross_margin,
        net_margin=net_margin,
        debt_ratio=debt_ratio,
        operating_cash_flow=None,  # 免費端點無現金流量表資料來源，誠實標記為缺漏（非 0）
        pe_ratio=pe_ratio,
    )

    report_date = dt.date(fiscal_year, 3 * fiscal_quarter, 15)  # 概估公布日，實際以 MOPS 公告日為準
    return MopsFetchResult(
        ticker=ticker,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        metrics=metrics,
        report_date=report_date,
        raw_source_ref=f"{INCOME_STATEMENT_URL} + {BALANCE_SHEET_URL} + {PE_RATIO_URL}（公司代號={ticker}）",
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
