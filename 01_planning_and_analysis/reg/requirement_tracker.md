# 需求追蹤表 (Requirement Tracker)

| REQ ID | 提出日期 | 來源 | 優先級 | 描述 | 對應設計 | 對應實作 | 對應測試 | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| REQ_001 | 2026-07-14 | 使用者口述 | P0 | 台股財務資料擷取（MOPS） | 待 Phase 02 | 待 Phase 03 | 待 Phase 04 | ✅ 已驗證 |
| REQ_002 | 2026-07-14 | 使用者口述 + 缺口拷問 | P0 | 美股財務資料擷取（SEC EDGAR + 市場資料 API） | 待 Phase 02 | 待 Phase 03 | 待 Phase 04 | ✅ 已驗證 |
| REQ_003 | 2026-07-14 | Planner 需求分析 | P0 | 跨市場財務指標正規化與儲存 | 待 Phase 02 | 待 Phase 03 | 待 Phase 04 | ✅ 已驗證 |
| REQ_004 | 2026-07-14 | 使用者口述 | P0 | 財報因子統計模型 | 待 Phase 02 | 待 Phase 03 | 待 Phase 04 | ✅ 已驗證 |
| REQ_005 | 2026-07-14 | 使用者口述 | P0 | 股價時間序列模型 | 待 Phase 02 | 待 Phase 03 | 待 Phase 04 | ✅ 已驗證 |
| REQ_006 | 2026-07-14 | Planner 需求分析 | P0 | 雙模型融合（Ensemble）與預測結果產出 | 待 Phase 02 | 待 Phase 03 | 待 Phase 04 | ✅ 已驗證 |
| REQ_007 | 2026-07-14 | 缺口拷問 | P0 | 預測結果查詢 API | 待 Phase 02 | 待 Phase 03 | 待 Phase 04 | ✅ 已驗證 |
| REQ_008 | 2026-07-14 | Planner 需求分析 | P1 | 資料擷取與模型更新排程機制 | 待 Phase 02 | 待 Phase 03 | 待 Phase 04 | ✅ 已驗證 |
| REQ_009 | 2026-07-14 | Planner 需求分析 | P1 | 預測準確率回測與追蹤報告 | 待 Phase 02 | 待 Phase 03 | 待 Phase 04 | ✅ 已驗證 |
| REQ_SEC_001 | 2026-07-14 | 資安基準（中級） | P0 | API 存取控制與身份驗證 | 待 Phase 02 | 待 Phase 03 | 待 Phase 04 | ✅ 已驗證 |
| REQ_011 | 2026-07-15 | 使用者口述（out-of-band，比照 REQ_010） | P1 | 使用者可透過 UI/API 新增追蹤公司（台股/美股），美股未提供 CIK 時自動以 SEC ticker 對照表查詢；一併補完 mops_ingest/sec_edgar_ingest/price_ingest 三個排程任務的真實擷取邏輯 | `02_system_design/outputs/api_spec.md` | `app/routers/companies.py`, `app/ingestion/sec_edgar_client.py`, `app/jobs.py` | `tests/test_api_companies.py`, `tests/test_cik_lookup.py`, `tests/test_jobs.py` | ✅ 已驗證 |
| REQ_012 | 2026-07-15 | 使用者口述（out-of-band，REQ_011 之延伸） | P2 | 新增追蹤公司時，股票代碼與公司名稱擇一輸入即可，並以字串包含比對（大小寫不敏感）方式模糊搜尋候選公司；台股重用既有 TWSE 損益表端點作為目錄，美股重用既有 SEC ticker 對照表 | `02_system_design/outputs/api_spec.md` | `app/routers/companies.py`(`GET /search`), `app/ingestion/mops_client.py`, `app/ingestion/sec_edgar_client.py` | `tests/test_api_companies.py`, `tests/test_mops_client.py`, `tests/test_cik_lookup.py` | ✅ 已驗證 |
| REQ_013 | 2026-07-15 | 使用者口述（out-of-band） | P1 | 新增獨立 `/admin` 頁面檢視 6 個排程任務之下次執行時間與最新一次執行結果（成功/失敗、觸發方式、錯誤訊息），並可手動立即觸發任務 | `02_system_design/outputs/api_spec.md` | `app/db_models.py`(`JobRun`), `app/jobs.py`(`track_job`), `app/routers/admin.py`, `app/static/admin.{html,js}` | `tests/test_jobs.py`, `tests/test_admin_jobs.py`, `tests/test_admin_page.py` | ✅ 已驗證 |

## grill-me 缺口拷問記錄

見 `grill_me_session.md`（本次以對話形式進行，摘要記錄於下）：

1. **缺口**：美股資料來源未定義（MOPS 僅涵蓋台股）。
   **結論**：美股財報改用 SEC EDGAR，股價與市場資料改用市場資料 API（供應商於 Phase 02 選型，記錄為 OI-001）。
2. **缺口**：股價預測輸出格式未定義（絕對數值？報酬率？方向？）。
   **結論**：確定為「未來一週漲跌方向 + 幅度區間」。
3. **缺口**：系統呈現形式未定義，影響 Phase 02 是否需要 UI 設計。
   **結論**：確定為後端分析服務 + API，本期不含網頁儀表板。
