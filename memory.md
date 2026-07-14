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

## 當前狀態

- 目前階段：Phase 04（測試驗證）— `in_progress`（Phase 01~03 已完成並各自建立 Baseline v1）
- 下一步建議：Phase 04 聚焦於彙整已有的 49 項單元測試結果為正式測試報告、執行覆蓋率分析（coverage.py）、視需要規劃 API 整合測試（httpx AsyncClient 對真實 SQLite/PostgreSQL）與 Phase 03 資安檢核提到的滲透測試（項次57，目前⬚未涵蓋）。

## Git 版本歷程

| 時間 | 動作 | 說明 |
| :--- | :--- | :--- |
| 2026-07-14 | `git init` + root commit `bd804a9` | 補建版本控管，一次性納入 Phase 01/02 現況 |
| 2026-07-14 | 建立標籤 `baseline-phase01-v1` | 回溯標記，指向 root commit |
| 2026-07-14 | 建立標籤 `baseline-phase02-v1` | 回溯標記，指向 root commit |
| 2026-07-14 | 建立並切換分支 `phase-03-implementation` | `main` 保留為基準分支，後續開發於此分支進行 |
