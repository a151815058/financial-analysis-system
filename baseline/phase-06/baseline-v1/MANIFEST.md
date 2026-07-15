# Phase 06 Baseline — v1

- **建立時間**：2026-07-15T00:00:00
- **階段**：06_maintenance（維護與營運，第一輪）
- **Evaluator 評分**：回歸測試完整性 30/30、監控有效性 19/25、錯誤萃取準確性 21/25、產出物驗證 10/10、安全維護有效性 10/10（加權總分 90）

## 觸發情境

使用者提供真實 Supabase PostgreSQL 連線與 Alpha Vantage API Key，對台積電（2330）、Apple（AAPL）執行真實外部資料擷取（MOPS/TWSE/SEC EDGAR/Alpha Vantage），過程中發現並修復 3 項真實缺陷。

## 已完成的真實驗證

| 驗證項目 | 方法 | 結果 |
| :--- | :--- | :--- |
| 3 項熱修補 | 真實外部 API 呼叫觸發，修復後補上單元測試 | ✅ HF-001/002/003 皆修復並驗證，見 `outputs/hotfix_log.md` |
| 回歸測試 | 71 項（62 單元/整合 + 9 系統整合，真實 HTTP 子行程） | ✅ 71/71 通過，覆蓋率 92% |
| 安全回歸 | `python -m bandit` + `python -m pip_audit`（手動執行，繞過框架腳本瑕疵） | ✅ 0 HIGH/MEDIUM、專案實際 21 個相依套件 0 已知漏洞 |
| 真實資料端到端 | 台積電/Apple 財報+股價寫入 Supabase，經 API 與瀏覽器儀表板驗證 | ✅ 可正確呈現 |
| Phase 05 回頭補驗證 | 資料庫連線與 schema 套用改用真實 Supabase | ✅ `phase_gates.json` 05_deployment.availability_check 18→22 |

## 誠實揭露：評分未達滿分之項目

- **監控有效性（19/25）**：`monitoring_dashboard.md` 為基於 `audit_logs`/`predictions` 表之 SQL 查詢與閾值建議設計，本環境無 Docker/Prometheus/Grafana/Sentry 等 APM 平台，**非實際運作中的即時告警系統**，故未給滿分
- **錯誤萃取準確性（21/25）**：根本原因分析已完整記錄於 `outputs/hotfix_log.md`（每項熱修補皆有「發現方式/根本原因/影響範圍/修補方案/驗證」結構），但依 `06_maintenance/io_files.yaml` 現行 IO 合約未要求獨立的 `incident_report.md`，分析內容整併於 hotfix_log 而非獨立文件，故未給滿分

## 未能驗證項目（需真實 Docker/APM 環境）

- 容器化部署（`docker build`/`docker compose up`）與 nginx 反向代理仍未驗證（沿用 Phase 05 已知限制）
- 監控告警機制未接上實際運作中的 APM 平台，僅為查詢定義與閾值建議
- `predictions`/`prediction_backtests` 尚無真實資料，模型準確率追蹤查詢已就緒但無資料可驗證

## 框架瑕疵發現（已回報至根目錄 `待辦事項.md`）

| # | 腳本 | 問題 |
| :--- | :--- | :--- |
| 8 | `scripts/security/run_security_scan.py` | 硬編碼裸 `bandit`/`pip-audit` 指令，失敗時歸類為 `skip` 卻計入整體 `PASS`，形同靜默假通過 |

已改為手動以 `python -m bandit`/`python -m pip_audit` 執行等效操作，不影響本階段安全回歸檢查之實質內容。

## 檔案雜湊清單

見同目錄 `MANIFEST_hashes.txt`（4 個檔案 SHA-256）。

## 建議

1. 待使用者決定執行模型預測流程後，回頭驗證 `monitoring_dashboard.md` §4 之準確率查詢
2. 若未來取得 Docker 環境，應同時補做 Phase 05 容器化驗證與 Phase 06 即時監控平台串接
3. `scripts/security/run_security_scan.py`（框架瑕疵 #8）修正後，應改回使用框架標準流程執行安全掃描
