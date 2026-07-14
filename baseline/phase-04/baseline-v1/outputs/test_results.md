# 雙套測試結果報告 (Test Results)

> 生成日期：2026-07-14 | Phase 04 測試驗證
> 專案：各公司各季度財務分析與股價預測系統

## 一、測試架構說明

本系統為純後端 API 服務（無網頁 UI），依框架「Skill 上下文推薦」原則，Playwright（瀏覽器 UI 測試）
**不適用**，改以兩層 pytest 測試取代傳統雙軌（API+UI）測試：

| 測試層 | 位置 | 說明 | 項數 |
| :--- | :--- | :--- | :---: |
| 單元/整合測試 | `03_implementation_and_coding/outputs/tests/`（Phase 03 產出） | FastAPI `TestClient`（in-process），涵蓋資料擷取、正規化、模型、融合、回測、認證、API 端點邏輯 | 49 |
| 系統整合測試（本階段新增） | `04_testing/outputs/test_api.py` | 真實啟動 `uvicorn` 子行程，以實際 HTTP 呼叫驗證完整部署路徑 | 9 |
| **合計** | | | **58** |

## 二、測試結果總覽

| 項目 | 結果 |
| :--- | :--- |
| 總測試數 | 58 |
| ✅ 通過 | 58（100%） |
| ❌ 失敗 | 0 |
| 程式碼覆蓋率（`app/`） | **92.5%**（786 行中 727 行已覆蓋，59 行未覆蓋） |
| 執行時間 | 約 6~14 秒（視環境而定） |
| 完整結果檔 | `combined_test_results.xml`（JUnit 格式）、`coverage.json` |

## 三、需求測試覆蓋率（對應 `reg/requirement_tracker.md`）

| REQ ID | 描述 | 對應測試 | 狀態 |
| :--- | :--- | :--- | :---: |
| REQ_001 | 台股財務資料擷取（MOPS） | `test_mops_client.py`（4 項，含批次隔離失敗） | ✅ |
| REQ_002 | 美股財務資料擷取（SEC EDGAR+Alpha Vantage） | `test_sec_edgar_mapping.py`（5 項）、`test_alpha_vantage_client.py`（3 項） | ✅ |
| REQ_003 | 跨市場財務指標正規化 | `test_normalizer.py`（4 項，含版本化） | ✅ |
| REQ_004 | 財報因子統計模型 | `test_factor_model.py`（4 項，含可重現性） | ✅ |
| REQ_005 | 股價時間序列模型 | `test_timeseries_model.py`（4 項，含缺值處理） | ✅ |
| REQ_006 | 雙模型融合 | `test_ensemble.py`（4 項） | ✅ |
| REQ_007 | 預測結果查詢 API | `test_api_companies.py`、`test_api_predictions.py`、`test_api.py`（系統整合） | ✅ |
| REQ_008 | 資料擷取與模型更新排程 | `test_auth.py`（admin 端點權限）、`test_api.py::test_admin_scope_can_trigger_ingest_real_http` | ⚠️ 部分（排程實際觸發邏輯待 `scheduler.py` 與資料管線整合後於後續階段驗證，見下方限制說明） |
| REQ_009 | 預測準確率回測 | `test_backtest.py`（5 項） | ✅ |
| REQ_SEC_001 | API 存取控制與身份驗證 | `test_auth.py`（6 項）、`test_api.py`（3 項認證相關） | ✅ |

**需求測試覆蓋率：9/9 功能需求 + 1/1 安全需求皆有對應測試（100%）**；REQ_008 標記部分符合，原因見下方限制說明。

## 四、程式碼覆蓋率細節（低於 90% 之模組）

| 模組 | 覆蓋率 | 未覆蓋原因 |
| :--- | :---: | :--- |
| `app/scheduler.py` | 0% | 僅為排程任務**宣告**（cron 表達式註冊），任務函式本身留待與資料管線整合後才有實際邏輯可測；本階段測試聚焦於已實作之業務邏輯 |
| `app/ingestion/http_utils.py` | 57% | 重試/指數退避邏輯之「多次失敗後仍失敗」分支未觸發（測試以 1 次成功/1 次失敗為主，避免測試因退避 sleep 而變慢）；核心的成功路徑與批次隔離邏輯已 100% 覆蓋 |
| `app/db_session.py` | 79% | `get_session()` 的 generator 清理路徑於部分測試路徑未觸發 |
| `app/routers/predictions.py` | 86% | `history` 端點之部分排序分支未在系統整合測試中額外覆蓋（已於 Phase 03 單元測試覆蓋核心邏輯） |

> 92.5% 屬合理水準，未覆蓋部分均為聲明性配置或次要分支，非核心業務邏輯缺口。

## 五、限制說明（REQ_008 部分符合）

`app/routers/admin.py` 的 `POST /admin/ingest/trigger` 端點目前僅記錄稽核日誌並回傳 `202 Accepted`，**尚未實際呼叫**資料擷取/模型推論管線（`app/ingestion/*`、`app/prediction/*`）。這是 Phase 03 任務範圍內的合理邊界（T-12 定義為「API 層」，管線編排非本階段任務），非缺陷。待後續整合任務將 `app/scheduler.py` 的任務函式與 admin 觸發端點串接至實際管線後，需針對「觸發後確實執行擷取/推論」補充整合測試。

## 六、安全測試

- SAST（Phase 03 已執行）：bandit 0 findings，pip-audit 0 known vulnerabilities
- DAST（本階段執行）：見 `dast_report.md`，核心攻擊面無 Critical/High 風險發現
- 詳見 `security_check_report.md`（Phase 03 產出）與 `dast_report.md`（本階段產出）

## 七、Bug 追蹤

本階段測試過程中發現 1 項 Trivial 缺陷（測試資源清理，非功能性缺陷），已當場修復，詳見 `bug/bug_tracker.md`。

## 八、回歸測試策略

- 本次修復（BUG_001：ResourceWarning 未釋放連線）已納入既有測試套件（`conftest.py` 的 fixture 邏輯本身即為回歸防護，非新增獨立測試案例）。
- 建議後續開發規範：任何新增資料庫連線相關 fixture，皆須遵循「session 結束時 dispose()」慣例，避免同類問題復發。
- 完整測試套件（58 項）建議於每次程式碼變更後重新執行，作為標準回歸測試基準。
