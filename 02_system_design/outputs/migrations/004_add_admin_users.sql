-- =============================================================================
-- Migration 004：新增 admin_users 資料表（REQ_014：/admin 頁面帳號密碼登入）
-- 目標資料庫：PostgreSQL 15+（Supabase）
-- 冪等：CREATE TABLE IF NOT EXISTS，可重複執行
--
-- 與 job_runs（Migration 003）相同：全新資料表，app/db_session.py 的 init_db() 於每次應用
-- 程式啟動時呼叫 Base.metadata.create_all() 即會自動建立，不需手動對正式資料庫執行才會生效。
-- 此檔案僅作為 SSOT 文件與需要手動介入場景之備援。
--
-- 首筆帳號建立方式：本專案未提供公開註冊端點（避免任何人皆可自建後台帳號的風險），首筆帳號
-- 由維運者以 bcrypt 雜湊密碼後手動 INSERT，或透過既有 admin scope 存取權限自行決定建立方式。
-- =============================================================================

CREATE TABLE IF NOT EXISTS admin_users (
    user_id        BIGSERIAL PRIMARY KEY,
    username       VARCHAR(50)  NOT NULL UNIQUE,
    password_hash  VARCHAR(100) NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE admin_users IS
    'REQ_014：/admin 頁面帳號密碼登入用之後台管理者帳號，與 api_keys 分開管理';
