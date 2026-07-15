# 熱修補歷程 (Hotfix Log)

> 產出日期：2026-07-15 | Phase 06 維護與營運
> 本次三項熱修補皆於「真實外部資料來源擷取」過程中發現（非模擬/單元測試環境），修復後已補上對應單元測試防止回歸。

## HF-001：`mops_client.py` 查詢端點 404，改用 TWSE OpenAPI 重寫

- **發現方式**：對台積電（2330）執行真實 MOPS 財報擷取，`https://mopsov.twse.com.tw/server-java/t164sb03` 回傳 `404 Client Error: Not Found`
- **根本原因**：原設計假設單一 HTML 端點可一次取得 7 項核心財務指標，該端點本身已失效，且此假設不成立——台股財務比率實際分散於損益表、資產負債表、市場本益比等不同來源，非單一報表
- **影響範圍**：`app/ingestion/mops_client.py` 全部函式（`fetch_quarterly_financials`、`fetch_batch`）；`tests/test_mops_client.py` 全面改寫
- **修補方案**：改用臺灣證券交易所 OpenAPI（`openapi.twse.com.tw`，TWSE 依 MOPS 申報內容整理之結構化 JSON 鏡像）3 個真實端點合併取得：
  - `opendata/t187ap06_L_ci`（綜合損益表）→ 營業收入、EPS，並據以計算毛利率/淨利率
  - `opendata/t187ap07_L_ci`（資產負債表）→ 資產/負債總額，據以計算負債比率
  - `exchangeReport/BWIBBU_ALL`（個股日本益比）→ 本益比（僅為查詢當下最新值，非財報基準日當時本益比，已於程式註解與 docstring 誠實揭露此限制）
  - 新增防呆：若請求之 fiscal_year/fiscal_quarter 與資料集實際期別不符，明確報錯而非靜默回傳錯誤期別資料（因免費端點僅提供最新一期）
  - `operating_cash_flow` 因免費端點無現金流量表資料來源，固定回傳 `None`（誠實標記缺漏，不以 0 或估算值填補）
- **驗證**：`tests/test_mops_client.py`（5 項，涵蓋合併三端點、查無公司、期別不符、資產負債表缺漏容錯、批次隔離），並以台積電真實資料完整跑過一次寫入 Supabase（revenue=1,134,103,440 千元、EPS=22.08、gross_margin=66.246%、net_margin=50.507%、debt_ratio=31.504%、pe_ratio=32.54）
- **狀態**：✅ 已修復並驗證

## HF-002：`sec_edgar_client.py` 單季與年初至今累計數字混淆

- **發現方式**：對 Apple（CIK 320193）執行真實 SEC EDGAR 財報擷取時，人工比對原始 XBRL 資料發現同一 fy/fp（如 2026 Q2）底下同時存在「單季（約91天）」與「年初至今累計（約182天）」兩筆數值
- **根本原因**：`_find_value_for_period()` 原邏輯對指定 fy/fp 僅取陣列中第一筆匹配項，未區分揭露期間長度，可能不確定地取到累計數字並誤植為單季數字（10-Q 常見的真實 XBRL 揭露慣例，非本系統獨有問題）
- **影響範圍**：`app/ingestion/sec_edgar_client.py` 之 `_find_value_for_period`（間接影響 revenue、eps、operating_cash_flow 及衍生比率 gross_margin/net_margin/debt_ratio 之正確性）
- **修補方案**：新增 `_duration_days()` 依 `start`/`end` 計算揭露期間長度，優先採用落在單季範圍（80~100天）之數值；若候選皆有期間資訊卻無單季範圍者（如現金流量表常僅申報累計值），寧可回傳 `None` 視為缺漏，也不誤標為單季；無 `start`/`end` 之即時性數值（資產負債表項目）不受此限制
- **驗證**：`tests/test_sec_edgar_mapping.py` 新增 3 項測試（單季優先於累計、累計限定情境回傳 None、即時性數值不受影響），既有 4 項測試無回歸。以 Apple 真實資料驗證：修復前若未過濾會誤取 254,940,000,000（6個月累計），修復後正確取得 111,184,000,000（單季，已與獨立人工核對之真實 SEC 申報數字一致）
- **狀態**：✅ 已修復並驗證

## HF-003：`alpha_vantage_client.py` 對 `outputsize=full` 免費層級限制的錯誤訊息不明確

- **發現方式**：對 Apple 執行真實股價擷取，`outputsize='full'` 回傳 `{"Information": "...premium feature..."}`，因原程式碼僅檢查 `Error Message`/`Note` 兩個鍵，未識別 `Information` 鍵，導致錯誤訊息退化為不明確的「回應缺少 Time Series (Daily)」
- **根本原因**：Alpha Vantage 免費層級不支援 `outputsize=full`（僅付費方案可用），程式碼對此限制訊息未特別辨識
- **影響範圍**：`app/ingestion/alpha_vantage_client.py` 之 `fetch_daily_prices`
- **修補方案**：新增對 `Information` 鍵的辨識與明確錯誤訊息；擷取端改用免費層級支援的 `outputsize='compact'`（近100個交易日）
- **驗證**：`tests/test_alpha_vantage_client.py` 新增 1 項測試；以 Apple 真實資料驗證 `compact` 模式成功寫入 100 筆真實股價（2026-02-19 ~ 2026-07-14）
- **狀態**：✅ 已修復並驗證

## 修補統計

| 項目 | 數量 |
| :--- | :--- |
| 修補模組數 | 3（`mops_client.py`、`sec_edgar_client.py`、`alpha_vantage_client.py`） |
| 相關測試現況 | `test_mops_client.py` 5 項（全改寫）、`test_sec_edgar_mapping.py` 8 項（5 既有 + 3 新增）、`test_alpha_vantage_client.py` 4 項（3 既有 + 1 新增） |
| 影響資料正確性等級 | HF-002 為 B 類（可能導致寫入資料庫的財務數字錯誤，非僅程式異常），HF-001/HF-003 為 A 類（連線失敗/錯誤訊息不明確，未寫入錯誤資料） |
| 是否已影響正式資料庫 | 是——修復前 HF-001 曾嘗試寫入失敗（未寫入，因例外中斷交易，Supabase 無髒資料）；HF-002/HF-003 於修復後才首次執行擷取，故 Supabase 中無誤植資料 |
