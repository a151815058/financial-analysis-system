# 需求追溯矩陣 (Requirements Traceability Matrix - RTM)

> 專案：各公司各季度財務分析與股價預測系統
> 最後更新：2026-07-24

| 需求編號 | 原始輸入來源 | 規格定義 (01) | 系統設計 (02) | 開發實作 (03) | 測試案例 (04) | 部署驗證 (05) | 維護記錄 (06) | 當前狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| REQ_001 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_001 | `db_schema.sql`(financial_reports)<br>`api_spec.md`(financials) | `app/ingestion/mops_client.py`（HF-001 改用 TWSE OpenAPI 重寫） | `tests/test_mops_client.py`（5 項）+ 真實台積電(2330)資料擷取寫入 Supabase | `docker-compose.yml`(app 服務)、`deployment_config.md`（DB 已真實驗證） | `06_maintenance/outputs/hotfix_log.md`（HF-001） | `[已驗證]` |
| REQ_002 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_002 | `db_schema.sql`(financial_reports,source=SEC_EDGAR)<br>`api_spec.md`(financials) | `app/ingestion/sec_edgar_client.py`（HF-002 單季/累計修正）、`app/ingestion/alpha_vantage_client.py`（HF-003 Information 訊息） | `tests/test_sec_edgar_mapping.py`（8 項）、`tests/test_alpha_vantage_client.py`（4 項）+ 真實 Apple(AAPL)資料擷取寫入 Supabase | `docker-compose.yml`(app 服務，環境變數注入金鑰) | `06_maintenance/outputs/hotfix_log.md`（HF-002、HF-003） | `[已驗證]` |
| REQ_003 | Planner 需求分析 | `formal_requirements.md` §REQ_003 | `er_diagram.md`(companies/financial_reports) | `app/ingestion/normalizer.py` | `tests/test_normalizer.py`（4） | `db_schema.sql` 掛載為 Postgres 初始化腳本，已於 Supabase 實際套用 | `06_maintenance/outputs/regression_test_report.md` | `[已驗證]` |
| REQ_004 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_004 | `db_schema.sql`(predictions.factor_model_*, trained_models 新表 PATCH-002)<br>`activity_diagram.md`<br>`migrations/005_add_trained_models.sql` | `app/prediction/factor_model.py`（解決 OI-003）、`app/prediction/features.py`（REQ_016 新增：財報 YoY/QoQ 特徵工程）、`app/jobs.py::run_weekly_predict`（REQ_016：跨公司彙總訓練）、`app/prediction/model_registry.py`（新檔，PATCH-002：模型持久化/版本化）、`app/jobs.py::run_model_retrain`（PATCH-002） | `tests/test_factor_model.py`（4）、`tests/test_prediction_features.py`（10 項，REQ_016）、`tests/test_jobs.py`（PATCH-002 新增 5 項） | 隨 app 容器部署（未單獨拆分服務） | `06_maintenance/outputs/monitoring_dashboard.md`、`06_maintenance/outputs/patch_changelog.md`（PATCH-002）；`weekly_predict` 已排程串接（REQ_016），`model_retrain` 已補完真實邏輯（PATCH-002：訓練後以 `trained_models` 表持久化，`weekly_predict` 優先讀取），但真實財報樣本仍不足 10 筆訓練門檻，尚未在真實資料上實際觸發訓練/持久化 | `[不連貫警告]`（實作與測試皆完成，模型本身可訓練/推論/持久化；真實財報樣本量不足（3 筆 < 10 筆門檻）尚未在真實資料上觸發訓練，見 REQ_016、PATCH-002 補充說明） |
| REQ_005 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_005 | `db_schema.sql`(price_history, predictions.timeseries_model_*) | `app/prediction/timeseries_model.py`；股價真實資料已由 REQ_001/002 補齊（TW 50+ 筆、US 100+ 筆）；`app/jobs.py::run_weekly_predict`（REQ_016 串接排程） | `tests/test_timeseries_model.py`（4）、`tests/test_jobs.py`（REQ_016 新增 6 項） | 隨 app 容器部署 | `06_maintenance/outputs/monitoring_dashboard.md`；已於 2026-07-17 對台積電(2330)/Apple(AAPL) 真實股價成功產生預測並寫入 Supabase | `[已驗證]`（REQ_016：已對真實資料成功執行並產出預測） |
| REQ_006 | Planner 需求分析 | `formal_requirements.md` §REQ_006 | `db_schema.sql`(predictions.ensemble_weight_*)<br>`sequence_diagram.md` | `app/prediction/ensemble.py`；`app/jobs.py::_replace_prediction_for_week`（REQ_016：財報因子模型資料不足時優雅降級為僅時間序列模型，見補充說明） | `tests/test_ensemble.py`（4）、`tests/test_jobs.py`（REQ_016，驗證融合/降級兩種路徑） | 隨 app 容器部署 | `06_maintenance/outputs/monitoring_dashboard.md` | `[不連貫警告]`（融合邏輯本身已測試；因 REQ_004 財報樣本不足，真實資料目前皆走「僅時間序列模型」降級路徑，尚未真正融合過真實資料，見 REQ_016 補充說明） |
| REQ_007 | 缺口拷問 | `formal_requirements.md` §REQ_007 | `api_spec.md`（6 個查詢端點） | `app/routers/companies.py`、`app/routers/predictions.py` | `tests/test_api_companies.py`、`tests/test_api_predictions.py`、`04_testing/outputs/test_api.py`（系統整合，真實 HTTP）+ 真實 Supabase 資料 API 讀取驗證 | `nginx.conf`（反向代理對外唯一入口） | `06_maintenance/outputs/monitoring_dashboard.md`（API 稽核事件監控，§3） | `[已驗證]` |
| REQ_008 | Planner 需求分析 | `formal_requirements.md` §REQ_008 | `api_spec.md`(POST /admin/ingest/trigger)<br>`activity_diagram.md` | `app/routers/admin.py`、`app/scheduler.py`、`app/main.py`（scheduler 啟動/關閉；`_stub_job` 已於 PATCH-002 移除，6 任務全數為真實邏輯）、`app/jobs.py`（REQ_011 追加：mops_ingest/sec_edgar_ingest/price_ingest 真實邏輯；REQ_016 追加：weekly_predict 真實邏輯；PATCH-001 追加：weekly_backtest 真實邏輯；PATCH-002 追加：model_retrain 真實邏輯） | `tests/test_auth.py`、`test_api.py::test_admin_scope_can_trigger_ingest_real_http`、`tests/test_jobs.py`（REQ_011、REQ_016、PATCH-001、PATCH-002） | 排程隨 app 容器啟動（同進程 APScheduler） | `06_maintenance/outputs/monitoring_dashboard.md` §2（排程健康度監控已設計）；REQ_011 已解除資料擷取 3 任務的管線斷鏈，REQ_016 解除 weekly_predict 之管線斷鏈，PATCH-001/PATCH-002（`06_maintenance/outputs/patch_changelog.md`）解除 weekly_backtest/model_retrain 之管線斷鏈 | `[已驗證]`（6 個排程任務皆已脫離 stub：3 個資料擷取 + weekly_predict + weekly_backtest + model_retrain，皆已於本機連線正式 Supabase 驗證真實執行） |
| REQ_009 | Planner 需求分析 | `formal_requirements.md` §REQ_009 | `db_schema.sql`(prediction_backtests)<br>`api_spec.md`(backtest) | `app/prediction/backtest.py`、`app/routers/predictions.py`、`app/jobs.py::run_weekly_backtest`（新增，PATCH-001：評分邏輯，含 `_nearest_baseline_price`/`_target_price_after`） | `tests/test_backtest.py`（5）、`tests/test_api_predictions.py`、`tests/test_jobs.py`（PATCH-001 新增 8 項） | 隨 app 容器部署 | `06_maintenance/outputs/patch_changelog.md`（PATCH-001）；`06_maintenance/outputs/monitoring_dashboard.md` §4 已過時（原記錄 `prediction_backtests` 為空，PATCH-001 後已有真實資料） | `[已驗證]`（PATCH-001：`weekly_backtest` 已補完真實邏輯，本機連線正式 Supabase 驗證已產生 2 筆真實回測資料，`GET /api/v1/companies/{ticker}/backtest` 已能正常回傳，不再固定 404） |
| REQ_SEC_001 | 資安基準（中級） | `security_requirements.md` §五 | `db_schema.sql`(api_keys,audit_logs)<br>`threat_model.md` | `app/auth.py`、`app/audit.py`（含 source_ip 修復）；本次以真實 API Key 驗證 | `tests/test_auth.py`（7）、`04_testing/outputs/dast_report.md`（DAST） | `nginx.conf`（TLS/安全標頭）、`security_deployment_checklist.md`、`signature_status.json` | `06_maintenance/outputs/security_trend.md`（100%，未下降） | `[已驗證]` |
| REQ_010 | 使用者口述（Phase 05 後追加，Phase 06 前） | 補於本文件 | 無獨立設計文件（沿用既有 API 端點，未另建 UI 雛型） | `app/static/dashboard.{html,css,js}`、`app/main.py`（`/dashboard`、`/static` 掛載） | `tests/test_dashboard.py`（3 項）+ 真實瀏覽器驗證（Chrome headless + Puppeteer，見下方說明）+ 本次以真實瀏覽器視窗顯示台積電/Apple 真實資料 | 隨 app 容器一併部署（無獨立服務） | `06_maintenance/outputs/regression_test_report.md`（`test_dashboard.py` 3 項無回歸） | `[已驗證]` |
| REQ_011 | 使用者口述（Phase 06 後追加，out-of-band） | 補於本文件、`01_planning_and_analysis/reg/requirement_tracker.md` | `api_spec.md`(POST /api/v1/companies)<br>`threat_model.md` §三之一 | `app/routers/companies.py`（POST 端點）、`app/schemas.py`（`CompanyCreateRequest`）、`app/ingestion/sec_edgar_client.py`（`lookup_cik`）、`app/jobs.py`（新檔）、`app/static/dashboard.{html,css,js}`（新增公司表單） | `tests/test_api_companies.py`（新增 6 項）、`tests/test_cik_lookup.py`（4 項）、`tests/test_jobs.py`（3 項） | 隨 app 容器一併部署（無獨立服務）；排程任務現會真實呼叫外部 API，見 §五之提醒 | 補於本文件下方「REQ_011 補充說明」 | `[已驗證]` |
| REQ_012 | 使用者口述（REQ_011 之延伸，out-of-band） | 補於本文件、`01_planning_and_analysis/reg/requirement_tracker.md` | `api_spec.md`(GET /api/v1/companies/search) | `app/routers/companies.py`(`GET /search`)、`app/ingestion/mops_client.py`(`search_companies`，重用既有損益表端點)、`app/ingestion/sec_edgar_client.py`(`search_companies`，擴充既有 ticker 對照表快取)、`app/static/dashboard.{html,css,js}`（新增公司表單改為代碼/名稱擇一輸入之搜尋建議） | `tests/test_api_companies.py`（新增 3 項）、`tests/test_mops_client.py`（新增 4 項）、`tests/test_cik_lookup.py`（新增 4 項） | 隨 app 容器一併部署（無獨立服務） | 補於本文件下方「REQ_012 補充說明」 | `[已驗證]` |
| REQ_013 | 使用者口述（out-of-band） | 補於本文件、`01_planning_and_analysis/reg/requirement_tracker.md` | `api_spec.md`(GET /api/v1/admin/jobs、GET /admin) | `app/db_models.py`(`JobRun`)、`app/jobs.py`(`track_job`)、`app/routers/admin.py`(`GET /jobs` 擴充、`trigger_ingest` 帶 `trigger_mode`)、`app/static/admin.{html,js}`（新頁面）、`app/main.py`(`GET /admin` 路由、`job_functions` 全數包上 `track_job`) | `tests/test_jobs.py`（新增 4 項）、`tests/test_admin_jobs.py`（3 項）、`tests/test_admin_page.py`（3 項） | 隨 app 容器一併部署（無獨立服務）；`job_runs` 為新資料表，`init_db()` 之 `Base.metadata.create_all` 於下次啟動時自動建立，無需手動 migration（與 HF-004 之 ALTER TABLE 情境不同） | 補於本文件下方「REQ_013 補充說明」 | `[已驗證]` |
| REQ_014 | 使用者口述（out-of-band，REQ_013 之延伸） | 補於本文件、`01_planning_and_analysis/reg/requirement_tracker.md` | `api_spec.md`(/api/v1/auth/*)、`threat_model.md` §三之二 | `app/auth.py`(`hash_password`/`verify_password`/`require_admin_access`/`require_session_login`)、`app/routers/auth.py`（新檔）、`app/db_models.py`(`AdminUser`)、`app/main.py`(`SessionMiddleware`)、`app/static/admin.{html,js}`（登入卡片、變更密碼 modal） | `tests/test_api_auth.py`（10 項）、`tests/test_admin_jobs.py`（新增 3 項） | 隨 app 容器一併部署；`admin_users` 為新資料表，`init_db()` 自動建立，無需手動 migration | 補於本文件下方「REQ_014 補充說明」 | `[已驗證]` |
| REQ_015 | 使用者口述（out-of-band，REQ_014 之延伸） | 補於本文件、`01_planning_and_analysis/reg/requirement_tracker.md`、`security_requirements.md` §五之三（風險接受） | `api_spec.md`(一、認證與授權 REQ_015 註記)、`threat_model.md` §三之三 | `app/auth.py`(`optional_read_access`/`OptionalReadAccessContext`)、`app/routers/companies.py`、`app/routers/predictions.py`、`app/static/dashboard.{html,js}`（移除 API Key 輸入框，改登入/登出按鈕）、`app/static/admin.js`(`safeNextPath`，`?next=` 安全導回)、`app/db_session.py`(`pool_pre_ping`，順手修復 Supabase 閒置斷線) | `tests/test_auth.py`（改寫 2 項）、`tests/test_api_companies.py`（改寫 1 項、新增 2 項）、`tests/test_api_predictions.py`（新增 1 項） | 隨 app 容器一併部署（無獨立服務） | 補於本文件下方「REQ_015 補充說明」 | `[已驗證]` |
| REQ_016 | 使用者口述（out-of-band，補完 REQ_004/005/006 之 weekly_predict 斷鏈） | 補於本文件、`01_planning_and_analysis/reg/requirement_tracker.md` | 無獨立設計文件（沿用既有 `db_schema.sql`/`activity_diagram.md`，未變更 schema） | `app/prediction/features.py`（新檔，財報 YoY/QoQ 特徵工程）、`app/jobs.py`(`run_weekly_predict`/`_train_pooled_factor_model`/`_predict_company_timeseries`/`_replace_prediction_for_week`)、`app/main.py`（`weekly_predict` 由 stub 改真實邏輯）、`app/static/dashboard.js`（KPI 標籤誠實反映融合/降級兩種模式） | `tests/test_prediction_features.py`（新檔，10 項）、`tests/test_jobs.py`（新增 6 項） | 隨 app 容器一併部署（無獨立服務） | 補於本文件下方「REQ_016 補充說明」 | `[已驗證]`（實作完整、130 項測試通過、已對真實資料成功執行；財報因子模型本身因真實樣本不足暫走降級路徑，見補充說明） |

> 說明：`[不連貫警告]` 為框架標準狀態標記，表示該需求尚未貫穿所有階段。Phase 06（維護與營運）已於 2026-07-15 完成第一輪，REQ_001/002/003/007/SEC_001/010 已因本輪真實資料擷取與熱修補而更新為 `[已驗證]`。REQ_008 已因 REQ_011（同日 out-of-band 追加）補齊 3 個資料擷取任務的真實邏輯而更新為 `[已驗證]`。REQ_016（2026-07-17）將 weekly_predict 由 stub 接上真實邏輯：REQ_005（時間序列模型）已對真實資料成功執行，更新為 `[已驗證]`；REQ_004（財報因子模型）與 REQ_006（融合）實作與測試皆已完成，但受限於真實財報樣本量（見 REQ_016 補充說明），目前仍走「僅時間序列模型」降級路徑，尚未實際融合過真實資料，故維持 `[不連貫警告]`，待財報歷史隨排程持續累積、跨公司彙總樣本數達 10 筆門檻後會自動切換為真正的雙模型融合（無需再次介入）。**2026-07-24（Phase 06 第二輪，`06_maintenance/outputs/patch_changelog.md`）**：PATCH-001 將 `weekly_backtest` 由 stub 補完為真實回測評分邏輯，已於正式資料庫產生真實回測資料，REQ_009 因而更新為 `[已驗證]`；PATCH-002 將 `model_retrain` 由 stub 補完為真實模型持久化邏輯（新增 `trained_models` 表 + `app/prediction/model_registry.py`），REQ_004「版本化模型檔案」驗收條件所需之基礎設施至此已完整實作，惟仍受限於同一項真實財報樣本量不足之已知限制而尚未在正式環境實際觸發，REQ_004/REQ_006 維持 `[不連貫警告]`。REQ_008 因 6 個排程任務至此全數脫離 stub，狀態說明同步更新。
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

## REQ_010 補充說明：內部分析儀表板（Phase 05 之後、Phase 06 之前追加）

> 使用者要求暫緩進入 Phase 06，先新增一個可視化介面查看 API 資料（文字 + 圖表）。此為範疇外的
> 輕量追加，未依標準 SSDLC Phase 02（系統設計）先產出 UI 雛型再進 Phase 03 實作的順序，而是直接
> 於既有 Phase 03 `app/` 套件內新增靜態前端頁面，故未建立獨立 Baseline，僅在此矩陣與
> `system_specification.md`／`memory.md` 中補充記錄，維持追溯完整性。

- **技術方案**：嵌入 FastAPI 的靜態頁面（`GET /dashboard`），無額外 Python 依賴，前端為手刻 SVG 圖表（無 CDN 相依），呼叫既有 7 個 API 端點。
- **內容**：公司選擇器、財務指標歷史（表格 + 趨勢圖，7 指標可切換）、股價歷史趨勢圖、最新預測結果（KPI 卡片 + 股價圖上以區間色塊疊加融合/財報因子/時間序列三模型明細）、回測準確率（含尚無資料時的空狀態）。
- **配色**：採用 dataviz skill 的參考色板，已實際執行 `validate_palette.js` 驗證 light/dark 兩模式（皆 PASS，含 CVD 分離度與對比度檢查）。
- **驗證方式**：由於本環境無法開啟真實使用者瀏覽器，改以 Chrome headless（系統既有安裝）+ Puppeteer 驅動，實際輸入 API Key、選擇公司、觸發圖表 hover，並擷取螢幕截圖確認：light mode、dark mode、無效金鑰錯誤狀態、tooltip 互動皆正確渲染。新增 `tests/test_dashboard.py`（3 項）驗證路由本身可正常回應。全部 52 項自動化測試（Phase 03/04 既有 49 + 本次 3）皆通過。

## REQ_011 補充說明：新增追蹤公司 UI/API + 排程真實擷取邏輯（Phase 06 後追加）

> 使用者要求在既有系統上追加「新增公司」功能（含美股），並依 SSDLC 規劃。此為範疇外的輕量追加，
> 比照 REQ_010 先例，未走完整 Phase 02→03 PDCA 順序、未建立獨立 Baseline，僅於本文件與
> `01_planning_and_analysis/reg/requirement_tracker.md`／`phase_gates.json`（`out_of_band_additions`）
> 補充記錄。建立在先前 out-of-band 的 HF-004（`companies.cik` 欄位）之上。

- **新增公司**：`POST /api/v1/companies`（`admin` scope）。美股未提供 `cik` 時，自動呼叫 SEC 官方
  `company_tickers.json` 對照表查詢；查無結果則回 `422`，前端表單會秀出手動 CIK 欄位。重複
  `(market, ticker)` 回 `409`。
- **排程真實邏輯**：新增 `app/jobs.py`，`mops_ingest`/`sec_edgar_ingest`/`price_ingest` 三個排程任務
  自 stub 改為真正查詢 `companies` 表、呼叫對應擷取 client、寫入 `financial_reports`/`price_history`。
  `weekly_predict`/`model_retrain`/`weekly_backtest` 三個模型類任務仍維持 stub，非本次範圍。
- **前端**：`dashboard.js`/`dashboard.html`/`dashboard.css` 新增「＋ 新增公司」表單，處理
  409/422/403 等錯誤情境，成功後自動刷新並選取新公司。
- **驗證方式**：新增 23 項自動化測試（`test_api_companies.py` 擴充 6 項、`test_cik_lookup.py` 4 項、
  `test_jobs.py` 3 項，另計入既有擴充），全數通過；既有 `04_testing/outputs/test_api.py`（9 項真實
  uvicorn 子行程系統整合測試）於本次異動後重新執行，全數通過，未產生回歸。詳見
  `04_testing/outputs/test_results.md`。

## REQ_012 補充說明：新增公司代碼/名稱模糊搜尋（REQ_011 之延伸）

> 使用者於實際測試 REQ_011「新增公司」功能後提出回饋：股票代碼與公司名稱應可擇一輸入，並支援
> 模糊搜尋。比照 REQ_010/REQ_011 先例，屬 out-of-band 輕量追加。

- **模糊查詢語意**：確認後採用「字串包含比對（大小寫不敏感）」，非編輯距離（如容錯拼錯字）之
  真正模糊比對，避免為目前規模（百到千筆候選）不成比例地引入額外演算法庫。
- **公司目錄來源**：
  - 美股：重用既有 `sec_edgar_client.py` 為 CIK 自動查詢而快取的 SEC ticker 對照表，擴充為同時
    保存名稱，未新增外部依賴。
  - 台股：重用既有 `mops_client.py` 已在呼叫的 TWSE 綜合損益表端點（本身即涵蓋全體上市一般業
    公司），僅萃取「公司代號」/「公司名稱」兩欄作為目錄，不解析財報數字。
- **已知限制**：台股比對對象為公司正式登記名稱（如「台灣積體電路製造股份有限公司」），輸入口語
  簡稱（如「台積電」）若非該名稱之連續子字串，將查無結果；此時使用者可於表單直接手動輸入代碼與
  名稱，維持既有 REQ_011 手動輸入路徑不受影響。
- **驗證方式**：新增 11 項自動化測試（`test_mops_client.py`、`test_cik_lookup.py` 各自的
  `search_companies` 案例、`test_api_companies.py` 之 `GET /search` 端點案例），既有 84 項測試
  （REQ_011 完成時基準）與新增 11 項共 95 項全數通過，無回歸。

## REQ_013 補充說明：排程執行狀況頁面（/admin）+ 手動觸發

> 使用者升級 Render 為付費方案（不休眠）後詢問排程能否穩定執行，進而要求新增一個可檢視排程執行
> 狀況、並可手動觸發更新的頁面。屬 out-of-band 輕量追加。

- **執行紀錄範圍**：確認後採用「每個任務僅保留最新一筆執行結果」（非歷史紀錄），新增 `job_runs`
  資料表（`task_name` 為主鍵，`status`/`trigger_mode`/`started_at`/`finished_at`/`detail`），每次
  執行以 upsert 覆寫。
- **實作方式**：新增 `app/jobs.py::track_job()` 包裝函式，將全部 6 個排程任務（含 3 個仍為 stub
  的模型任務）統一包裝，執行完成後記錄成功/失敗；`app/routers/admin.py` 的手動觸發端點呼叫
  `scheduler.add_job(..., kwargs={"trigger_mode": "manual"})` 以區分排程自動觸發與手動觸發。
- **頁面位置**：確認後採用獨立 `/admin` 頁面（與 `/dashboard` 分開），需 admin scope API Key，
  提供任務清單、最新結果（成功/失敗徽章）、下次排定時間、錯誤訊息，以及每個任務的「立即執行」
  手動觸發按鈕。
- **資料庫變更方式**：與 HF-004（`companies.cik` 需手動執行 migration）不同，`job_runs` 是全新
  資料表，`app/db_session.py::init_db()` 呼叫的 `Base.metadata.create_all()` 會在下次應用程式啟動
  時自動建立，不需額外對正式資料庫手動執行 SQL。
- **驗證方式**：新增 10 項自動化測試（`track_job` 成功/失敗/手動觸發/upsert 各案例、
  `GET /api/v1/admin/jobs` 含執行結果與權限檢查、`/admin` 頁面路由），既有測試無回歸。

## REQ_014 補充說明：/admin 頁面帳號密碼登入

> 使用者升級 Render 方案、確認排程可穩定執行後，覺得 `/admin` 用貼 API Key 的方式不夠像正規後台
> 登入，要求改成帳號密碼（或 Google 帳號，兩者擇一，選了帳號密碼因為現在就能直接完成，不需要
> 使用者先去 Google Cloud Console 建 OAuth 憑證）。範圍確認僅限 `/admin` 頁面本身；`/dashboard`
> 與既有 REST API（`companies`/`predictions`）維持現有 `X-API-Key` 機制不變。

- **Session 機制**：Starlette 內建 `SessionMiddleware`（簽章 cookie，免建 session 資料表），密碼
  以 bcrypt 雜湊儲存於新資料表 `admin_users`。
- **既有 API 相容性**：`/api/v1/admin/jobs`、`/api/v1/admin/ingest/trigger` 改為「session 登入或
  admin scope API Key 擇一即可」（`require_admin_access`），而非完全捨棄 API Key，避免破壞既有
  REQ_008 定義之程式化呼叫端相容性；401/403 語意與既有 API Key 驗證一致（金鑰無效→401，scope
  不足→403）。
- **UX 流程**：頁面載入時不直接顯示排程表格，先呼叫 `GET /api/v1/auth/me` 靜默檢查既有 session；
  沒有則顯示登入卡片，登入成功才淡入顯示排程狀態表格與操作按鈕（符合使用者要求之「點擊按鈕後
  才可以出現」）。另提供「變更密碼」功能（重用既有 `.modal-overlay`/`.modal` 樣式），讓使用者能
  自行更換我透過對話明碼告知的初始密碼。
- **已知限制**：登入端點尚未實作失敗次數節流/帳號鎖定機制，詳見 `security_requirements.md`
  §五之二；Google 帳號登入選項因需使用者先行於 Google Cloud Console 建立 OAuth 憑證，本次未採用，
  日後如需要可在現有帳號密碼架構上以獨立登入方式並存加入。
- **驗證方式**：新增 13 項自動化測試（密碼雜湊 round-trip、登入成功/失敗/帳號不存在同訊息、
  `/me`、登出、變更密碼成功/失敗、session 不帶 API Key 也能存取排程端點、兩者皆無時拒絕），既有
  106 項測試無回歸；已對真實 Supabase 建立首筆帳號並實測登入/查詢/觸發/登出完整流程。

## REQ_015 補充說明：/dashboard 查詢公開化 + 移除 API Key 輸入（REQ_014 之延伸）

> 使用者要求 `/dashboard` 新增登入按鈕導向登入頁，並移除 API Key 輸入框。第一版實作將查詢類端點
> 全數改為需登入 session（沿用 REQ_014 之 `/admin` 帳密登入），經使用者實測後反饋「不需要登入也能
> 查看」，故調整為：**查詢/瀏覽公開、新增公司（寫入）仍需登入**。此為本專案至今唯一一次主動放寬
> （而非延伸強化）既有安全需求的決定，過程與理由完整記錄於 `security_requirements.md` §五之三、
> `threat_model.md` §三之三，比照 REQ_010~014 先例，未走完整 Phase 02→03 PDCA 順序、未建立獨立
> Baseline。

- **API 層**：新增 `app/auth.py::optional_read_access`，查詢類端點（公司清單/搜尋/財務/股價/預測/
  回測）不再要求任何憑證；若仍附帶 session 或 X-API-Key 則正常辨識並記錄稽核日誌之 `auth_method`
  （`session`/`apikey`/`anonymous`），主動附上但無效的 API Key 仍視為錯誤（401），不會被靜默當成
  匿名請求。`POST /api/v1/companies`（新增公司）與 `/api/v1/admin/*` 不受影響，維持原本
  `require_admin_access` 保護。
- **前端**：`dashboard.html`/`dashboard.js` 移除 API Key 輸入框與「連線」按鈕，改為「登入」/「登出」
  按鈕；頁面載入時一律嘗試載入公司資料（不再等待登入），登入狀態僅用於解鎖「新增公司」表單與顯示
  已登入帳號。「登入」按鈕導向 `/admin?next=/dashboard`，`admin.js` 新增 `safeNextPath()` 驗證
  `next` 僅接受站內相對路徑（防開放式導向），登入成功後自動導回。
- **順手修復一個既有缺陷**：實測時發現伺服器閒置一段時間後，第一個打向 Supabase 的請求會因連線池
  已關閉閒置連線而回 500（`psycopg.OperationalError: server closed the connection unexpectedly`）；
  `app/db_session.py::make_engine()` 原未開啟 `pool_pre_ping`，已修復。與本次功能異動關係不大，但為
  完整端到端驗證過程中發現的真實缺陷，一併記錄。
- **驗證方式**：修改/新增 4 項自動化測試（`test_auth.py` 2 項、`test_api_companies.py` 2 項、
  `test_api_predictions.py` 1 項，另有 1 項既有測試因行為改變而重寫斷言），既有 110 項測試無回歸，
  合計 114 項全數通過。另以全新（無 cookie/無 localStorage）headless Chrome 設定檔實測：未登入時
  `/dashboard` 正確顯示真實公司資料（台積電/Apple/SPCX），右上角正確顯示「登入」按鈕；匿名嘗試
  `POST /api/v1/companies` 正確回 401。
- **後續追加（2026-07-17，REQ_016 之後）**：使用者要求登入後能從 `/dashboard` 導向 `/admin`，
  提升雙向導覽的使用者體驗（`/admin` 原本就有「回財務儀表板」footer 連結，`/dashboard` 一直缺對應
  的反向連結）。在登入狀態列新增「後台管理」按鈕（`#admin-link-btn`），僅登入後顯示，點擊導向
  `/admin`。以 Puppeteer 驅動系統既有 Chrome 實測：未登入時按鈕隱藏、登入後正確顯示且點擊後真的
  導到 `/admin`。純前端改動，130 項既有測試無回歸（無新增測試，UI 顯示邏輯以瀏覽器實測驗證，比照
  REQ_010 先例）。

## REQ_016 補充說明：weekly_predict 排程真實邏輯（補完 REQ_004/005/006 斷鏈）

> 使用者要求確認 weekly_predict 排程是否已實作，得知仍為 stub 後要求補上。此為 out-of-band 追加，
> 比照 REQ_010~015 先例，未走完整 Phase 02→03 PDCA 順序、未建立獨立 Baseline。

- **特徵工程（新模組 `app/prediction/features.py`）**：財報因子模型（`factor_model.py`）本身是通用
  統計模型，不認識「財報」這個領域概念；新增 `compute_derived_features()` 由財報歷史算出 7 項衍生
  特徵（`revenue_yoy`/`eps_qoq`/`gross_margin`/`net_margin`/`debt_ratio`/
  `operating_cash_flow_yoy`/`pe_ratio`，符合 REQ_004 驗收條件），`compute_future_weekly_return_pct()`
  比對股價算出訓練標籤（財報公布日起算未來 5 個交易日報酬率）。
- **真實資料量限制（本次最重要的發現）**：財報因子模型統計設計要求至少 10 筆訓練樣本，但實際
  Supabase 目前僅有台積電 1 筆、Apple 2 筆財報（其餘 0 筆），且首筆財報連 YoY/QoQ 都算不出來（無
  前期資料可比對），實際可訓練樣本數是 0。財報一季才更新一次，這不是實作問題，是資料量尚未累積
  夠——單一公司要湊到 10 筆需 2.5 年以上歷史。
- **訓練樣本改採跨公司彙總（cross-sectional）**：不要求每家公司各自訓練，而是彙總全部追蹤公司的
  財報歷史一起訓練一個模型（`_train_pooled_factor_model`），讓門檻更快達成，且統計上也更合理
  （分位數迴歸本就偏好更大樣本）。
- **資料不足時的優雅降級（詢問使用者後之明確決策）**：財報因子模型不可訓練，或某公司當週推論特徵
  不可得時，`weekly_predict` 不會空手而回，也不會偽裝成雙模型融合結果，而是僅用時間序列模型
  （對真實股價資料已足夠，2330 有 51+ 筆、AAPL 有 100+ 筆，遠超過 30 天門檻）出預測，`model_version`
  明確加註 `-ts-only` 後綴、`factor_model_*` 欄位留空、`ensemble_weight_factor=0`，dashboard KPI 卡片
  也同步改為誠實顯示「僅時間序列模型（財報因子模型資料不足）」而非一律寫死「融合模型」。待財報歷史
  隨排程持續累積、跨公司彙總樣本數達 10 筆門檻，會在下一次執行時自動切換為真正的雙模型融合，
  不需要再次人工介入或部署新版本。
- **已知簡化（已於 2026-07-24 PATCH-002 補完）**：REQ_004 驗收條件提到模型應「版本化模型檔案」，
  理想設計是 `model_retrain`（週日 22:00 排程）負責訓練並持久化模型、`weekly_predict`（週一 01:00
  排程）僅載入既有模型做推論。本次（REQ_016，2026-07-17）僅實作 `weekly_predict`，尚未實作獨立的
  模型持久化/版本管理，改採簡化設計：每次執行皆即時重新訓練財報因子模型（不快取）。以當時資料量
  （訓練僅需毫秒等級）不構成效能問題；`model_retrain`/`weekly_backtest` 兩個排程任務仍維持 stub，
  不在本次範圍。**後續進展**：`weekly_backtest` 已於 PATCH-001（2026-07-24）補完；`model_retrain`
  已於 PATCH-002（同日）補完，新增 `trained_models` 表持久化模型，`weekly_predict` 改為優先讀取
  已持久化模型、找不到才 fallback 回本節所述之即時訓練，詳見 `06_maintenance/outputs/patch_changelog.md`。
- **一致性維護**：`_replace_prediction_for_week()` 會先刪除該公司當週既有預測再寫入最新一筆，維持
  「每家公司每週一筆」語意（例如透過 `/admin` 手動重觸發時不會產生重複列）；實作過程中發現並修復
  一個 SQLAlchemy flush 順序陷阱——同一次 flush 內先 `delete()` 再 `add()` 同一組唯一鍵的資料列，
  預設仍會先送出 INSERT 才送 DELETE，導致資料庫端誤觸唯一鍵衝突，已加上顯式 `session.flush()`
  修復（測試 `test_run_weekly_predict_rerun_replaces_same_week_prediction` 涵蓋此情境）。
- **驗證方式**：新增 16 項自動化測試（`test_prediction_features.py` 10 項、`test_jobs.py` 新增 6
  項，涵蓋特徵工程正確性、資料不足時的降級路徑、融合路徑、重觸發不重複、批次隔離單一公司失敗不
  中斷其餘公司），既有 114 項測試無回歸，合計 130 項全數通過。並以真實環境端到端驗證：透過
  `/admin` 手動觸發 `weekly_predict`，對台積電(2330)/Apple(AAPL) 真實資料成功產生
  `v1.0.0-ts-only` 預測並寫入 Supabase（SPCX 因無股價資料正確略過，未產生預測）；Chrome headless
  重新截圖確認 `/dashboard` 的「最新一週預測方向」等 KPI 卡片與股價圖預測區間正確顯示真實預測
  結果，且降級模式下標籤誠實顯示「僅時間序列模型」而非誤植「融合模型」。`ruff`/`bandit` 皆乾淨。

## 框架瑕疵回饋（詳見根目錄 `待辦事項.md`）

| # | 問題 | 影響 |
| :--- | :--- | :--- |
| 6 | `scripts/security/generate_sbom.py` 硬編碼裸 `pip` 指令，本環境無法使用 | SBOM 改手動產生等效輸出 |
| 7 | `scripts/security/install_hooks.py` 寫死指向框架自身倉庫路徑，無法用於獨立專案 | pre-commit hook 改手動安裝並驗證 |
| 8 | `scripts/security/run_security_scan.py` 硬編碼裸 `bandit`/`pip-audit` 指令，失敗時歸類為 `skip` 卻計入整體 `PASS`，形同靜默假通過 | 安全掃描改用 `python -m bandit`/`python -m pip_audit` 手動執行，結果見 `06_maintenance/outputs/security_trend.md` |
| 9 | `scripts/check_spec_integrity.py` 的 `--project` 相對路徑以框架自身 `ROOT` 而非執行時工作目錄解析，誤將專案外部路徑當成掃描目標 | 改用絕對路徑執行；掃描結果另外發現本專案 7 個階段皆缺 `inputs/spec_ref.md`（Phase 01 即已如此，非本次新增，未在本輪處理） |

## Phase 06 維護記錄摘要

> 2026-07-15 完成第一輪維護與營運週期，觸發原因：使用者提供真實 Supabase PostgreSQL + Alpha Vantage API Key 後，對台積電(2330)與 Apple(AAPL) 執行真實外部資料擷取，過程中發現並修復 3 個真實缺陷（HF-001/002/003，詳見 `06_maintenance/outputs/hotfix_log.md`）。回歸測試 71/71 通過，安全回歸檢查 100%（未下降）。詳見 `06_maintenance/outputs/regression_test_report.md`、`security_trend.md`、`monitoring_dashboard.md`。
