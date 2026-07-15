# API 規格 (API Specification)

> 生成日期：2026-07-14 | Phase 02 系統設計
> 對應需求：REQ_007（查詢 API）、REQ_008（排程觸發）、REQ_SEC_001（存取控制）
> 認證方式：API Key（Header：`X-API-Key`），對應 `api_keys` 資料表

## 一、認證與授權

| 項目 | 說明 |
| :--- | :--- |
| 認證機制 | 所有端點皆須於 Header 帶入 `X-API-Key`，伺服器比對 `api_keys.key_hash` |
| 授權範圍 (scope) | `read`：可查詢財務指標/股價/預測結果；`admin`：額外可觸發排程任務 |
| 失敗回應 | 金鑰缺失或無效 → `401 Unauthorized`；權限不足 → `403 Forbidden` |
| 傳輸安全 | 全站強制 HTTPS（🔒 構面 6：系統與通訊保護），本地開發環境除外並於報告中註記為階段性限制 |

## 二、端點清單

### GET /api/v1/companies
- **說明**：查詢公司清單
- **Query 參數**：`market`（可選，`TW`/`US`）、`industry`（可選）
- **回應** `200 OK`：
```json
[
  { "ticker": "2330", "market": "TW", "name": "台積電", "industry": "半導體", "currency": "TWD" },
  { "ticker": "AAPL", "market": "US", "name": "Apple Inc.", "industry": "消費電子", "currency": "USD" }
]
```

### POST /api/v1/companies
- **說明**：新增追蹤公司（對應 REQ_011，需 `admin` scope）
- **Request Body**：
```json
{ "ticker": "MSFT", "market": "US", "name": "Microsoft Corp.", "industry": "軟體", "cik": null }
```
- **欄位說明**：
  - `ticker`（必填）、`market`（必填，`TW`/`US`）、`name`（必填）、`industry`（可選）
  - `cik`（可選，僅 `market=US` 有意義）：美股公司若未提供，伺服器會呼叫 SEC 官方 ticker→CIK 對照表自動查詢；查無結果才需使用者手動填入
  - `currency` 不接受客戶端輸入，伺服器依 `market` 自動決定（`TW`→`TWD`、`US`→`USD`）
- **回應** `201 Created`：`CompanyOut`（同 GET /api/v1/companies 單筆格式）
- **錯誤**：
  - `409 Conflict`：`(market, ticker)` 已存在
  - `422 Unprocessable Entity`：`market=US` 且未提供 `cik`，SEC 自動查詢亦查無對應 CIK
  - `403 Forbidden`：呼叫者非 `admin` scope
- **後續資料出現時機**：新增公司僅登記公司主檔，實際財務/股價資料需待排程（`mops_ingest`/`sec_edgar_ingest`/`price_ingest`，見下方 `POST /api/v1/admin/ingest/trigger`）下次執行或手動觸發後才會寫入。

### GET /api/v1/companies/{ticker}/financials
- **說明**：查詢指定公司之季度財務指標歷史（對應 REQ_001~003）
- **Path 參數**：`ticker`
- **Query 參數**：`market`（必填，區分台股/美股同代號情境）、`quarters`（預設 8，最近 N 季）
- **回應** `200 OK`：
```json
{
  "ticker": "2330",
  "market": "TW",
  "reports": [
    {
      "fiscal_year": 2026, "fiscal_quarter": 1, "report_date": "2026-04-15",
      "revenue": 592000000000, "eps": 9.87, "gross_margin": 55.2,
      "net_margin": 40.1, "debt_ratio": 32.5, "operating_cash_flow": 350000000000,
      "pe_ratio": 18.3, "currency": "TWD", "source": "MOPS", "is_latest_version": true
    }
  ]
}
```
- **錯誤**：查無資料 → `404 Not Found`

### GET /api/v1/companies/{ticker}/prices
- **說明**：查詢歷史股價（對應 REQ_005 資料需求）
- **Query 參數**：`market`（必填）、`from`、`to`（日期區間，預設近 180 天）

### GET /api/v1/companies/{ticker}/predictions/latest
- **說明**：查詢最新一週預測結果（對應 REQ_004~007）
- **Query 參數**：`market`（必填）
- **回應** `200 OK`：
```json
{
  "ticker": "2330", "market": "TW", "base_week_start_date": "2026-07-13",
  "direction": "UP", "range_lower_pct": 2.0, "range_upper_pct": 5.0,
  "confidence_score": 0.72,
  "sub_models": {
    "factor_model": { "direction": "UP", "range_pct": [1.5, 4.0] },
    "timeseries_model": { "direction": "UP", "range_pct": [2.5, 6.0] }
  },
  "model_version": "v1.0.0"
}
```

### GET /api/v1/companies/{ticker}/predictions/history
- **說明**：查詢歷史預測結果（供人工比對與可解釋性追溯）
- **Query 參數**：`market`（必填）、`weeks`（預設 12）

### GET /api/v1/companies/{ticker}/backtest
- **說明**：查詢預測準確率回測報告（對應 REQ_009）
- **回應** `200 OK`：
```json
{
  "ticker": "2330", "market": "TW", "window_weeks": 12,
  "directional_accuracy": 0.67, "range_hit_rate": 0.42
}
```

### POST /api/v1/admin/ingest/trigger
- **說明**：手動觸發資料擷取/模型更新排程（對應 REQ_008，需 `admin` scope）
- **Request Body**：
```json
{ "task": "mops_ingest" }
```
- **可用 task 值**：`mops_ingest`（台股）、`sec_edgar_ingest`（美股財報）、`price_ingest`（股價）、`model_retrain`、`weekly_predict`、`weekly_backtest`
- **回應** `202 Accepted`：任務已排入佇列
- **權限不足**：`403 Forbidden`

## 三、免責聲明（所有回應皆應附帶）

> 本系統輸出僅供分析參考，不構成投資建議。過往預測準確率不代表未來績效。
