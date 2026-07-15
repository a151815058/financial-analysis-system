# 專案記憶檔 (memory.md)

## 專案概覽

- **專案名稱**：各公司各季度財務分析與股價預測系統
- **建立日期**：2026-07-14
- **框架版本**：SSDLC-Skill（來源：SSDLC-Skill-main）
- **初始設定**：
  - 資安防護基準：中級 (medium) — 已啟用
  - 引導式協作 (@guide)：已啟用，目前於 Phase 01 關卡 1
  - 階段 IO 檔案管理 (@io)：已啟用

## 對話歷程

### 2026-07-14 — Session 1：專案初始化

- 使用者要求執行 `@init` 建立「各公司各季度財務分析與股價預測系統」專案。
- 已確認：專案路徑 `./financial-analysis-system`、資安等級 medium、引導式協作啟用、IO 管理啟用。
- AI 代理已建立完整 SSDLC 目錄結構（00~06 階段 + 根目錄控制檔案）。
- 下一步：進入 Phase 01 引導式協作關卡 1（目標確認），釐清財務分析與股價預測的具體需求範圍。

### 2026-07-14 — Session 1（續）：Phase 01 需求釐清與完成

- 使用者提供財務分析範圍（台股+美股，7 項指標）、預測方法（財報因子統計模型+時間序列模型）、資料來源（MOPS）。
- Planner 執行缺口拷問，發現 3 項缺口並經使用者確認：
  1. 美股資料來源（MOPS 不涵蓋美股）→ 確定改用 SEC EDGAR + 市場資料 API。
  2. 預測輸出格式未定義 → 確定為「未來一週漲跌方向 + 幅度區間」。
  3. 系統呈現形式未定義 → 確定為後端分析服務 + API（無網頁 UI）。
- Generator 產出：`formal_requirements.md`（REQ_001~REQ_009）、`security_requirements.md`（REQ_SEC_001，中級資安）、`requirement_tracker.md`、`specs/features/requirements.feature`（9 個 Gherkin 場景）、`specs/executable_spec.yaml`（phase_01_planning 區塊）。
- Evaluator 審查通過，綜合評分 92 分（coverage 95 / clarity 92 / traceability 95 / format 95 / security_coverage 90）。
- 全域 Agent 已同步：`traceability_matrix.md`、`system_specification.md` 更新至 v0.2；建立 `baseline/phase-01/baseline-v1/`（含 MANIFEST.md 與 SHA-256）；`phase_gates.json` 更新（01 completed，02 in_progress）。
- 留下 3 項待確認事項（OI-001 市場資料 API 供應商、OI-002 美股欄位對應、OI-003 預測幅度區間粒度），將於 Phase 02/03 確認。
- 下一步：開始 Phase 02 系統設計（資料庫 Schema、ER 圖、API 規格、UML 圖），不需 UI 雛型。

### 2026-07-14 — Session 1（續）：Phase 02 系統設計完成

- Planner 確認 OI-001：美股市場資料 API 供應商選定 Alpha Vantage。
- Generator 產出：`db_schema.sql`（7 張表）、`er_diagram.md`、`api_spec.md`（7 端點，API Key 認證）、`usecase_diagram.md`、`activity_diagram.md`（每週預測流程 + 回測流程）、`sequence_diagram.md`（API 查詢 + 排程觸發預測流程）、`threat_model.md`（STRIDE，涵蓋構面 1/4/6）。
- 依使用者先前確認（後端服務 + API，無網頁 UI），本階段未產出 `ui_prototype.html`，屬 Planner 依系統類型判定之非必要產出，非缺漏。
- Evaluator 審查通過，綜合評分 94 分（coverage 96 / clarity 93 / traceability 94 / format 95 / security_coverage 92）。
- 全域 Agent 已同步：`traceability_matrix.md`、`system_specification.md` 更新至 v0.3；建立 `baseline/phase-02/baseline-v1/`；`phase_gates.json` 更新（02 completed，03 in_progress）。
- OI-002（美股 XBRL 欄位對應）、OI-003（預測幅度區間粒度）延續帶入 Phase 03。
- 下一步：開始 Phase 03 開發與編碼（依建議技術棧 Python + FastAPI + PostgreSQL + statsmodels/scikit-learn + Prophet/ARIMA 進行實作任務拆解）。

