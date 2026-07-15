# 回歸測試報告 (Regression Test Report)

> 生成日期：2026-07-15 | Phase 06 維護與營運
> 觸發原因：`06_maintenance/hotfix_log.md` 記錄之 3 項熱修補（HF-001/002/003），依 SKILL.md 規範「每次維護變更後強制執行回歸測試」

## 一、結果總覽

| 測試層 | 位置 | 項數 | 結果 |
| :--- | :--- | :---: | :---: |
| 單元/整合測試 | `03_implementation_and_coding/outputs/tests/` | 62 | ✅ 62/62（100%） |
| 系統整合測試（真實 HTTP 子行程） | `04_testing/outputs/test_api.py` | 9 | ✅ 9/9（100%） |
| **合計** | | **71** | ✅ **71/71（100%）** |
| 程式碼覆蓋率（`app/`） | | | 92%（877 行中 66 行未覆蓋） |
| Ruff 靜態檢查 | 全域 | — | ✅ 全數通過 |

**基準比較**：Phase 04 完成時為 58 項（49 單元 + 9 系統整合），REQ_010 儀表板追加後為 61 項（52 + 9）。本次 3 項熱修補淨增 10 項單元測試（TWSE 新模組 5 項、MOPS 全改寫淨增 1 項、SEC EDGAR 累計/單季區分新增 3 項、Alpha Vantage Information 訊息新增 1 項），系統整合層 9 項未變動，**無測試被刪除或跳過，無既有功能被破壞**。

## 二、本次修補回歸驗證重點

| 熱修補 | 對應回歸測試 | 驗證結論 |
| :--- | :--- | :--- |
| HF-001（MOPS 端點重寫） | `test_mops_client.py`（5 項） | 三端點合併邏輯、期別不符防呆、資產負債表缺漏容錯、批次隔離皆通過；並以台積電真實資料完整跑過寫入流程 |
| HF-002（SEC EDGAR 單季/累計混淆） | `test_sec_edgar_mapping.py`（8 項，含 3 項新增） | 既有 5 項備援標籤邏輯測試全數通過（無回歸），新增 3 項驗證單季優先、累計限定情境誠實回傳 None、即時性數值不受影響 |
| HF-003（Alpha Vantage Information 訊息） | `test_alpha_vantage_client.py`（4 項，含 1 項新增） | 既有速率限制/錯誤訊息/批次隔離測試通過，新增測試驗證 `Information` 鍵正確觸發例外 |

## 三、覆蓋率細節（未覆蓋部分說明）

| 檔案 | 覆蓋率 | 未覆蓋原因 |
| :--- | :---: | :--- |
| `app/scheduler.py` | 0% | 排程任務註冊介面，實際觸發邏輯依 REQ_008 規劃留待與資料管線整合後於後續維護週期驗證（Phase 04 報告已知限制，非本次回歸新增缺口） |
| `app/ingestion/http_utils.py` | 57% | 未覆蓋行為重試失敗後之例外堆疊路徑（`exhausted retries` 分支），因需真實網路逾時情境觸發，單元測試以 mock 覆蓋主要邏輯已足夠 |
| `app/routers/predictions.py` | 86% | 未覆蓋部分為尚無真實 `predictions`/`prediction_backtests` 資料時的邊界回應（本次 session 未執行模型預測，屬預期缺口） |

上述未覆蓋項目皆為既有已知限制，非本次熱修補引入之新缺口。

## 四、真實環境端到端驗證（非僅單元測試）

本次除自動化測試外，另以真實外部服務與真實 Supabase PostgreSQL 完成端到端驗證（詳見 `06_maintenance/outputs/hotfix_log.md` 與 `memory.md`）：

- 台積電（2330）：真實 MOPS（TWSE OpenAPI）財報 + TWSE 股價，已寫入 Supabase 並經 API 讀取驗證
- Apple（AAPL）：真實 SEC EDGAR 財報 + Alpha Vantage 股價，已寫入 Supabase 並經 API 讀取驗證
- `/dashboard` 前端已於真實瀏覽器視窗確認可正確呈現上述真實資料

## 五、結論

回歸測試完整性達成 SKILL.md 審查標準「確認修補後系統既有功能皆未損壞」。**無 A 類或 B 類錯誤**，本次維護變更可視為驗收通過。
