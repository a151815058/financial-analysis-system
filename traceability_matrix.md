# 需求追溯矩陣 (Requirements Traceability Matrix - RTM)

> 專案：各公司各季度財務分析與股價預測系統
> 最後更新：2026-07-15

| 需求編號 | 原始輸入來源 | 規格定義 (01) | 系統設計 (02) | 開發實作 (03) | 測試案例 (04) | 部署驗證 (05) | 維護記錄 (06) | 當前狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| REQ_001 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_001 | `db_schema.sql`(financial_reports)<br>`api_spec.md`(financials) | `app/ingestion/mops_client.py`（HF-001 改用 TWSE OpenAPI 重寫） | `tests/test_mops_client.py`（5 項）+ 真實台積電(2330)資料擷取寫入 Supabase | `docker-compose.yml`(app 服務)、`deployment_config.md`（DB 已真實驗證） | `06_maintenance/outputs/hotfix_log.md`（HF-001） | `[已驗證]` |
| REQ_002 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_002 | `db_schema.sql`(financial_reports,source=SEC_EDGAR)<br>`api_spec.md`(financials) | `app/ingestion/sec_edgar_client.py`（HF-002 單季/累計修正）、`app/ingestion/alpha_vantage_client.py`（HF-003 Information 訊息） | `tests/test_sec_edgar_mapping.py`（8 項）、`tests/test_alpha_vantage_client.py`（4 項）+ 真實 Apple(AAPL)資料擷取寫入 Supabase | `docker-compose.yml`(app 服務，環境變數注入金鑰) | `06_maintenance/outputs/hotfix_log.md`（HF-002、HF-003） | `[已驗證]` |
| REQ_003 | Planner 需求分析 | `formal_requirements.md` §REQ_003 | `er_diagram.md`(companies/financial_reports) | `app/ingestion/normalizer.py` | `tests/test_normalizer.py`（4） | `db_schema.sql` 掛載為 Postgres 初始化腳本，已於 Supabase 實際套用 | `06_maintenance/outputs/regression_test_report.md` | `[已驗證]` |
| REQ_004 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_004 | `db_schema.sql`(predictions.factor_model_*)<br>`activity_diagram.md` | `app/prediction/factor_model.py`（解決 OI-003） | `tests/test_factor_model.py`（4） | 隨 app 容器部署（未單獨拆分服務） | `06_maintenance/outputs/monitoring_dashboard.md`（`predictions` 表現況為空，待執行預測） | `[不連貫警告]`（模型尚未對真實資料執行，見 monitoring_dashboard.md §4） |
| REQ_005 | `inputs/user_requirement_raw.md` | `formal_requirements.md` §REQ_005 | `db_schema.sql`(price_history, predictions.timeseries_model_*) | `app/prediction/timeseries_model.py`；股價真實資料已由 REQ_001/002 補齊（TW 50 筆、US 100 筆） | `tests/test_timeseries_model.py`（4） | 隨 app 容器部署 | `06_maintenance/outputs/monitoring_dashboard.md` | `[不連貫警告]`（模型尚未對真實資料執行） |
| REQ_006 | Planner 需求分析 | `formal_requirements.md` §REQ_006 | `db_schema.sql`(predictions.ensemble_weight_*)<br>`sequence_diagram.md` | `app/prediction/ensemble.py` | `tests/test_ensemble.py`（4） | 隨 app 容器部署 | `06_maintenance/outputs/monitoring_dashboard.md` | `[不連貫警告]`（模型尚未對真實資料執行） |
| REQ_007 | 缺口拷問 | `formal_requirements.md` §REQ_007 | `api_spec.md`（6 個查詢端點） | `app/routers/companies.py`、`app/routers/predictions.py` | `tests/test_api_companies.py`、`tests/test_api_predictions.py`、`04_testing/outputs/test_api.py`（系統整合，真實 HTTP）+ 真實 Supabase 資料 API 讀取驗證 | `nginx.conf`（反向代理對外唯一入口） | `06_maintenance/outputs/monitoring_dashboard.md`（API 稽核事件監控，§3） | `[已驗證]` |
| REQ_008 | Planner 需求分析 | `formal_requirements.md` §REQ_008 | `api_spec.md`(POST /admin/ingest/trigger)<br>`activity_diagram.md` | `app/routers/admin.py`、`app/scheduler.py`、`app/main.py`（scheduler 啟動/關閉）、`app/jobs.py`（REQ_011 追加：mops_ingest/sec_edgar_ingest/price_ingest 真實邏輯；weekly_predict/model_retrain/weekly_backtest 仍為 stub） | `tests/test_auth.py`、`test_api.py::test_admin_scope_can_trigger_ingest_real_http`、`tests/test_jobs.py`（REQ_011） | 排程隨 app 容器啟動（同進程 APScheduler） | `06_maintenance/outputs/monitoring_dashboard.md` §2（排程健康度監控已設計）；REQ_011 已解除資料擷取 3 任務的管線斷鏈 | `[已驗證]`（資料擷取 3 任務已串接；模型類 3 任務仍為已知限制，見 `04_testing/outputs/test_results.md` §五） |
| REQ_009 | Planner 需求分析 | `formal_requirements.md` §REQ_009 | `db_schema.sql`(prediction_backtests)<br>`api_spec.md`(backtest) | `app/prediction/backtest.py`、`app/routers/predictions.py` | `tests/test_backtest.py`（5）、`tests/test_api_predictions.py` | 隨 app 容器部署 | `06_maintenance/outputs/monitoring_dashboard.md` §4（`prediction_backtests` 現況為空） | `[不連貫警告]`（待有真實預測/回測資料） |
| REQ_SEC_001 | 資安基準（中級） | `security_requirements.md` §五 | `db_schema.sql`(api_keys,audit_logs)<br>`threat_model.md` | `app/auth.py`、`app/audit.py`（含 source_ip 修復）；本次以真實 API Key 驗證 | `tests/test_auth.py`（7）、`04_testing/outputs/dast_report.md`（DAST） | `nginx.conf`（TLS/安全標頭）、`security_deployment_checklist.md`、`signature_status.json` | `06_maintenance/outputs/security_trend.md`（100%，未下降） | `[已驗證]` |
| REQ_010 | 使用者口述（Phase 05 後追加，Phase 06 前） | 補於本文件 | 無獨立設計文件（沿用既有 API 端點，未另建 UI 雛型） | `app/static/dashboard.{html,css,js}`、`app/main.py`（`/dashboard`、`/static` 掛載） | `tests/test_dashboard.py`（3 項）+ 真實瀏覽器驗證（Chrome headless + Puppeteer，見下方說明）+ 本次以真實瀏覽器視窗顯示台積電/Apple 真實資料 | 隨 app 容器一併部署（無獨立服務） | `06_maintenance/outputs/regression_test_report.md`（`test_dashboard.py` 3 項無回歸） | `[已驗證]` |
| REQ_011 | 使用者口述（Phase 06 後追加，out-of-band） | 補於本文件、`01_planning_and_analysis/reg/requirement_tracker.md` | `api_spec.md`(POST /api/v1/companies)<br>`threat_model.md` §三之一 | `app/routers/companies.py`（POST 端點）、`app/schemas.py`（`CompanyCreateRequest`）、`app/ingestion/sec_edgar_client.py`（`lookup_cik`）、`app/jobs.py`（新檔）、`app/static/dashboard.{html,css,js}`（新增公司表單） | `tests/test_api_companies.py`（新增 6 項）、`tests/test_cik_lookup.py`（4 項）、`tests/test_jobs.py`（3 項） | 隨 app 容器一併部署（無獨立服務）；排程任務現會真實呼叫外部 API，見 §五之提醒 | 補於本文件下方「REQ_011 補充說明」 | `[已驗證]` |
| REQ_012 | 使用者口述（REQ_011 之延伸，out-of-band） | 補於本文件、`01_planning_and_analysis/reg/requirement_tracker.md` | `api_spec.md`(GET /api/v1/companies/search) | `app/routers/companies.py`(`GET /search`)、`app/ingestion/mops_client.py`(`search_companies`，重用既有損益表端點)、`app/ingestion/sec_edgar_client.py`(`search_companies`，擴充既有 ticker 對照表快取)、`app/static/dashboard.{html,css,js}`（新增公司表單改為代碼/名稱擇一輸入之搜尋建議） | `tests/test_api_companies.py`（新增 3 項）、`tests/test_mops_client.py`（新增 4 項）、`tests/test_cik_lookup.py`（新增 4 項） | 隨 app 容器一併部署（無獨立服務） | 補於本文件下方「REQ_012 補充說明」 | `[已驗證]` |
| REQ_013 | 使用者口述（out-of-band） | 補於本文件、`01_planning_and_analysis/reg/requirement_tracker.md` | `api_spec.md`(GET /api/v1/admin/jobs、GET /admin) | `app/db_models.py`(`JobRun`)、`app/jobs.py`(`track_job`)、`app/routers/admin.py`(`GET /jobs` 擴充、`trigger_ingest` 帶 `trigger_mode`)、`app/static/admin.{html,js}`（新頁面）、`app/main.py`(`GET /admin` 路由、`job_functions` 全數包上 `track_job`) | `tests/test_jobs.py`（新增 4 項）、`tests/test_admin_jobs.py`（3 項）、`tests/test_admin_page.py`（3 項） | 隨 app 容器一併部署（無獨立服務）；`job_runs` 為新資料表，`init_db()` 之 `Base.metadata.create_all` 於下次啟動時自動建立，無需手動 migration（與 HF-004 之 ALTER TABLE 情境不同） | 補於本文件下方「REQ_013 補充說明」 | `[已驗證]` |
| REQ_014 | 使用者口述（out-of-band，REQ_013 之延伸） | 補於本文件、`01_planning_and_analysis/reg/requirement_tracker.md` | `api_spec.md`(/api/v1/auth/*)、`threat_model.md` §三之二 | `app/auth.py`(`hash_password`/`verify_password`/`require_admin_access`/`require_session_login`)、`app/routers/auth.py`（新檔）、`app/db_models.py`(`AdminUser`)、`app/main.py`(`SessionMiddleware`)、`app/static/admin.{html,js}`（登入卡片、變更密碼 modal） | `tests/test_api_auth.py`（10 項）、`tests/test_admin_jobs.py`（新增 3 項） | 隨 app 容器一併部署；`admin_users` 為新資料表，`init_db()` 自動建立，無需手動 migration | 補於本文件下方「REQ_014 補充說明」 | `[已驗證]` |
| REQ_015 | 使用者口述（out-of-band，REQ_014 之延伸） | 補於本文件、`01_planning_and_analysis/reg/requirement_tracker.md`、`security_requirements.md` §五之三（風險接受） | `api_spec.md`(一、認證與授權 REQ_015 註記)、`threat_model.md` §三之三 | `app/auth.py`(`optional_read_access`/`OptionalReadAccessContext`)、`app/routers/companies.py`、`app/routers/predictions.py`、`app/static/dashboard.{html,js}`（移除 API Key 輸入框，改登入/登出按鈕）、`app/static/admin.js`(`safeNextPath`，`?next=` 安全導回)、`app/db_session.py`(`pool_pre_ping`，順手修復 Supabase 閒置斷線) | `tests/test_auth.py`（改寫 2 項）、`tests/test_api_companies.py`（改寫 1 項、新增 2 項）、`tests/test_api_predictions.py`（新增 1 項） | 隨 app 容器一併部署（無獨立服務） | 補於本文件下方「REQ_015 補充說明」 | `[已驗證]` |

> 說明：`[不連貫警告]` 為框架標準狀態標記，表示該需求尚未貫穿所有階段。Phase 06（維護與營運）已於 2026-07-15 完成第一輪，REQ_001/002/003/007/SEC_001/010 已因本輪真實資料擷取與熱修補而更新為 `[已驗證]`；REQ_004/005/006/009 仍標記 `[不連貫警告]`，原因是模型預測/回測尚未對真實資料執行（非監控或測試機制缺陷，見 `06_maintenance/outputs/monitoring_dashboard.md`）。REQ_008 已因 REQ_011（同日 out-of-band 追加）補齊 3 個資料擷取任務的真實邏輯而更新為 `[已驗證]`，模型類任務的限制併入 REQ_004/005/006 之既有已知限制範圍，不再視為 REQ_008 本身之缺口。
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

## 框架瑕疵回饋（詳見根目錄 `待辦事項.md`）

| # | 問題 | 影響 |
| :--- | :--- | :--- |
| 6 | `scripts/security/generate_sbom.py` 硬編碼裸 `pip` 指令，本環境無法使用 | SBOM 改手動產生等效輸出 |
| 7 | `scripts/security/install_hooks.py` 寫死指向框架自身倉庫路徑，無法用於獨立專案 | pre-commit hook 改手動安裝並驗證 |
| 8 | `scripts/security/run_security_scan.py` 硬編碼裸 `bandit`/`pip-audit` 指令，失敗時歸類為 `skip` 卻計入整體 `PASS`，形同靜默假通過 | 安全掃描改用 `python -m bandit`/`python -m pip_audit` 手動執行，結果見 `06_maintenance/outputs/security_trend.md` |
| 9 | `scripts/check_spec_integrity.py` 的 `--project` 相對路徑以框架自身 `ROOT` 而非執行時工作目錄解析，誤將專案外部路徑當成掃描目標 | 改用絕對路徑執行；掃描結果另外發現本專案 7 個階段皆缺 `inputs/spec_ref.md`（Phase 01 即已如此，非本次新增，未在本輪處理） |

## Phase 06 維護記錄摘要

> 2026-07-15 完成第一輪維護與營運週期，觸發原因：使用者提供真實 Supabase PostgreSQL + Alpha Vantage API Key 後，對台積電(2330)與 Apple(AAPL) 執行真實外部資料擷取，過程中發現並修復 3 個真實缺陷（HF-001/002/003，詳見 `06_maintenance/outputs/hotfix_log.md`）。回歸測試 71/71 通過，安全回歸檢查 100%（未下降）。詳見 `06_maintenance/outputs/regression_test_report.md`、`security_trend.md`、`monitoring_dashboard.md`。