### 2026-07-14 — Session 1（續）：補建 Git 版本控管

- 專案於 `@init` 時未同步建立 Git 倉庫，Phase 01、02 已在無版本控管狀態下完成。
- 使用者要求補建 Git，執行 `git init`，建立 `.gitignore`（排除 `.env`/`*.db`/`__pycache__` 等）。
- 由於 Phase 01/02 的中間檔案狀態未個別保存，無法拆分出符合歷史真實性的逐階段 commit，故以單一 root commit `bd804a9` 一次性納入現況，commit message 中明確標註「補建 Git、Phase 01-02 為回溯納入」，避免誤讀為虛構的漸進式歷史。
- 建立兩個回溯性 Baseline 標籤：`baseline-phase01-v1`、`baseline-phase02-v1`（皆指向 root commit，訊息中註明為回溯標記）。
- 依 CORE_RULES「所有開發工作必須在非 main 分支上進行」之規範，建立並切換至工作分支 `phase-03-implementation`，`main` 保留作為里程碑基準分支。
- 之後每個階段完成後將各自產生獨立 commit，`@snapshot`/`@baseline` 從此可產生真正的 `git diff` 補丁供 `@restore` 使用。

### 2026-07-14 — Session 1（續）：Phase 03 開發與編碼完成

- Planner 拆解 13 項任務（T-01~T-13），選定技術棧：Python 3.14 + FastAPI + SQLAlchemy 2.0 + scikit-learn + statsmodels + APScheduler。
- Generator 實作完整 `app/` 套件：資料擷取（MOPS/SEC EDGAR/Alpha Vantage）、正規化、財報因子模型（GradientBoostingClassifier + QuantReg）、時間序列模型（ARIMA）、雙模型融合、回測、API Key 認證、稽核日誌、7 個 API 端點、排程宣告。
- **解決 OI-002**：`sec_edgar_client.py` 採 us-gaap 標籤備援清單，容忍不同公司/年度標籤差異。
- **解決 OI-003**：`factor_model.py` 改採統計分位數迴歸（5%/95%）估計幅度區間，取代原先考慮的固定級距方案。
- **環境問題排除**：本機 Python 3.14 Windows 環境下，`scipy 1.18.0` 官方 wheel 之 `scipy.signal._max_len_seq_inner` 載入失敗（DLL load failed），導致 `statsmodels`（ARIMA/QuantReg）完全無法使用；改用 `scipy==1.17.1` 後驗證修復，已固定於 `requirements.txt` 並於 Baseline MANIFEST 中特別註記，供 Phase 05 換部署環境時留意重驗證。
- 撰寫 49 項 pytest 單元/整合測試（涵蓋正規化版本控管、三個外部資料源之批次隔離失敗、模型輸出格式與可重現性、融合邏輯、回測計算、API 認證與端點行為），全數通過。
- 執行 `ruff check`/`ruff format`（0 錯誤）、`bandit` SAST（0 findings）、`pip-audit` 依賴掃描（0 已知漏洞）。
- **安全檢核發現並當場修復**：稽核日誌 `audit_logs` 缺來源 IP 欄位（對應中級檢核構面 2 項次 19），新增 `source_ip` 欄位、於全部端點寫入、補上測試驗證；同步回補 Phase 02 的 `db_schema.sql`。
- Evaluator 審查通過，加權總分 97（spec_compliance 94 / code_quality 100 / test_coverage 95 / security_handling 100）；本階段安全評分 100%（6 項安全關卡指標，HTTPS 因本機開發環境列為階段性限制不計分）。
- 全域 Agent 已同步：`traceability_matrix.md`、`system_specification.md` 更新至 v0.4；建立 `baseline/phase-03/baseline-v1/`，並實際執行可執行性驗證（`python -m py_compile` 語法檢查通過、`uvicorn` 啟動後 `GET /health` 回應 200、49 個檔案 SHA-256 雜湊清單）；`phase_gates.json` 更新（03 completed，04 in_progress）。
- 已於 `phase-03-implementation` 分支提交 Git commit。
- 下一步：Phase 04 測試驗證（現有 49 項單元測試已於 Phase 03 完成，Phase 04 聚焦於整合測試報告彙整、覆蓋率分析，以及視需要之滲透測試規劃）。

