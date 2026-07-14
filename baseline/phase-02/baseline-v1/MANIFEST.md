# Phase 02 Baseline — v1

- **建立時間**：2026-07-14T02:00:00
- **階段**：02_system_design（系統設計）
- **Evaluator 評分**：coverage 96 / clarity 93 / traceability 94 / format 95 / security_coverage 92
- **關鍵設計決策**：
  - 資料庫：PostgreSQL，7 張資料表（見 `db_schema.sql`）
  - API：7 個端點，API Key 認證（read/admin scope）
  - 市場資料 API 供應商：Alpha Vantage（OI-001 已解決）
  - 不含網頁 UI（系統定位為後端分析服務 + API）
- **威脅建模**：已完成 STRIDE 分析，涵蓋構面 1/4/6

## 檔案清單與 SHA-256

| 檔案 | SHA-256 |
| :--- | :--- |
| outputs/db_schema.sql | 571473b1c545f5e343c47e4997c6ad75e0cfee11b8a865b61ea730b56d5abcf7 |
| outputs/er_diagram.md | e0939abb5e5df4b646572783ab5c06dd777543435aa0688d942bd3cb4fe8bef2 |
| outputs/api_spec.md | ef06185bd57f22ae14709c3c488467e0d438152e26b7259dc4d6852486a98ff0 |
| outputs/usecase_diagram.md | 1d6016960572be59cb8eab8bacd72c05b779b9c3bc959251a27cc3a5723582ef |
| outputs/activity_diagram.md | 4f56876b0a5f8601fb4e920d01eb2cf34e4e7571cb4efd72eda878f6b342bba4 |
| outputs/sequence_diagram.md | 9ec166a7dd2df464db93c446d68292bb91f40f43b196ece9f1bdfb24402c1eb1 |
| outputs/threat_model.md | a94caf7778483b38e180140ef27275f437c5be96c48563d4a60d43b5bbe165b3 |
| SKILL.md | abe1921584d3631d13290f0bef7974307197ef38858aa94594e22cff2da52407 |

> 注意：專案尚未初始化 Git 倉庫，無 Git commit hash 可記錄，建議儘早 `git init`。

## 備註

本階段為設計文件階段，無可執行程式碼，故不適用「服務啟動與 HTTP 回應檢查」等執行期驗證項目。UI 雛型（`ui_prototype.html`）依 Planner 判定與使用者確認為非必要產出（系統為純後端服務），故未產出，非缺漏。
