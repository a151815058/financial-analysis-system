-- =============================================================================
-- Migration 002：companies 新增 cik 欄位（HF-004，REQ_008 排程補完之附帶變更）
-- 目標資料庫：PostgreSQL 15+（Supabase）
-- 冪等：可重複執行，已套用過不會報錯
-- =============================================================================

ALTER TABLE companies ADD COLUMN IF NOT EXISTS cik VARCHAR(10);

COMMENT ON COLUMN companies.cik IS
    'REQ_002/REQ_008：SEC EDGAR Company Facts API 所需之 CIK 編號，US 公司排程擷取用；'
    'NULL 表示尚未登記，sec_edgar_ingest 會略過該公司';

-- 回填目前資料庫中唯一已知的美股種子公司（HF-002 驗證時以此 CIK 手動擷取過 Apple 真實資料）
UPDATE companies SET cik = '0000320193'
WHERE market = 'US' AND ticker = 'AAPL' AND cik IS NULL;