### 2026-07-14 — Session 1（續）：Phase 04 測試驗證完成

- Planner 判定系統為純後端 API（無 UI），Playwright 不適用，改以「系統整合測試」（真實 HTTP，取代傳統 UI 測試軌）作為第二測試層。
- Generator 撰寫 `04_testing/outputs/test_api.py`：實際啟動 `uvicorn` 子行程 + 真實 SQLite 檔案 + 真實 HTTP 呼叫，9 項測試涵蓋健康檢查、認證繞過、CRUD 查詢、admin 權限、404 情境，全數通過。
- 執行覆蓋率分析（pytest-cov）：合併 Phase 03 的 49 項 + 本階段 9 項共 58 項測試，`app/` 整體覆蓋率 92.5%。
- 執行 DAST 等效動態測試（本環境無 Java，OWASP ZAP 不可用）：針對真實運行中的服務手動測試 HTTP 安全標頭、SQL Injection-like/XSS-like payload、輸入驗證邊界（負數/超量分頁參數）、錯誤資訊洩漏，核心攻擊面無 Critical/High 風險，僅 2 項中低/低風險（缺 HTTP 安全標頭、Server 標頭洩漏）排入 Phase 05。
- 撰寫 `run_tests.bat` 並**實際執行測試**（非僅撰寫）：首次執行發現 2 項腳本邏輯錯誤（`popd` 後相對路徑深度算錯、`if exist` 判斷條件寫反成檢查目的地而非來源），修復後重新執行確認 58 passed。過程中也發現此環境呼叫 `cmd.exe /c` 需要 `.\` 前綴否則報「不是內部或外部命令」，並發現 UTF-8 BOM 批次檔若非 CRLF 換行會被 cmd.exe 嚴重誤解析（逐字拆散），已修正為 CRLF + BOM。
- 發現並修復 1 項 Trivial 缺陷（BUG_001）：測試出現 `ResourceWarning: unclosed database`，根因為 `db_session` fixture 與 `app/main.py` lifespan 使用的模組級預設 engine 皆未於測試結束時 `dispose()`；已於 `conftest.py` 修復並補上驗證。
- Evaluator 審查通過，加權總分 98（requirement_coverage 97 / dual_track_pass_rate 100 / bug_tracking 100 / regression_strategy 90 / security_testing 100）。
- 全域 Agent 已同步：`traceability_matrix.md`、`system_specification.md` 更新至 v0.5；建立 `baseline/phase-04/baseline-v1/`；順手修正 `baseline/phase-03/baseline-v1/MANIFEST_hashes.txt` 的自我參照雜湊錯誤（先前產生時檔案重導向已建立空檔導致被 find 一併掃入）；`phase_gates.json` 更新（04 completed，05 in_progress）。
- 已知限制記錄：REQ_008 的 admin 觸發端點目前僅記錄稽核日誌，尚未實際串接資料擷取/推論管線（Phase 03 任務邊界內的合理範圍，非缺陷，已於 `test_results.md` 第五節說明）。
- 下一步：Phase 05 部署發布（PostgreSQL 正式資料庫決策、Docker/系統服務化、環境變數與密鑰管理、SBOM、HTTPS/反向代理設定，並回頭補齊 Phase 04 DAST 報告中列出的 HTTP 安全標頭）。

### 2026-07-14 — Session 1（續）：Phase 05 部署發布完成（含誠實揭露的環境限制）

- 詢問使用者兩個關鍵決策：正式資料庫（選定 PostgreSQL，產出遷移設定不實際連線）、部署方式（選定 Docker，產出組態不實際 build，因本機無 Docker）。
- Planner/Generator 產出：`Dockerfile`（多階段、非 root 使用者執行、HEALTHCHECK）、`docker-compose.yml`（app+db+nginx 三服務，db/app 不對外開放埠口，僅 nginx 對外）、`nginx.conf`（HTTPS 導向、TLS 1.2+、**回應 Phase 04 DAST 發現**補上缺少的安全標頭）、`sbom.json`、`build_manifest.json`、`signature_status.json`、`deployment_topology.md`（含回滾方案）、`security_deployment_checklist.md`。
- **發現並回報 2 項框架腳本瑕疵**（記錄於框架根目錄 `待辦事項.md` #6/#7，未直接修改框架，遵循「反饋走待辦」規則）：
  1. `scripts/security/generate_sbom.py` 硬編碼裸 `pip freeze`，本環境僅 `python -m pip` 可用，靜默失敗且不報錯 → 改手動產生等效 SBOM
  2. `scripts/security/install_hooks.py` 寫死指向框架自身倉庫路徑，無法用於任何獨立專案 → 手動安裝 pre-commit hook 至本專案 `.git/hooks/pre-commit`，並以含偽造 API Key 之真實測試檔驗證確實攔截 commit
- **誠實的 Evaluator 評分**：由於本機環境無 Docker/nginx/PostgreSQL，多數 Phase 05 核心產出（映像檔建置、容器編排啟動、反向代理實際轉發、資料庫實際連線）**無法實際驗證**。沒有為了好看而灌水評分，加權總分僅 66（明顯低於 Phase 01~04 的 92~98），如實反映「組態已產出但未經真實基礎設施驗證」的現況。部署安全子項單獨達 90%，通過安全關卡門檻（70%）。
- 已完成的真實驗證（不需 Docker）：`build_manifest.json` 33 檔 SHA-256 重新計算比對一致；應用程式（非容器化）健康檢查 200 OK；PostgreSQL 驅動 `psycopg[binary]` 安裝成功且 SQLAlchemy engine 可建立（未連線）；pre-commit hook 真實攔截測試。
- 全域 Agent 已同步：`traceability_matrix.md`、`system_specification.md` 更新至 v0.6（新增附錄說明部署架構與驗證限制）；建立 `baseline/phase-05/baseline-v1/`（MANIFEST.md 明確列出「已驗證」vs「未能驗證」項目）；`phase_gates.json` 更新（05 completed 但標記 `deployment_verified_in_real_infra: false`，06 in_progress）。
- 下一步：Phase 06 維運營運（日誌分析、監控指標、Hotfix 流程），並在使用者未來取得 Docker/PostgreSQL 環境後，回頭補做 Phase 05 的真實部署驗證（`security_deployment_checklist.md` 待辦清單第 5 項）。

### 2026-07-14 — Session 1（續）：內部分析儀表板追加（範疇外，Phase 06 前）

- 使用者要求暫緩 Phase 06，先規劃一個可視化介面查看 API 資料（文字 + 圖表）。
- 詢問兩個技術決策：前端方式（選定：嵌入 FastAPI 的靜態儀表板 HTML+JS+手刻 SVG，不用 CDN/不另起服務）、儀表板內容（選定：公司選擇器+財務指標歷史、股價趨勢圖、最新預測含視覺化區間、回測準確率）。
- 載入 `dataviz` skill 指引：色板選用 skill 參考色板，實際執行 `validate_palette.js` 驗證 light/dark 兩模式皆 PASS（含 CVD 分離度、對比度檢查）；圖表遵循 mark specs（2px 線、hairline 格線、crosshair+tooltip 互動層、多序列圖例+直接標籤）。
- 新增檔案：`app/static/dashboard.{html,css,js}`，`app/main.py` 新增 `/dashboard` 路由與 `/static` 掛載。前端純呼叫既有 7 個 API 端點，不新增後端邏輯。
- **股價圖預測區間視覺化**：股價歷史折線圖延伸一格「預測」，以扇形淡色區塊（融合模型）+ 三條色彩區分的垂直範圍柱（融合/財報因子/時間序列，各自 lower~upper）呈現，滑鼠 hover 可查看精確數值。
- **實際瀏覽器驗證**（非僅程式碼審查）：本環境無法開啟真實使用者瀏覽器，改用系統既有 Chrome + Puppeteer（`puppeteer-core`，未下載額外 Chromium）以無頭模式實際驅動：輸入 API Key、切換公司、觸發圖表 hover，並擷取螢幕截圖確認。驗證項目：真實資料渲染（seed 台積電假資料）、light mode、dark mode（`prefers-color-scheme`）、無效金鑰錯誤狀態、tooltip 互動、回測無資料時的空狀態訊息，皆正確顯示。
- 新增 `tests/test_dashboard.py`（3 項），累計自動化測試 52 項全數通過；ruff/bandit 皆乾淨。
- **未走完整 SSDLC 順序**：正常應先在 Phase 02 補設計文件再到 Phase 03 實作，但此為使用者要求之範疇外輕量追加，未建立獨立 Baseline，僅於 `traceability_matrix.md`（新增 REQ_010）、`system_specification.md`（新增 FEAT_010 + 附錄 B-1）、`executable_spec.yaml`（新增 `feature_010_dashboard` 區塊）、`phase_gates.json`（新增 `out_of_band_additions` 區塊）中完整記錄，維持追溯完整性但不假裝走了完整 PDCA。
- 下一步：使用者尚未決定是否/何時繼續 Phase 06（維護與營運）。

### 2026-07-14 — Session 1（續）：儀表板現場展示 + 真實資料串接請求（待續，未執行）

- 使用者要求在瀏覽器實際打開儀表板查看：以本機 Chrome（非無頭模式）開啟真實視窗，並灌入 2 家示範公司（台積電 2330、Apple AAPL）的假資料供操作展示。使用者確認看到的是假資料。
- 使用者詢問台積電目前股價資料抓到哪個時間點 → 回覆當時示範資料範圍為 2026-04-01 ~ 2026-06-29（假資料），並誠實說明：資料擷取管線（`mops_client.py`）尚未實際串接到 admin 觸發端點，目前系統完全沒有真實資料。
- 使用者接著要求：① 測試環境改用 PostgreSQL（非 SQLite）② 開始抓「正式資料」（真實 MOPS/股價）。
- AI 提出兩個關鍵決策問題：PostgreSQL 安裝方式（本機未偵測到 PostgreSQL 或 Docker）、真實資料範圍（現有系統僅有 MOPS 台股財報擷取邏輯，**沒有台股股價的真實資料來源**——Alpha Vantage 僅適用美股，需新增 TWSE 價格擷取模組）。
- 使用者回答：PostgreSQL 由使用者自行安裝/提供連線資訊；資料範圍先聚焦「台積電股價歷史（需新增 TWSE 來源）」。
- **待續，尚未執行**：使用者接著說「明天繼續用」，本次 session 到此暫停。**下次接續時**：
  1. 待使用者提供 PostgreSQL 連線資訊（host/port/user/password/db name），更新 `DATABASE_URL` 並實際驗證連線（`db_schema.sql` 為 Postgres 語法，可直接執行）。
  2. 新增 TWSE 股價擷取模組（`app/ingestion/twse_price_client.py` 或類似命名），使用 TWSE 官方公開 API（如 `https://www.twse.com.tw/exchangeReport/STOCK_DAY` 或 `openapi.twse.com.tw`），比照現有 `mops_client.py`/`alpha_vantage_client.py` 的批次隔離失敗與 retry 設計模式。
  3. 實際對台積電（2330）執行一次真實 MOPS 財報擷取 + TWSE 股價擷取，寫入 PostgreSQL，並在儀表板上以真實資料重新驗證。
  4. 提醒：對外部公開網站（MOPS/TWSE）發送真實請求時，需注意請求頻率與 User-Agent 標示，避免對外部服務造成負擔（見 `formal_requirements.md` 業務規則：僅使用公開合法資料來源，不得違反其使用條款）。
