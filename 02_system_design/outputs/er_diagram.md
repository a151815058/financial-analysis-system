# ER 圖 (Entity Relationship Diagram)

> 生成日期：2026-07-14 | Phase 02 系統設計
> 來源：SSOT `specs/executable_spec.yaml` + `formal_requirements.md`
> 對應 DDL：`db_schema.sql`

---

## Mermaid 格式

```mermaid
erDiagram
    companies ||--o{ financial_reports : "has"
    companies ||--o{ price_history : "has"
    companies ||--o{ predictions : "has"
    predictions ||--o| prediction_backtests : "evaluated_by"
    api_keys ||--o{ audit_logs : "generates"

    companies {
        bigint company_id PK
        varchar ticker "台股代號/美股Ticker"
        varchar market "TW/US"
        varchar name
        varchar industry
        char currency "TWD/USD"
        timestamptz created_at
    }

    financial_reports {
        bigint report_id PK
        bigint company_id FK
        int fiscal_year
        smallint fiscal_quarter "1-4"
        date report_date
        numeric revenue
        numeric eps
        numeric gross_margin
        numeric net_margin
        numeric debt_ratio
        numeric operating_cash_flow
        numeric pe_ratio
        char currency
        varchar source "MOPS/SEC_EDGAR"
        int data_version "財報更正版本"
        boolean is_latest_version
    }

    price_history {
        bigint price_id PK
        bigint company_id FK
        date trade_date
        numeric open_price
        numeric high_price
        numeric low_price
        numeric close_price
        bigint volume
        varchar source "TWSE/ALPHA_VANTAGE"
    }

    predictions {
        bigint prediction_id PK
        bigint company_id FK
        date base_week_start_date
        varchar direction "UP/DOWN/FLAT"
        numeric range_lower_pct
        numeric range_upper_pct
        numeric confidence_score
        varchar factor_model_direction
        varchar timeseries_model_direction
        numeric ensemble_weight_factor
        numeric ensemble_weight_timeseries
        varchar model_version
    }

    prediction_backtests {
        bigint backtest_id PK
        bigint prediction_id FK
        varchar actual_direction
        numeric actual_return_pct
        boolean direction_hit
        boolean range_hit
    }

    api_keys {
        bigint api_key_id PK
        varchar key_hash UK
        varchar owner
        varchar scope "read/admin"
        timestamptz revoked_at
    }

    audit_logs {
        bigint log_id PK
        bigint api_key_id FK
        varchar action
        varchar result "SUCCESS/FAILURE"
        jsonb detail
        timestamptz occurred_at
    }
```

---

## 設計說明

| 決策 | 理由 |
| :--- | :--- |
| `financial_reports` 以 `(company_id, fiscal_year, fiscal_quarter, data_version)` 唯一鍵 | 支援 REQ_003 財報更正版本追蹤，`is_latest_version` 供查詢時快速篩選最新版 |
| `predictions` 保留子模型明細欄位（`factor_model_*` / `timeseries_model_*`） | 對應 REQ_006 要求融合結果需保留兩子模型個別預測，供可解釋性追溯 |
| `api_keys` 僅存 `key_hash`，不存明文金鑰 | 對應資安需求 REQ_SEC_001 與構面 1（存取控制）最小揭露原則 |
| `audit_logs` 獨立於業務表 | 對應構面 2（事件日誌與可歸責性），Phase 03 實作時所有寫入/查詢動作皆應落一筆記錄 |
