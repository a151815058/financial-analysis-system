# Phase 03 Baseline — v1

- **建立時間**：2026-07-14T03:30:00
- **階段**：03_implementation_and_coding（開發與編碼）
- **Evaluator 評分**：spec_compliance 94 / code_quality 100 / test_coverage 95 / security_handling 100（加權總分 97）
- **技術棧**：Python 3.14 + FastAPI 0.139 + SQLAlchemy 2.0 + scikit-learn 1.9 + statsmodels 0.14（scipy 需固定 1.17.1，見下方環境註記）

## Baseline 可執行性驗證（依 CORE_RULES 第三-4-4 節）

| 驗證項目 | 結果 |
| :--- | :--- |
| 啟動腳本存在（run.bat / start.sh） | ✅ 通過 |
| 依賴清單完整性（requirements.txt） | ✅ 通過 |
| 程式碼語法檢查（`python -m py_compile`） | ✅ 通過，無語法錯誤 |
| 服務啟動與 HTTP 回應檢查 | ✅ 通過，`uvicorn` 啟動後 `GET /health` 回應 `200 OK` |
| 檔案雜湊一致性 | ✅ 已產生 `MANIFEST_hashes.txt`（49 個檔案 SHA-256） |
| 單元測試 | ✅ 49/49 通過（`unit_test_results.xml`） |
| Lint/Format | ✅ ruff check 0 errors，ruff format 全數合規 |
| SAST/依賴掃描 | ✅ bandit 0 findings，pip-audit 0 known vulnerabilities |

## ⚠️ 環境相依重要註記

本專案執行環境為 **Python 3.14（Windows）**，實測發現 **scipy 1.18.0 官方 Windows wheel 之 `scipy.signal._max_len_seq_inner` 編譯擴充模組載入失敗**（`ImportError: DLL load failed`），導致依賴 `scipy.signal` 的 `statsmodels`（ARIMA、QuantReg 等）完全無法載入。

**已驗證修復**：改用 `scipy==1.17.1`（已在 `requirements.txt` 明確釘選版本）即可正常運作，已於本機重現測試通過（49 項單元測試含 ARIMA/QuantReg 測試皆綠燈）。

**部署前必讀**：Phase 05 若更換執行環境（不同作業系統/Python 版本），務必重新驗證 `scipy.signal` 是否可正常載入，避免此環境相依問題復發。

## 已解決之待確認事項

- **OI-002**：美股 XBRL 財報欄位對應 → `app/ingestion/sec_edgar_client.py` 標籤備援清單設計
- **OI-003**：預測幅度區間粒度 → `app/prediction/factor_model.py` 統計分位數迴歸（5%/95%）

## Evaluator 發現並當場修復之項目

- 安全檢核（構面 2 項次 19）發現 `audit_logs` 缺來源 IP 欄位，已新增 `source_ip` 並於全部端點寫入，測試 `tests/test_api_companies.py::test_list_companies_records_source_ip_in_audit_log` 驗證通過。同步回補 `02_system_design/outputs/db_schema.sql` 之 `audit_logs` 表定義。

## 檔案雜湊清單

完整 49 個檔案之 SHA-256 雜湊值見同目錄 `MANIFEST_hashes.txt`。

## Git 版本註記

本階段程式碼已提交至分支 `phase-03-implementation`，commit 訊息包含完整實作範圍說明。
