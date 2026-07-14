# 部署安全檢核表 (Security Deployment Checklist)

> 生成日期：2026-07-14 | Phase 05 部署發布
> 適用構面：構面 3（營運持續計畫）、構面 6（系統與通訊保護）

## 一、TLS / 憑證

| 項目 | 狀態 | 說明 |
| :--- | :---: | :--- |
| 全站 HTTPS 導向（HTTP→HTTPS 301） | ✅ 已設定 | `nginx/nginx.conf` |
| TLS 版本限制（僅 1.2/1.3） | ✅ 已設定 | `ssl_protocols TLSv1.2 TLSv1.3;` |
| 強密碼套件 | ✅ 已設定 | `ssl_ciphers HIGH:!aNULL:!MD5;` |
| 正式憑證取得與掛載 | ⏳ 待辦 | 本階段僅提供占位路徑 `/etc/nginx/certs/`；正式憑證建議使用 Let's Encrypt（`certbot`）或機關內部 CA，掛載至該路徑 |
| HSTS 標頭 | ✅ 已設定 | `Strict-Transport-Security: max-age=63072000` |

## 二、Secret 管理

| 項目 | 狀態 | 說明 |
| :--- | :---: | :--- |
| API 金鑰/資料庫密碼一律環境變數注入 | ✅ 已設計 | `docker-compose.yml` 使用 `${VAR}` 語法，未寫死於程式碼或 Dockerfile |
| `.env` 已列入 `.gitignore` | ✅ 已確認 | 專案根 `.gitignore` 已含 `.env` |
| 提供 `.env.example`（不含真實密鑰） | ✅ 已提供 | `05_deployment/outputs/.env.example`、`03_implementation_and_coding/outputs/.env.example` |
| 資料庫連線字串不明文寫入設定檔 | ✅ 已確認 | 透過 `DATABASE_URL` 環境變數組裝，含密碼部分僅存在於執行時環境變數 |
| Git pre-commit hook 防止密鑰誤入版控 | ✅ 已安裝並實測驗證 | 框架內建 `scripts/security/install_hooks.py` 因寫死指向框架自身倉庫路徑而無法直接用於獨立專案（已記錄於根目錄 `待辦事項.md` #7），故手動安裝等效 hook 至 `.git/hooks/pre-commit`，並以真實測試檔（含偽造 API Key 樣式字串）驗證：`git commit` 確實被攔截（`BLOCKED: 2 potential secret(s)`） |
| API Key（應用層）僅存雜湊值 | ✅ 已確認（Phase 03） | `api_keys.key_hash`（SHA-256），非明文 |

## 三、防火牆規則 / 網路隔離

| 項目 | 狀態 | 說明 |
| :--- | :---: | :--- |
| 資料庫不對外開放埠口 | ✅ 已設計 | `docker-compose.yml` 中 `db` 服務僅在 `internal` network，無 `ports` 對外映射 |
| `app` 服務不直接對外開放 | ✅ 已設計 | 使用 `expose: "8000"`（僅 compose 內部網路可見），對外唯一入口為 `nginx` 的 443/80 |
| 僅 nginx 對外開放埠口 | ✅ 已設計 | `docker-compose.yml` 僅 `nginx` 有 `ports` 映射 |

## 四、備份與營運持續（構面 3）

| 項目 | 狀態 | 說明 |
| :--- | :---: | :--- |
| RPO（可容忍資料損失時間）定義 | ⏳ 待辦 | 建議定義為 24 小時（每日備份），視實際營運需求調整 |
| RTO（最大可容忍中斷時間）定義 | ⏳ 待辦 | 建議定義為 4 小時 |
| 資料庫備份排程 | ⏳ 待辦 | 建議使用 `pg_dump` 排程（cron 或 APScheduler 任務）+ 異地存放（見待辦事項） |
| 備份還原測試 | ⏳ 待辦 | 待實際部署環境建立後執行還原演練 |
| 系統備援機制 | ⏳ 待辦 | 單一 `app` 容器目前無多副本設計；未來可評估 `docker compose up --scale app=2` 或導入負載平衡 |

## 五、階段性限制說明

> ⚠️ 本檢核表中標記「⏳ 待辦」之項目，多數需要**實際部署環境**（正式伺服器、真實網域、憑證頒發機構帳號）才能執行，非本機開發階段可完成，屬階段性限制而非設計缺陷。已於 `phase_gates.json` 記錄，待實際上線前逐項完成。

## 六、待辦事項彙總

1. ~~安裝 Git pre-commit hook~~ ✅ 已完成（本階段手動安裝並驗證）
2. 取得正式 TLS 憑證並掛載至 `nginx/certs/`
3. 定義並實作 RPO/RTO 與資料庫備份排程
4. 執行備份還原演練
5. 於具備 Docker 環境執行 `docker compose config` 語法驗證 + `docker compose up` 實際煙霧測試
