# 缺陷追蹤表 (Bug Tracker)

| Bug ID | 發現日期 | 嚴重度 | 描述 | 重現步驟 | 根因 | 修復方案 | 狀態 | 修復日期 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| BUG_001 | 2026-07-14 | Trivial | 執行完整測試套件（單元測試+系統整合測試）時出現多筆 `ResourceWarning: unclosed database` | 執行 `pytest tests/ 04_testing/outputs/test_api.py` | (1) `db_session` fixture 建立的 in-memory SQLite engine 未於測試結束時呼叫 `dispose()`；(2) `app/main.py` lifespan 啟動時使用的模組級預設 `engine`（`app/db_session.py`）於整個測試 session 期間未釋放 | 於 `tests/conftest.py` 新增：① `db_session` fixture teardown 呼叫 `engine.dispose()`；② session-scoped autouse fixture `_dispose_default_engine`，於全部測試結束後釋放預設模組級 engine | ✅ 已修復 | 2026-07-14 |

> 本階段（Phase 04）執行雙套測試（Phase 03 遺留 49 項單元/整合測試 + 本階段新增 9 項系統整合測試，共 58 項）皆一次全數通過，僅發現上述 1 項測試環境資源清理相關的 Trivial 缺陷，無 Major/Critical 功能性缺陷。