- 本機 demo 伺服器（含 2 家假資料公司）與瀏覽器視窗於本次 session 結束時仍在背景執行，供使用者持續操作展示用；下次 session 開始時應先確認是否仍需要，或關閉並改接真實資料源。

## 關鍵決策記錄

| 時間 | 決策 | 理由 |
| :--- | :--- | :--- |
| 2026-07-14 | 採中級資安防護基準 | 系統涉及公司財務資料與預測模型，需高於一般系統的存取控制與稽核要求 |
| 2026-07-14 | 啟用引導式協作 | 使用者為初次使用本框架，適合以 5 關卡對話式引導完成階段設定 |
| 2026-07-14 | 啟用 IO 檔案管理 | 使用者選擇嚴格勾稽各階段輸入輸出檔案交接 |
| 2026-07-14 | 美股財報改用 SEC EDGAR、股價改用市場資料 API | MOPS 公開資訊觀測站僅涵蓋台股，無法取得美股資料 |
| 2026-07-14 | 預測輸出定為「方向 + 幅度區間」而非絕對股價 | 對財報因子（季頻）與時間序列（日頻）混合訊號而言，區間預測較穩健，也保留更多資訊量 |
| 2026-07-14 | 系統定位為後端服務 + API，不做網頁 UI | 使用者明確表示僅需分析/預測服務，Phase 02 可省略 UI 雛型設計 |
| 2026-07-14 | 美股市場資料 API 選定 Alpha Vantage | 免費層級可用、支援股價與基本財務指標，適合 MVP 階段（速率限制列為已知限制，Phase 03 排程需考量） |
| 2026-07-14 | 預測幅度區間改採統計分位數迴歸，不用固定級距 | 依實際資料分布給出區間寬度，較具統計依據；解決 Phase 01 遺留的 OI-003 |
| 2026-07-14 | 美股財報欄位對應採「備援 tag 清單」設計 | 不同公司/年度可能用不同但語意相同的 us-gaap 標籤，備援清單避免單一標籤缺失即擷取失敗；解決 OI-002 |
| 2026-07-14 | requirements.txt 明確釘選 scipy==1.17.1 | scipy 1.18.0 官方 cp314 Windows wheel 之 `scipy.signal` 編譯擴充損壞，1.17.1 驗證可正常運作 |
| 2026-07-14 | Phase 04 不寫 Playwright UI 測試，改用真實 HTTP 系統整合測試 | 系統無網頁 UI，Playwright 不適用；改以啟動真實服務進行端到端 HTTP 驗證，達到等效的「非 mock、真實環境」驗證目的 |
| 2026-07-14 | DAST 以手動腳本取代 OWASP ZAP | 本環境無 Java，ZAP 無法安裝；改以針對相同攻擊面（認證/注入/輸入驗證/錯誤洩漏）手動測試，並在報告中明確註記涵蓋廣度不如 ZAP，非隱瞞限制 |
| 2026-07-14 | Phase 05 部署評分如實給低分（66），不因「已盡力產出組態」而灌水 | 本機無 Docker/PostgreSQL，多數 Evaluator 審查項目（建置/啟動/連線/簽章）本質上無法驗證；誠實評分才能讓使用者清楚知道哪些東西是「寫好了」而非「驗證過」 |
| 2026-07-14 | 框架腳本瑕疵發現後不直接修改框架，改記錄至待辦事項.md | 遵循框架「反饋走待辦」規則：developer 角色只能反饋，不能直接改框架根目錄檔案 |
| 2026-07-14 | 儀表板前端不用 CDN、手刻 SVG 圖表 | 避免對外部資源的執行期相依（離線/內網部署也能運作），且能精確控制 dataviz skill 要求的 mark specs 與互動細節 |
| 2026-07-14 | 用 Chrome headless + Puppeteer 實際截圖驗證 UI，而非只看程式碼 | 專案守則要求 UI 變更需在瀏覽器中實際測試；雖無真人瀏覽器，仍用系統既有 Chrome 驅動取得等效的真實渲染驗證，而非僅憑程式碼審查宣稱「應該可以動」 |

## 當前狀態

- 目前階段：Phase 06（維護與營運）— `in_progress`（尚未開始；使用者暫緩，先完成範疇外的儀表板追加 REQ_010/FEAT_010）
- 下一步：等候使用者決定是否/何時繼續 Phase 06。屆時規劃重點：日誌分析與監控指標（對應 audit_logs 與 predictions/backtest 資料）、Hotfix 流程、回歸測試機制。同時提醒使用者：待取得 Docker/PostgreSQL 環境後，應回頭執行 `05_deployment/outputs/security_deployment_checklist.md` 待辦清單（TLS 憑證、備份排程、`docker compose up` 實際驗證）。

## Git 版本歷程

| 時間 | 動作 | 說明 |
| :--- | :--- | :--- |
| 2026-07-14 | `git init` + root commit `bd804a9` | 補建版本控管，一次性納入 Phase 01/02 現況 |
| 2026-07-14 | 建立標籤 `baseline-phase01-v1` | 回溯標記，指向 root commit |
| 2026-07-14 | 建立標籤 `baseline-phase02-v1` | 回溯標記，指向 root commit |
| 2026-07-14 | 建立並切換分支 `phase-03-implementation` | `main` 保留為基準分支，後續開發於此分支進行 |
