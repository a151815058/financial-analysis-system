# 系統功能規格說明書 (Living Documentation)

> **專案名稱**：各公司各季度財務分析與股價預測系統
> **文件版本**：v0.7（Phase 05 完成 + 內部分析儀表板追加）
> **最後更新**：2026-07-14

## 【第一部分：人類閱讀區】

### 一、 系統概述

本系統彙整台股與美股上市（櫃）公司之季度財務資料，計算 7 項核心財務指標（營收、EPS、毛利率、淨利率、負債比、現金流、本益比），並結合「財報因子統計模型」與「股價時間序列模型」進行融合預測，產出每週股價漲跌方向與幅度區間，供 API 查詢使用。系統定位為後端分析服務，不含網頁儀表板；輸出僅供分析參考，非投資建議。

### 二、 整體描述

#### 產品功能摘要

| 功能編號 | 模組名稱 | 功能說明 | 當前狀態 |
| :--- | :--- | :--- | :--- |
| FEAT_001 | 台股財務資料擷取 | 自 MOPS 擷取台股季度財報並正規化 | `[規格完成]` |
| FEAT_002 | 美股財務資料擷取 | 自 SEC EDGAR + 市場資料 API 擷取美股財報與股價 | `[規格完成]` |
| FEAT_003 | 跨市場財務指標正規化 | 統一資料模型、幣別標註、版本化 | `[規格完成]` |
| FEAT_004 | 財報因子統計模型 | 財務指標驅動之漲跌方向/幅度區間預測 | `[規格完成]` |
| FEAT_005 | 股價時間序列模型 | 短期價格動能預測 | `[規格完成]` |
| FEAT_006 | 雙模型融合 | 財報模型 + 時間序列模型 Ensemble | `[規格完成]` |
| FEAT_007 | 預測結果查詢 API | 財務指標與預測結果查詢端點 | `[規格完成]` |
| FEAT_008 | 排程機制 | 財報/股價/模型定期更新排程 | `[規格完成]` |
| FEAT_009 | 準確率回測 | 預測結果歷史準確率追蹤 | `[規格完成]` |
| FEAT_010 | 內部分析儀表板 | 文字+圖表視覺化查看財務指標/股價/預測/回測（`GET /dashboard`） | `[已實作並驗證]` |

### 三、 具體需求

#### 功能需求詳細說明

完整功能需求、驗收條件詳見 `01_planning_and_analysis/outputs/formal_requirements.md`（REQ_001~REQ_009）與安全需求 `security_requirements.md`（REQ_SEC_001）。摘要：

1. **資料擷取**：台股經 MOPS、美股經 SEC EDGAR（10-Q/10-K）+ 市場資料 API 擷取，需支援批次、重試、版本化。
2. **預測建模**：財報因子統計模型與股價時間序列模型雙軌並行，融合輸出「方向 + 幅度區間 + 信心分數」。
3. **服務化**：以 API 對外提供財務指標查詢與預測結果查詢，具備身分驗證。
4. **維運**：排程自動更新、失敗通知、預測準確率回測（近 12 週滾動視窗）。

#### 外部介面需求（API）

認證方式：API Key（`X-API-Key` Header），scope 分為 `read` / `admin`。完整規格見 `02_system_design/outputs/api_spec.md`。

| 端點 | 方法 | 說明 |
| :--- | :--- | :--- |
| `/api/v1/companies` | GET | 查詢公司清單 |
| `/api/v1/companies/{ticker}/financials` | GET | 查詢財務指標歷史 |
| `/api/v1/companies/{ticker}/prices` | GET | 查詢股價歷史 |
| `/api/v1/companies/{ticker}/predictions/latest` | GET | 查詢最新一週預測 |
| `/api/v1/companies/{ticker}/predictions/history` | GET | 查詢歷史預測 |
| `/api/v1/companies/{ticker}/backtest` | GET | 查詢回測準確率 |
| `/api/v1/admin/ingest/trigger` | POST | 手動觸發資料擷取/模型更新（需 admin） |

#### 資料庫需求

