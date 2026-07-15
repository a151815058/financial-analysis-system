# 部署組態設定 (Deployment Config)

> 補產出日期：2026-07-15 | 對應 `06_maintenance/io_files.yaml` 必填輸入
> 補產出原因：Phase 05 原輸出未含此檔名，`io_files.yaml` 之 IO 合約要求 `deployment_config.md` 作為 Phase 06 輸入，故依 Phase 05 實際決策回頭整理。內容與 `deployment_topology.md`（拓樸圖）互補，本檔聚焦「實際組態值」而非依賴關係圖。

## 一、執行環境現況

| 項目 | 決策 | 狀態 |
| :--- | :--- | :--- |
| 應用程式執行方式 | `uvicorn app.main:app`（非容器化，直接於本機執行） | ✅ 已實際運行並驗證 |
| 容器化部署 | Docker Compose（`Dockerfile` + `docker-compose.yml`，app+db+nginx 三服務） | ⏳ 組態已產出，未實際 `docker build`/`docker compose up`（本機無 Docker） |
| 正式資料庫 | PostgreSQL（Supabase 代管，非 docker-compose 中的 `db` 服務） | ✅ 已實際連線並驗證（見下） |
| 反向代理 | nginx（HTTPS 導向、TLS 1.2+、安全標頭） | ⏳ 組態已產出，未實際 `nginx -t` 驗證 |

## 二、資料庫連線組態

- **實際使用**：Supabase PostgreSQL（Session Pooler，`aws-0-ap-southeast-2.pooler.supabase.com:5432`），非 `docker-compose.yml` 內建的自架 `db` 服務
- **驅動**：`psycopg[binary]==3.3.4`（SQLAlchemy URL scheme 需為 `postgresql+psycopg://`，非預設的 `postgresql://`，否則會嘗試載入未安裝的 `psycopg2`）
- **Schema**：`02_system_design/outputs/db_schema.sql` 已於 2026-07-15 實際套用，7 張資料表全數建立成功
- **後續若改自架 PostgreSQL**：需將 `DATABASE_URL` 指向 `docker-compose.yml` 中的 `db` 服務並重新驗證，目前組態仍保留該服務定義以維持彈性

## 三、環境變數清單

| 變數 | 用途 | 現況 |
| :--- | :--- | :--- |
| `DATABASE_URL` | 資料庫連線字串 | ✅ 已設定為真實 Supabase 連線 |
| `ALPHA_VANTAGE_API_KEY` | 美股股價來源 | ✅ 已設定真實金鑰（免費層級，`outputsize` 僅能用 `compact`） |
| `SEC_EDGAR_USER_AGENT` | SEC EDGAR 存取識別 | ⚠️ 仍為範例佔位值，正式上線前應換成真實聯絡信箱 |
| `MOPS_BASE_URL` | 舊版 MOPS HTML 端點基底 URL | ⚠️ 已停用，`mops_client.py` 改用 `openapi.twse.com.tw` 固定端點，此變數目前未被程式碼引用 |
| `HTTP_TIMEOUT_SECONDS` / `HTTP_MAX_RETRIES` | 外部 API 逾時與重試設定 | ✅ 沿用預設值（10s / 3 次） |
| `MIN_SECURITY_SCORE_PCT` | 安全關卡門檻 | ✅ 70（沿用專案中級防護基準） |

## 四、對外服務端點

- 應用程式：`http://127.0.0.1:8000`（本機驗證用；正式環境應僅透過 nginx 443 對外）
- `/health`：健康檢查端點，已實際驗證回應 200
- `/dashboard`：內部分析儀表板（REQ_010，範疇外追加功能）
- `/api/v1/*`：需 `X-API-Key` 標頭，已實際驗證 `companies`/`financials`/`prices` 端點

## 五、已知組態限制（誠實揭露）

1. 容器化部署（Docker/docker-compose）與反向代理（nginx）組態皆未經實際建置/執行驗證，詳見 `security_deployment_checklist.md` 待辦事項彙總第 6 項
2. TLS 正式憑證、資料庫備份排程、備援機制皆為待辦（需正式部署環境）
3. `SEC_EDGAR_USER_AGENT` 仍為佔位值，正式上線前須更換

## 六、Phase 06 銜接重點

- 監控應涵蓋：`audit_logs` 表（API 存取與擷取任務事件）、外部資料來源擷取成功率（MOPS/TWSE/SEC EDGAR/Alpha Vantage 皆已知有真實失效模式，見 `patch_changelog.md`）
- 現金流量表（`operating_cash_flow`）與美股本益比（`pe_ratio`）為已知資料缺口，非系統錯誤，監控時不應誤判為異常
