-- =============================================================================
-- Migration 003：新增 job_runs 資料表（REQ_013：排程執行狀況 /admin 頁面）
-- 目標資料庫：PostgreSQL 15+（Supabase）
-- 冪等：CREATE TABLE IF NOT EXISTS，可重複執行
--
-- 與 Migration 002（HF-004）不同之處：job_runs 是全新資料表，app/db_session.py 的
-- init_db() 於每次應用程式啟動時呼叫 Base.metadata.create_all()，即會自動建立此表，
-- 不需要像 002 的 ALTER TABLE 那樣手動對正式資料庫執行才會生效。此檔案僅作為 SSOT
-- 文件與需要手動介入場景（如資料庫帳號無 DDL 自動建立權限）之備援。
-- =============================================================================

CREATE TABLE IF NOT EXISTS job_runs (
    task_name     VARCHAR(40)  PRIMARY KEY,
    status        VARCHAR(10)  NOT NULL CHECK (status IN ('success', 'failure')),
    trigger_mode  VARCHAR(10)  NOT NULL CHECK (trigger_mode IN ('scheduled', 'manual')),
    started_at    TIMESTAMPTZ  NOT NULL,
    finished_at   TIMESTAMPTZ  NOT NULL,
    detail        VARCHAR(1000)
);

COMMENT ON TABLE job_runs IS
    'REQ_013：每個排程任務僅保留最新一筆執行結果（非歷史紀錄），執行時 upsert 覆寫';
