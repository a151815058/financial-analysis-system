# 修補日誌與異動明細 (Patch Changelog)

> 產出日期：2026-07-24 | Phase 06 維護與營運
> 本次二項變更皆為「排程任務由佔位（stub）補完為真實邏輯」，非既有功能之缺陷修復（非 hotfix）。兩者皆已在本機連線正式 Supabase 資料庫驗證過真實執行結果，非僅單元測試通過。

## PATCH-001：`weekly_backtest` 由佔位函式補完為真實回測評分邏輯（REQ_009）

- **變更動機**：`app/main.py` 中 `weekly_backtest` 排程（每週一 01:30）原為 `_stub_job`，觸發後僅記錄警告、不執行任何邏輯。連帶地，`prediction_backtests` 表從未被任何程式碼寫入資料，導致對外 API `GET /api/v1/companies/{ticker}/backtest` 永遠回傳 `404 No backtest data available yet`，`app/prediction/backtest.py` 已寫好的準確率計算函式（`BacktestRecord`）從未被實際呼叫。
- **影響範圍**：新增 `app/jobs.py::run_weekly_backtest`（含輔助函式 `_nearest_baseline_price`、`_target_price_after`）；`app/main.py` 排程註冊改接真實函式。
- **實作方案**：
  - 評分資格採**資料驅動**（而非日曆天數門檻）：一筆 `Prediction` 只要能找到基準收盤價、及基準日之後第 5 個「實際已入庫」交易日收盤價（對應 `TimeSeriesModel.TRADING_DAYS_PER_WEEK`），即視為可評分；找不到則略過、留待下次排程重試，不需另外實作台股/美股假日曆邏輯。
  - 基準價回溯視窗 7 天（往回找，避免用預測當時尚不存在的股價當基準）；目標價安全閥 21 天（超過視為資料缺口，不勉強產出失真結果）。
  - 已評分過的預測不重複評分（`prediction_backtests.prediction_id` UNIQUE 約束 + `outerjoin`/`IS NULL` 查詢）。
  - 批次隔離：單一預測評分失敗不中斷其餘預測（比照 `run_weekly_predict` 既有慣例）。
- **驗證**：
  - `tests/test_jobs.py` 新增 8 項單元測試（方向/區間命中與未命中、基準價/目標價缺失略過、已評分不重評、批次隔離），全數通過；全專案 138 項測試無回歸。
  - 本機連線正式 Supabase 手動觸發後，4 筆既有真實預測中 2 筆有足夠股價資料被成功評分並寫入 `prediction_backtests`（另 2 筆因股價資料未滿 5 個交易日，正確略過待重試）。
  - `GET /api/v1/companies/2330/backtest?market=TW`、`GET /api/v1/companies/AAPL/backtest?market=US` 由原本必定 404，驗證後皆回傳 200 與正確之 `directional_accuracy`/`range_hit_rate`。
- **狀態**：✅ 已完成並於正式資料庫驗證

## PATCH-002：`model_retrain` 由佔位函式補完為模型持久化訓練邏輯（REQ_004）

- **變更動機**：REQ_004 驗收條件明訂「模型訓練與推論流程需可重現（固定隨機種子、版本化模型檔案）」，但 `weekly_predict` 原設計每次執行皆即時重新訓練財報因子模型（不快取、不持久化），此為 `app/jobs.py` 文件明記之已知簡化；`model_retrain` 排程（每週日 22:00）則維持 `_stub_job`，從未真正訓練或持久化任何模型。
- **範圍界定**：僅處理跨公司彙總訓練的 `FactorModel`。`TimeSeriesModel` 為逐公司、以當週最新股價序列即時 fit 的 ARIMA 模型，本質上每週皆須用最新資料重新訓練，不適合亦不需要持久化重用，故不在本次範圍內，維持現行行為。
- **影響範圍**：
  - 新增資料表 `trained_models`（`app/db_models.py::TrainedModel`；`02_system_design/outputs/migrations/005_add_trained_models.sql`、`db_schema.sql` 同步）。
  - 新增 `app/prediction/model_registry.py`（`save_factor_model`/`load_factor_model`，以 `pickle` 序列化模型內容，僅還原本系統自行寫入之資料，非反序列化不可信輸入）。
  - 新增 `app/jobs.py::run_model_retrain`；`run_weekly_predict` 改為優先呼叫 `model_registry.load_factor_model()`，找不到已持久化模型時 fallback 為既有的即時訓練（`_train_pooled_factor_model`），確保全新部署或 `model_retrain` 尚未執行過一輪時，`weekly_predict` 仍可正常運作。
  - `app/main.py`：`model_retrain` 改接真實邏輯；因此時全部 6 個排程任務皆已脫離 stub，一併移除已無呼叫端的 `_stub_job` 死碼（及隨之未使用的 `logging`/`logger`）。
- **驗證**：
  - `tests/test_jobs.py` 新增 5 項單元測試（無公司略過、樣本不足時保留既有模型不覆蓋、樣本足夠時正確持久化並可還原推論、重跑 upsert 單列、`weekly_predict` 優先使用已持久化模型而不觸發即時訓練 fallback），全數通過；全專案 143 項測試無回歸。
  - 本機重啟服務後，確認 `trained_models` 表已自動於正式 Supabase 建立（`Base.metadata.create_all()`，新表毋須手動 migration 即生效，吸取 `hotfix_log.md` HF-004 教訓後仍實際查詢資料庫確認，而非僅信任 migration 檔案存在）。
  - 手動觸發 `model_retrain`：因真實財報樣本量仍為 3 筆（< 10 筆訓練門檻，見 `traceability_matrix.md` REQ_004/REQ_016 補充說明），如預期優雅略過（`job_runs` 回報 `success`，`trained_models` 維持 0 筆，非誤判為 `failure`）。
  - 手動觸發 `weekly_predict`：確認在無已持久化模型情況下，正確 fallback 為即時訓練並成功完成（`job_runs` 回報 `success`），證明新舊行為銜接無斷點。
- **已知限制**：真實財報樣本量未達訓練門檻前，`model_retrain` 尚無法在正式環境產出實際持久化模型（僅單元測試以合成資料驗證過持久化/還原邏輯本身正確）；待財報歷史隨排程持續累積、跨公司彙總樣本數達 10 筆門檻後，`model_retrain` 會自動開始正常持久化，`weekly_predict` 會自動切換為讀取模式，無需再次介入。
- **狀態**：✅ 已完成（程式邏輯已於正式資料庫驗證運作正常；實際模型持久化待真實樣本量達標後自動生效）

## 本輪統計

| 項目 | 內容 |
| :--- | :--- |
| 補完排程任務數 | 2（`weekly_backtest`、`model_retrain`）—— 連同先前已完成之 `mops_ingest`/`sec_edgar_ingest`/`price_ingest`/`weekly_predict`（REQ_011/REQ_016），`app/main.py` 6 個排程任務至此已全數脫離 stub |
| 新增資料表 | 1（`trained_models`，Migration 005） |
| 新增/異動測試 | `tests/test_jobs.py` 新增 13 項（`weekly_backtest` 8 項 + `model_retrain` 5 項），全專案共 143 項測試通過，無回歸 |
| 是否已影響正式資料庫 | 是——`weekly_backtest` 已對正式 Supabase 產生 2 筆真實回測資料；`model_retrain` 已對正式 Supabase 自動建立 `trained_models` 新表（目前仍為空，符合真實資料現況） |
