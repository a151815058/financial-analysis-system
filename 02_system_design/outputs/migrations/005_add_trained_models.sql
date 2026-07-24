-- =============================================================================
-- Migration 005：新增 trained_models 資料表（REQ_004：版本化模型檔案）
-- 目標資料庫：PostgreSQL 15+（Supabase）
-- 冪等：CREATE TABLE IF NOT EXISTS，可重複執行
--
-- 與 job_runs（Migration 003）、admin_users（Migration 004）相同：全新資料表，
-- app/db_session.py 的 init_db() 於每次應用程式啟動時呼叫 Base.metadata.create_all()
-- 即會自動建立，不需手動對正式資料庫執行才會生效。此檔案僅作為 SSOT 文件與需要手動介入
-- 場景之備援。
--
-- 用途：model_retrain（app/jobs.py::run_model_retrain）訓練財報因子模型後，透過
-- app/prediction/model_registry.py 將模型以 pickle 序列化存入 artifact 欄位；
-- weekly_predict 優先讀取此表已持久化之模型做推論，取代原本每次即時重新訓練的簡化設計。
-- model_name 為主鍵，同一模型僅保留最新一筆（upsert，同 job_runs 之慣例）。
-- =============================================================================

CREATE TABLE IF NOT EXISTS trained_models (
    model_name     VARCHAR(40)  PRIMARY KEY,
    model_version  VARCHAR(40)  NOT NULL,
    trained_at     TIMESTAMPTZ  NOT NULL,
    sample_size    INTEGER      NOT NULL,
    artifact       BYTEA        NOT NULL
);

COMMENT ON TABLE trained_models IS
    'REQ_004：已持久化之訓練模型（目前僅 factor_model），供 weekly_predict 載入推論用，取代每次即時重訓';