7 張資料表，詳細 DDL 見 `02_system_design/outputs/db_schema.sql`，ER 圖見 `02_system_design/outputs/er_diagram.md`：`companies`、`financial_reports`、`price_history`、`predictions`、`prediction_backtests`、`api_keys`、`audit_logs`。

#### 技術架構需求

| 類別 | 實際採用 |
| :--- | :--- |
| 語言 | Python 3.14 |
| API 框架 | FastAPI 0.139 + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| 開發/測試資料庫 | SQLite（正式環境 PostgreSQL 待 Phase 05 決定） |
| 統計模型 | scikit-learn GradientBoostingClassifier（方向分類）+ statsmodels QuantReg（5%/95% 分位數迴歸估幅度區間） |
| 時間序列模型 | statsmodels ARIMA(2,1,2) |
| 排程 | APScheduler |
| Lint/Format | ruff |
| SAST/依賴掃描 | bandit + pip-audit |

模組結構：`app/config.py`、`app/db_models.py`、`app/ingestion/`（normalizer/mops_client/sec_edgar_client/alpha_vantage_client）、`app/prediction/`（factor_model/timeseries_model/ensemble/backtest）、`app/auth.py`+`app/audit.py`、`app/routers/`（companies/predictions/admin）、`app/scheduler.py`。

**關鍵實作決策**：
- OI-002（美股欄位對應）：`sec_edgar_client.py` 採 us-gaap 標籤備援清單設計，容忍不同公司/年度使用不同但語意相同的標籤。
- OI-003（預測幅度區間粒度）：改採統計分位數迴歸而非固定級距，依實際資料分布給出區間寬度。
- 安全檢核發現稽核日誌缺來源 IP（構面 2 項次 19），已於本階段當場修復（新增 `audit_logs.source_ip` 欄位）並補上測試驗證。

### 四、 UML 系統模型

- 用例圖：`02_system_design/outputs/usecase_diagram.md`（API 使用者 / 系統管理員 / 排程器三類角色）
- 活動圖：`02_system_design/outputs/activity_diagram.md`（每週預測產出主流程、回測流程）
- 時序圖：`02_system_design/outputs/sequence_diagram.md`（API 查詢流程、排程觸發預測產出流程）
- ER 圖：`02_system_design/outputs/er_diagram.md`

> 本系統定位為後端分析服務 + API，經使用者確認不需網頁儀表板，故無 UI 雛型產出。

### 五、 驗收標準

| 項目 | 結果 |
| :--- | :--- |
| 測試總數 | 58（Phase 03 單元/整合測試 49 + Phase 04 系統整合測試 9） |
| 通過率 | 100%（58/58） |
| 程式碼覆蓋率 | 92.5% |
| 需求測試覆蓋 | 9/9 功能需求 + 1/1 安全需求皆有對應測試 |
| SAST（bandit） | 0 findings |
| 依賴掃描（pip-audit） | 0 known vulnerabilities |
| DAST（手動等效測試，ZAP 環境不可用） | 核心攻擊面（認證繞過/注入/輸入驗證/錯誤洩漏）無 Critical/High 風險 |
| 已知限制 | REQ_008 admin 觸發端點尚未串接實際擷取/推論管線（Phase 03 任務邊界，非缺陷） |

_(SHA-256 驗證結果待 Phase 05 部署完成後同步)_

### 六、 附錄

#### 附錄 A：部署架構（Phase 05）

| 項目 | 內容 |
| :--- | :--- |
| 部署方式 | Docker（`Dockerfile` + `docker-compose.yml`：app + db + nginx 三服務） |
| 正式資料庫 | PostgreSQL 16（開發/測試維持 SQLite） |
| 反向代理 | nginx（HTTPS 導向、TLS 1.2+、安全標頭、資料庫/app 埠口不對外開放） |
| 環境參數 | 見 `05_deployment/outputs/.env.example`（POSTGRES_*、ALPHA_VANTAGE_API_KEY、SEC_EDGAR_USER_AGENT） |
| SBOM | `05_deployment/outputs/sbom.json`（19 個套件元件） |
| 建置完整性 | `05_deployment/outputs/build_manifest.json`（33 檔 SHA-256，已重新驗證一致） |
| 數位簽章 | 未執行（本環境無簽章憑證），以 SHA-256 作為替代完整性驗證，詳見 `signature_status.json` |

