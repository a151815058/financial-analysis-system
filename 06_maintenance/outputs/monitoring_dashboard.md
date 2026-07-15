# 監控儀表板設定 (Monitoring Dashboard Config)

> 生成日期：2026-07-15 | Phase 06 維護與營運
> 對應 `io_files.yaml`：模型預測準確率追蹤、資料擷取排程健康度

## 一、誠實揭露：本階段監控實作方式

本機環境無 Docker/Prometheus/Grafana/Sentry 等 APM 平台（同 Phase 05 之環境限制），故本階段**不產出即時視覺化告警平台組態**，改以「基於既有 `audit_logs`/`predictions`/`prediction_backtests` 資料表之 SQL 查詢定義 + 建議排程頻率」實作監控，可直接對接未來導入的任一 BI/APM 工具，或先以排程 SQL + 通知腳本方式運作。

## 二、監控指標一：資料擷取排程健康度

**資料來源**：`audit_logs` 表，`action` 欄位以 `ingest.*` 前綴標記各外部資料來源擷取事件

### 查詢語法

```sql
SELECT action, result, COUNT(*) AS event_count, MAX(occurred_at) AS last_occurred
FROM audit_logs
WHERE action LIKE 'ingest.%'
GROUP BY action, result
ORDER BY action, result;
```

### 目前真實基準值（2026-07-15，本次 session 手動擷取產生）

| 資料來源 | SUCCESS | FAILURE | 已知失效模式 |
| :--- | :---: | :---: | :--- |
| `ingest.manual.mops`（台股財報） | 1 | 1 | 舊端點 404（已於 HF-001 修復，失敗為修復前之真實記錄，非目前狀態） |
| `ingest.manual.twse`（台股股價） | 1 | 0 | 無 |
| `ingest.manual.sec_edgar`（美股財報） | 1 | 0 | 需留意單季/累計數字混淆（已於 HF-002 修復） |
| `ingest.manual.alpha_vantage`（美股股價） | 1 | 1 | 免費層級 `outputsize=full` 不可用（已於 HF-003 修復，失敗為修復前之真實記錄） |

### 告警閾值建議

| 條件 | 建議動作 |
| :--- | :--- |
| 同一 `action` 連續 3 次 FAILURE | 標記為 A 類錯誤，檢查外部服務是否改版（比照 HF-001 案例） |
| `ingest.*` 過去 7 天 SUCCESS 率 < 80% | 觸發人工複查 |
| 某資料來源超過排程週期（週一 00:00-01:00）2 倍時間未見任何 `ingest.*` 事件 | 視為排程中斷，檢查 `scheduler.py` 是否正常運作（目前 `scheduler.py` 覆蓋率 0%，排程實際觸發邏輯尚待整合，見 `regression_test_report.md` 第三節） |

## 三、監控指標二：API 存取與稽核事件

**資料來源**：`audit_logs` 表，`action` 不含 `ingest.` 前綴者（一般 API 呼叫）

```sql
SELECT action, result, COUNT(*) AS event_count
FROM audit_logs
WHERE action NOT LIKE 'ingest.%'
GROUP BY action, result
ORDER BY event_count DESC;
```

**目前真實基準值**：`companies.financials`、`companies.list`、`companies.prices` 各 6 次 SUCCESS、0 次 FAILURE（皆為本次 session 儀表板真實資料驗證所產生的查詢紀錄）。

**告警閾值建議**：任一 API 端點 FAILURE 率 > 5% 應觸發檢查（現況 0%，尚無異常）。

## 四、監控指標三：模型預測準確率追蹤

**資料來源**：`predictions` 與 `prediction_backtests` 表

```sql
SELECT
    COUNT(*) AS total_backtests,
    SUM(CASE WHEN direction_hit THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS direction_hit_rate,
    SUM(CASE WHEN range_hit THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) AS range_hit_rate
FROM prediction_backtests;
```

**現況**：`predictions`/`prediction_backtests` 兩表目前皆為空——本次 session 僅完成真實財報/股價資料擷取，尚未執行模型預測與回測流程。此為**已知缺口，非監控機制本身的問題**；待使用者決定執行模型預測後，此查詢即可產出真實準確率數據。

**告警閾值建議**（待有資料後生效）：`direction_hit_rate` 連續 4 週低於 50%（優於隨機猜測的最低基準）應觸發模型重新檢視。

## 五、建議排程頻率

| 監控項目 | 建議頻率 | 理由 |
| :--- | :--- | :--- |
| 資料擷取健康度（第二節） | 每次排程擷取後（週一，對應 `scheduler.py` 排程時間） | 即時掌握擷取成功率 |
| API 稽核事件（第三節） | 每日 | 一般 API 流量無需即時監控 |
| 模型預測準確率（第四節） | 每週（配合 `weekly_backtest` 排程） | 對應 `scheduler.py` 中 `weekly_backtest` 任務頻率 |

## 六、下一步

1. 待使用者決定執行模型預測流程後，第四節查詢才有意義（目前為空表）
2. 待 `scheduler.py` 實際排程觸發邏輯與資料管線整合後（見 REQ_008 已知限制），第二節「排程中斷」告警才能實際運作
3. 若未來取得 Docker 環境，可將本節 SQL 查詢接入 Grafana + PostgreSQL data source 作為真正的即時儀表板，取代目前的手動/排程查詢方式
