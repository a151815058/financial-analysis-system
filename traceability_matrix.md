# 需求追溯矩陣 (Requirements Traceability Matrix - RTM)

> 專案：各公司各季度財務分析與股價預測系統
> 最後更新：2026-07-14

| 需求編號 | 原始輸入來源 | 規格定義 (01) | 系統設計 (02) | 開發實作 (03) | 測試案例 (04) | 部署驗證 (05) | 維護記錄 (06) | 當前狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| REQ_001 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_001 | `db_schema.sql`(financial_reports)<br>`api_spec.md`(financials) | `app/ingestion/mops_client.py` | `tests/test_mops_client.py` | - | - | `[不連貫警告]`（待 Phase 05） |
| REQ_002 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_002 | `db_schema.sql`(financial_reports,source=SEC_EDGAR)<br>`api_spec.md`(financials) | `app/ingestion/sec_edgar_client.py`、`app/ingestion/alpha_vantage_client.py` | `tests/test_sec_edgar_mapping.py`、`tests/test_alpha_vantage_client.py` | - | - | `[不連貫警告]`（待 Phase 05） |
| REQ_003 | Planner 需求分析 | `formal_requirements.md` §REQ_003 | `er_diagram.md`(companies/financial_reports) | `app/ingestion/normalizer.py` | `tests/test_normalizer.py` | - | - | `[不連貫警告]`（待 Phase 05） |
| REQ_004 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_004 | `db_schema.sql`(predictions.factor_model_*)<br>`activity_diagram.md` | `app/prediction/factor_model.py`（解決 OI-003） | `tests/test_factor_model.py` | - | - | `[不連貫警告]`（待 Phase 05） |
| REQ_005 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_005 | `db_schema.sql`(price_history, predictions.timeseries_model_*) | `app/prediction/timeseries_model.py` | `tests/test_timeseries_model.py` | - | - | `[不連貫警告]`（待 Phase 05） |
| REQ_006 | Planner 需求分析 | `formal_requirements.md` §REQ_006 | `db_schema.sql`(predictions.ensemble_weight_*)<br>`sequence_diagram.md` | `app/prediction/ensemble.py` | `tests/test_ensemble.py` | - | - | `[不連貫警告]`（待 Phase 05） |
| REQ_007 | 缺口拷問 | `formal_requirements.md` §REQ_007 | `api_spec.md`（6 個查詢端點） | `app/routers/companies.py`、`app/routers/predictions.py` | `tests/test_api_companies.py`、`tests/test_api_predictions.py` | - | - | `[不連貫警告]`（待 Phase 05） |
| REQ_008 | Planner 需求分析 | `formal_requirements.md` §REQ_008 | `api_spec.md`(POST /admin/ingest/trigger)<br>`activity_diagram.md` | `app/routers/admin.py`、`app/scheduler.py` | `tests/test_auth.py`（admin 端點權限） | - | - | `[不連貫警告]`（待 Phase 05） |
| REQ_009 | Planner 需求分析 | `formal_requirements.md` §REQ_009 | `db_schema.sql`(prediction_backtests)<br>`api_spec.md`(backtest) | `app/prediction/backtest.py`、`app/routers/predictions.py` | `tests/test_backtest.py`、`tests/test_api_predictions.py` | - | - | `[不連貫警告]`（待 Phase 05） |
| REQ_SEC_001 | 資安基準（中級） | `security_requirements.md` §五 | `db_schema.sql`(api_keys,audit_logs)<br>`threat_model.md` | `app/auth.py`、`app/audit.py`（含 source_ip 修復） | `tests/test_auth.py` | - | - | `[不連貫警告]`（待 Phase 05） |

> 說明：`[不連貫警告]` 為框架標準狀態標記，表示該需求尚未貫穿所有階段（已完成 Phase 01~03）。待 Phase 04（測試整合報告）、05、06 逐步補齊後，狀態將更新為 `[已驗證]`。

## 待確認事項 (Open Issues)

| 編號 | 內容 | 提出階段 | 狀態 |
| :--- | :--- | :--- | :--- |
| OI-001 | 市場資料 API 供應商 | Phase 01 | ✅ 已於 Phase 02 確認：Alpha Vantage |
| OI-002 | 美股原文英文財報欄位對應細節 | Phase 01 | ✅ 已於 Phase 03 解決：`sec_edgar_client.py` us-gaap 標籤備援清單 |
| OI-003 | 預測幅度區間粒度尚未定案 | Phase 01 | ✅ 已於 Phase 03 解決：`factor_model.py` 分位數迴歸（5%/95%） |