> ⚠️ **驗證限制**：本機環境仍未安裝 Docker/nginx，容器化與反向代理組態**已產出但未經實際建置/執行驗證**。**PostgreSQL 部分已於 2026-07-15 補做真實驗證**：使用者提供真實 Supabase PostgreSQL，`db_schema.sql` 實際套用成功（7 表）、真實資料讀寫與 app 端 `/health`+API 驗證皆通過。已驗證項目：應用程式（非容器化）健康檢查通過、SHA-256 完整性比對一致、Git pre-commit 密鑰掃描 hook 實測攔截有效、PostgreSQL 實際連線與 schema 套用。詳見 `05_deployment/outputs/deployment_topology.md`、`deployment_config.md`。

#### 附錄 B：維運需求（Phase 06，2026-07-15 第一輪）

| 項目 | 內容 |
| :--- | :--- |
| 觸發情境 | 使用者提供真實 Supabase PostgreSQL 連線與 Alpha Vantage API Key，對台積電(2330)、Apple(AAPL) 執行真實外部資料擷取（MOPS/TWSE/SEC EDGAR/Alpha Vantage） |
| 發現並修復之熱修補 | 3 項（HF-001：MOPS 端點 404 改用 TWSE OpenAPI 重寫；HF-002：SEC EDGAR 單季/累計數字混淆；HF-003：Alpha Vantage `outputsize=full` 免費層級限制），詳見 `06_maintenance/outputs/hotfix_log.md` |
| 回歸測試 | 71 項全數通過（62 單元/整合 + 9 系統整合），覆蓋率 92%，詳見 `06_maintenance/outputs/regression_test_report.md` |
| 安全回歸 | Bandit 0 HIGH/MEDIUM、依賴掃描 0 已知漏洞（專案實際 21 個相依套件範圍），較歷史分數未下降，詳見 `06_maintenance/outputs/security_trend.md` |
| 監控設計 | 資料擷取排程健康度、API 稽核事件、模型預測準確率追蹤三項指標，皆基於 `audit_logs`/`predictions`/`prediction_backtests` 表之 SQL 查詢定義（本環境無 APM 平台），詳見 `06_maintenance/outputs/monitoring_dashboard.md` |
| 已知缺口 | `predictions`/`prediction_backtests` 表尚無真實資料（模型尚未對真實擷取資料執行）；`operating_cash_flow`（兩市場）與美股 `pe_ratio` 因免費資料來源限制長期為 `None`，非系統錯誤 |
| 框架回饋 | 新發現 1 項框架腳本瑕疵（`run_security_scan.py` 靜默假通過），已記錄至根目錄 `待辦事項.md` #8，未直接修改框架 |

#### 附錄 B-1：內部分析儀表板（FEAT_010，Phase 05 之後追加）

| 項目 | 內容 |
| :--- | :--- |
| 路由 | `GET /dashboard`（頁面）、`GET /static/dashboard.{css,js}`（資源） |
| 技術 | 純 HTML+CSS+原生 JS，無 CDN 相依，SVG 圖表手刻實作 |
| 內容 | 公司選擇器、財務指標歷史（表格+趨勢圖）、股價歷史趨勢圖、最新預測（KPI+股價圖區間疊加，含融合/財報因子/時間序列三模型明細）、回測準確率 |
| 認證 | 頁面本身不需認證；頁內對 API 呼叫仍需 X-API-Key（使用者於畫面右上角輸入，存於瀏覽器 localStorage） |
| 驗證方式 | Chrome headless + Puppeteer 實際驅動（輸入金鑰、切換公司、觸發 hover），螢幕截圖確認 light/dark mode、錯誤狀態、tooltip 互動皆正確；新增 `tests/test_dashboard.py`（3 項）；色板已跑過 dataviz skill 的 `validate_palette.js` 驗證（light/dark 皆 PASS） |
| 追溯 | 詳見 `traceability_matrix.md` REQ_010 |

