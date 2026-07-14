# 需求追溯矩陣 (Requirements Traceability Matrix - RTM)

> 專案：各公司各季度財務分析與股價預測系統
> 最後更新：2026-07-14

| 需求編號 | 原始輸入來源 | 規格定義 (01) | 系統設計 (02) | 開發實作 (03) | 測試案例 (04) | 部署驗證 (05) | 維護記錄 (06) | 當前狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| REQ_001 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_001 | `db_schema.sql`(financial_reports)<br>`api_spec.md`(financials) | `app/ingestion/mops_client.py` | `tests/test_mops_client.py`（4 項） | `docker-compose.yml`(app 服務) | - | `[不連貫警告]`（待 Phase 06） |
| REQ_002 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_002 | `db_schema.sql`(financial_reports,source=SEC_EDGAR)<br>`api_spec.md`(financials) | `app/ingestion/sec_edgar_client.py`、`app/ingestion/alpha_vantage_client.py` | `tests/test_sec_edgar_mapping.py`（5）、`tests/test_alpha_vantage_client.py`（3） | `docker-compose.yml`(app 服務，環境變數注入金鑰) | - | `[不連貫警告]`（待 Phase 06） |
| REQ_003 | Planner 需求分析 | `formal_requirements.md` §REQ_003 | `er_diagram.md`(companies/financial_reports) | `app/ingestion/normalizer.py` | `tests/test_normalizer.py`（4） | `db_schema.sql` 掛載為 Postgres 初始化腳本 | - | `[不連貫警告]`（待 Phase 06） |
| REQ_004 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_004 | `db_schema.sql`(predictions.factor_model_*)<br>`activity_diagram.md` | `app/prediction/factor_model.py`（解決 OI-003） | `tests/test_factor_model.py`（4） | 隨 app 容器部署（未單獨拆分服務） | - | `[不連貫警告]`（待 Phase 06） |
| REQ_005 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_005 | `db_schema.sql`(price_history, predictions.timeseries_model_*) | `app/prediction/timeseries_model.py` | `tests/test_timeseries_model.py`（4） | 隨 app 容器部署 | - | `[不連貫警告]`（待 Phase 06） |
| REQ_006 | Planner 需求分析 | `formal_requirements.md` §REQ_006 | `db_schema.sql`(predictions.ensemble_weight_*)<br>`sequence_diagram.md` | `app/prediction/ensemble.py` | `tests/test_ensemble.py`（4） | 隨 app 容器部署 | - | `[不連貫警告]`（待 Phase 06） |
| REQ_007 | 缺口拷問 | `formal_requirements.md` §REQ_007 | `api_spec.md`（6 個查詢端點） | `app/routers/companies.py`、`app/routers/predictions.py` | `tests/test_api_companies.py`、`tests/test_api_predictions.py`、`04_testing/outputs/test_api.py`（系統整合，真實 HTTP） | `nginx.conf`（反向代理對外唯一入口） | - | `[不連貫警告]`（待 Phase 06） |
| REQ_008 | Planner 需求分析 | `formal_requirements.md` §REQ_008 | `api_spec.md`(POST /admin/ingest/trigger)<br>`activity_diagram.md` | `app/routers/admin.py`、`app/scheduler.py` | `tests/test_auth.py`、`test_api.py::test_admin_scope_can_trigger_ingest_real_http` | 排程隨 app 容器啟動（同進程 APScheduler） | - | `[不連貫警告]`（⚠️ 部分符合：管線串接待後續，見 test_results.md 五） |
| REQ_009 | Planner 需求分析 | `formal_requirements.md` §REQ_009 | `db_schema.sql`(prediction_backtests)<br>`api_spec.md`(backtest) | `app/prediction/backtest.py`、`app/routers/predictions.py` | `tests/test_backtest.py`（5）、`tests/test_api_predictions.py` | 隨 app 容器部署 | - | `[不連貫警告]`（待 Phase 06） |
| REQ_SEC_001 | 資安基準（中級） | `security_requirements.md` §五 | `db_schema.sql`(api_keys,audit_logs)<br>`threat_model.md` | `app/auth.py`、`app/audit.py`（含 source_ip 修復） | `tests/test_auth.py`（6）、`04_testing/outputs/dast_report.md`（DAST） | `nginx.conf`（TLS/安全標頭）、`security_deployment_checklist.md`、`signature_status.json` | - | `[不連貫警告]`（待 Phase 06） |

> 說明：`[不連貫警告]` 為框架標準狀態標記，表示該需求尚未貫穿所有階段（已完成 Phase 01~05）。待 Phase 06 補齊後，狀態將更新為 `[已驗證]`。
>
> **⚠️ Phase 05 重要限制**：本機環境未安裝 Docker/nginx/PostgreSQL，故「部署驗證 (05)」欄位所列組態檔案**已產出但未經實際建置/執行驗證**（無 `docker build`/`docker compose up`/`nginx -t` 之真實結果）。已完成驗證項目：`build_manifest.json` 之 33 個檔案 SHA-256 雜湊已重新計算比對一致；應用程式本身（非容器化）健康檢查通過；Git pre-commit 密鑰掃描 hook 已安裝並以真實測試驗證攔截效果。詳見 `05_deployment/outputs/deployment_topology.md`「驗證限制」章節。

## 待確認事項 (Open Issues)

| 編號 | 內容 | 提出階段 | 狀態 |
| :--- | :--- | :--- | :--- |
| OI-001 | 市場資料 API 供應商 | Phase 01 | ✅ 已於 Phase 02 確認：Alpha Vantage |
| OI-002 | 美股原文英文財報欄位對應細節 | Phase 01 | ✅ 已於 Phase 03 解決：`sec_edgar_client.py` us-gaap 標籤備援清單 |
| OI-003 | 預測幅度區間粒度尚未定案 | Phase 01 | ✅ 已於 Phase 03 解決：`factor_model.py` 分位數迴歸（5%/95%） |

## Bug 追蹤摘要（詳見 `04_testing/bug/bug_tracker.md`）

| Bug ID | 嚴重度 | 狀態 |
| :--- | :--- | :--- |
| BUG_001 | Trivial | ✅ 已修復（測試資源清理，非功能性缺陷） |

## 框架瑕疵回饋（詳見根目錄 `待辦事項.md`）

| # | 問題 | 影響 |
| :--- | :--- | :--- |
| 6 | `scripts/security/generate_sbom.py` 硬編碼裸 `pip` 指令，本環境無法使用 | SBOM 改手動產生等效輸出 |
| 7 | `scripts/security/install_hooks.py` 寫死指向框架自身倉庫路徑，無法用於獨立專案 | pre-commit hook 改手動安裝並驗證 |
