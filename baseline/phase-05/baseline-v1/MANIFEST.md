# Phase 05 Baseline — v1

- **建立時間**：2026-07-14T04:45:00
- **階段**：05_deployment（部署發布）
- **Evaluator 評分**：config_baseline_integrity 27 / availability_check 18 / signature_verification 6 / config_correctness 6 / deployment_security 9（加權總分 66）

## ⚠️ 誠實揭露：本 Baseline 未經真實基礎設施驗證

本機開發環境**未安裝 Docker、nginx、PostgreSQL**。本階段產出之 `Dockerfile`、`docker-compose.yml`、
`nginx.conf` 為依標準實踐撰寫，**未經 `docker build`／`docker compose up`／`nginx -t` 實際執行驗證**。
加權總分 66（低於前四階段）如實反映此限制，非計算錯誤或評分寬鬆。

## 已完成的真實驗證（不依賴 Docker）

| 驗證項目 | 方法 | 結果 |
| :--- | :--- | :--- |
| 建置產物完整性 | 產生 `build_manifest.json`（33 檔 SHA-256）後重新計算比對 | ✅ 全數一致 |
| 應用程式健康檢查 | 直接以 `uvicorn` 啟動（非容器化），`curl /health` | ✅ 200 OK |
| Secret 掃描 pre-commit hook | 手動安裝至 `.git/hooks/pre-commit`，以含偽造 API Key 之測試檔實際觸發 `git commit` | ✅ 確認攔截（`BLOCKED: 2 potential secret(s)`） |
| PostgreSQL 驅動可安裝性 | `pip install psycopg[binary]` + SQLAlchemy `create_engine()` 建立引擎（未實際連線） | ✅ 安裝成功、引擎建立成功 |

## 未能驗證項目（需真實 Docker/PostgreSQL 環境）

- `docker build` / `docker compose up` 實際執行結果
- `nginx -t` 語法驗證與反向代理實際轉發
- PostgreSQL 實際連線與 `db_schema.sql` 於 Postgres 環境執行
- 容器化服務之 Health Check 煙霧測試
- 正式 TLS 憑證、資料庫備份排程（RPO/RTO）

## 框架瑕疵發現（已回報至根目錄 `待辦事項.md`）

| # | 腳本 | 問題 |
| :--- | :--- | :--- |
| 6 | `scripts/security/generate_sbom.py` | 硬編碼裸 `pip` 指令，本環境（僅 `python -m pip` 可用）靜默失敗 |
| 7 | `scripts/security/install_hooks.py` | 寫死指向框架自身倉庫路徑，無法用於獨立專案 |

兩者皆已改為手動等效操作完成，不影響本階段產出之實質內容。

## 檔案雜湊清單

見同目錄 `MANIFEST_hashes.txt`（10 個檔案 SHA-256）。

## 建議

正式上線前，務必於具備 Docker 之環境重新執行本 Baseline 之驗證項目，尤其是「未能驗證項目」章節列出之 5 項。