#### 附錄 C：變更紀錄

| 日期 | 階段 | 版號 | 摘要 |
| :--- | :--- | :--- | :--- |
| 2026-07-14 | 00 (@init) | v0.1 | 專案初始化，建立標準 SSDLC 目錄結構，啟用中級資安防護基準、引導式協作與 IO 管理 |
| 2026-07-14 | 01（規劃與需求分析） | v0.2 | 完成需求釐清（含美股資料來源缺口拷問），產出 9 項功能需求 + 1 項安全需求；Evaluator 通過（92 分）；建立 Phase 01 Baseline；Phase 02 解鎖 |
| 2026-07-14 | 02（系統設計） | v0.3 | 確認 OI-001（Alpha Vantage）；產出 DB Schema（7 表）、API 規格（7 端點）、用例圖、活動圖、時序圖、威脅建模；不含 UI 雛型；Evaluator 通過（94 分）；建立 Phase 02 Baseline；Phase 03 解鎖 |
| 2026-07-14 | 03（開發與編碼） | v0.4 | 完成 13 項任務實作；解決 OI-002/OI-003；49 項單元測試全數通過；ruff/bandit/pip-audit 全數乾淨；安全檢核發現並當場修復稽核日誌缺來源IP；Evaluator 通過（97 分）；建立 Phase 03 Baseline；Phase 04 解鎖 |
| 2026-07-14 | 04（測試驗證） | v0.5 | 新增 9 項系統整合測試（真實 HTTP），共 58 項測試全數通過，覆蓋率 92.5%；執行 DAST 等效測試無 Critical/High 風險；發現並修復 BUG_001；Evaluator 通過（98 分）；建立 Phase 04 Baseline；Phase 05 解鎖 |
| 2026-07-14 | 05（部署發布） | v0.6 | 決策：PostgreSQL + Docker；產出 Dockerfile/docker-compose/nginx.conf/SBOM/build_manifest；因環境無 Docker 未實際建置驗證，如實記錄於評分（加權總分 66，部署安全子項 90% 通過安全關卡）；建立 Phase 05 Baseline；Phase 06 解鎖 |
| 2026-07-14 | 05+（範疇外追加，Phase 06 前） | v0.7 | 新增 FEAT_010 內部分析儀表板（`/dashboard`），文字+圖表呈現財務指標/股價/預測/回測；Chrome headless+Puppeteer 實際驗證 light/dark mode 與互動；新增 3 項自動化測試（共 52 項）；未走完整 Phase 02 UI 設計流程，屬使用者要求之輕量追加 |
| 2026-07-15 | 06（維護與營運，第一輪） | v0.8 | 使用者提供真實 Supabase PostgreSQL 與 Alpha Vantage API Key，對台積電/Apple 執行真實外部資料擷取；發現並修復 3 項熱修補（HF-001/002/003）；補做 Phase 05 資料庫真實驗證（evaluator_score.availability_check 18→22，weighted_total 66→70）；71 項回歸測試全數通過；安全回歸 100%（未下降）；產出監控儀表板設計；新發現框架瑕疵回饋至 `待辦事項.md` #8 |

## 【第二部分：機器執行區】

> 以下 Gherkin 場景摘自 `specs/features/requirements.feature`，狀態將於各階段測試通過後回寫。

```gherkin
# language: zh-TW
功能: 台股/美股財務資料擷取與正規化

  場景: REQ_001 台股財務資料擷取 [未通過]
    假設 已指定台股股票代號清單
    當 系統向公開資訊觀測站（MOPS）擷取最近 N 季財報
    那麼 系統應取得營收、EPS、毛利率、淨利率、負債比、現金流、本益比等資料

  場景: REQ_004 財報因子統計模型預測 [未通過]
    假設 已取得正規化後的財務指標
    當 系統執行財報因子統計模型
    那麼 應輸出未來一週漲跌方向與幅度區間與信心分數
```

> 完整場景清單（共 9 個）請見 `specs/features/requirements.feature`。
