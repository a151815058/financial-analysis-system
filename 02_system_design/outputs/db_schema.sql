-- =============================================================================
-- 資料庫 Schema — 各公司各季度財務分析與股價預測系統
-- 目標資料庫：PostgreSQL 15+
-- 對應 ER 圖：er_diagram.md
-- 對應需求：REQ_001 ~ REQ_009, REQ_SEC_001
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. companies — 公司主檔
-- ---------------------------------------------------------------------------
CREATE TABLE companies (
    company_id      BIGSERIAL PRIMARY KEY,
    ticker          VARCHAR(20)  NOT NULL,               -- 台股代號 / 美股 Ticker
    market          VARCHAR(2)   NOT NULL CHECK (market IN ('TW', 'US')),
    name            VARCHAR(200) NOT NULL,
    industry        VARCHAR(100),
    currency        CHAR(3)      NOT NULL CHECK (currency IN ('TWD', 'USD')),
    cik             VARCHAR(10),                          -- SEC EDGAR CIK（US 公司排程擷取用，見 migrations/002）
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (market, ticker)
);
COMMENT ON TABLE companies IS 'REQ_003：跨市場公司主檔';
COMMENT ON COLUMN companies.cik IS 'REQ_002/REQ_008：SEC EDGAR Company Facts API 所需之 CIK 編號，US 公司排程擷取用；NULL 表示尚未登記，sec_edgar_ingest 會略過該公司';

-- ---------------------------------------------------------------------------
-- 2. financial_reports — 季度財務報表正規化資料
-- ---------------------------------------------------------------------------
CREATE TABLE financial_reports (
    report_id           BIGSERIAL PRIMARY KEY,
    company_id          BIGINT      NOT NULL REFERENCES companies(company_id),
    fiscal_year         INT         NOT NULL,
    fiscal_quarter      SMALLINT    NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    report_date         DATE        NOT NULL,             -- 財報公布日
    revenue             NUMERIC(20,2),                    -- 營收
    eps                 NUMERIC(10,4),                    -- 每股盈餘
    gross_margin        NUMERIC(6,3),                     -- 毛利率 (%)
    net_margin          NUMERIC(6,3),                     -- 淨利率 (%)
    debt_ratio          NUMERIC(6,3),                     -- 負債比 (%)
    operating_cash_flow NUMERIC(20,2),                    -- 營業現金流
    pe_ratio            NUMERIC(10,3),                    -- 本益比
    currency            CHAR(3)     NOT NULL,
    source              VARCHAR(20) NOT NULL CHECK (source IN ('MOPS', 'SEC_EDGAR')),
    data_version        INT         NOT NULL DEFAULT 1,   -- REQ_003：財報更正版本追蹤
    is_latest_version   BOOLEAN     NOT NULL DEFAULT true,
    raw_source_ref      TEXT,                             -- 原始申報文件連結/編號（如 SEC accession number）
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, fiscal_year, fiscal_quarter, data_version)
);
COMMENT ON TABLE financial_reports IS 'REQ_001/REQ_002/REQ_003：7 項核心財務指標正規化資料';
CREATE INDEX idx_financial_reports_company_period
    ON financial_reports (company_id, fiscal_year, fiscal_quarter)
    WHERE is_latest_version = true;

-- ---------------------------------------------------------------------------
-- 3. price_history — 歷史股價資料
-- ---------------------------------------------------------------------------
CREATE TABLE price_history (
    price_id     BIGSERIAL PRIMARY KEY,
    company_id   BIGINT      NOT NULL REFERENCES companies(company_id),
    trade_date   DATE        NOT NULL,
    open_price   NUMERIC(14,4),
    high_price   NUMERIC(14,4),
    low_price    NUMERIC(14,4),
    close_price  NUMERIC(14,4) NOT NULL,
    volume       BIGINT,
    source       VARCHAR(30) NOT NULL,                   -- 'TWSE' / 'ALPHA_VANTAGE'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, trade_date)
);
COMMENT ON TABLE price_history IS 'REQ_005：股價時間序列模型輸入資料';
CREATE INDEX idx_price_history_company_date ON price_history (company_id, trade_date DESC);

-- ---------------------------------------------------------------------------
-- 4. predictions — 每週股價預測結果（融合輸出）
-- ---------------------------------------------------------------------------
CREATE TABLE predictions (
    prediction_id                  BIGSERIAL PRIMARY KEY,
    company_id                     BIGINT      NOT NULL REFERENCES companies(company_id),
    base_week_start_date           DATE        NOT NULL,  -- 預測基準週起始日（週一）
    direction                      VARCHAR(4)  NOT NULL CHECK (direction IN ('UP', 'DOWN', 'FLAT')),
    range_lower_pct                NUMERIC(6,3) NOT NULL,
    range_upper_pct                NUMERIC(6,3) NOT NULL,
    confidence_score               NUMERIC(4,3) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
    factor_model_direction         VARCHAR(4),            -- REQ_004 子模型明細
    factor_model_range_lower_pct   NUMERIC(6,3),
    factor_model_range_upper_pct   NUMERIC(6,3),
    timeseries_model_direction     VARCHAR(4),            -- REQ_005 子模型明細
    timeseries_model_range_lower_pct NUMERIC(6,3),
    timeseries_model_range_upper_pct NUMERIC(6,3),
    ensemble_weight_factor         NUMERIC(4,3),          -- REQ_006 融合權重
    ensemble_weight_timeseries     NUMERIC(4,3),
    model_version                  VARCHAR(40) NOT NULL,  -- 模型版本標籤，供追溯
    created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, base_week_start_date, model_version)
);
COMMENT ON TABLE predictions IS 'REQ_004/REQ_005/REQ_006：融合預測結果';
CREATE INDEX idx_predictions_company_week ON predictions (company_id, base_week_start_date DESC);

-- ---------------------------------------------------------------------------
-- 5. prediction_backtests — 預測回測與準確率追蹤
-- ---------------------------------------------------------------------------
CREATE TABLE prediction_backtests (
    backtest_id       BIGSERIAL PRIMARY KEY,
    prediction_id     BIGINT      NOT NULL REFERENCES predictions(prediction_id),
    actual_direction  VARCHAR(4)  CHECK (actual_direction IN ('UP', 'DOWN', 'FLAT')),
    actual_return_pct NUMERIC(6,3),
    direction_hit     BOOLEAN,
    range_hit         BOOLEAN,
    evaluated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (prediction_id)
);
COMMENT ON TABLE prediction_backtests IS 'REQ_009：預測準確率回測記錄';

-- ---------------------------------------------------------------------------
-- 6. api_keys — API 存取控制（🔒 構面 1/4：存取控制、識別與鑑別）
-- ---------------------------------------------------------------------------
CREATE TABLE api_keys (
    api_key_id   BIGSERIAL PRIMARY KEY,
    key_hash     VARCHAR(128) NOT NULL UNIQUE,           -- 僅存雜湊值，不存明文金鑰
    owner        VARCHAR(100) NOT NULL,
    scope        VARCHAR(20)  NOT NULL DEFAULT 'read' CHECK (scope IN ('read', 'admin')),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    revoked_at   TIMESTAMPTZ
);
COMMENT ON TABLE api_keys IS 'REQ_SEC_001：API 金鑰管理（最小權限：read / admin）';

-- ---------------------------------------------------------------------------
-- 7. audit_logs — 事件日誌（🔒 構面 2，主要供 Phase 03/06 落實記錄）
-- ---------------------------------------------------------------------------
CREATE TABLE audit_logs (
    log_id       BIGSERIAL PRIMARY KEY,
    api_key_id   BIGINT REFERENCES api_keys(api_key_id),
    action       VARCHAR(100) NOT NULL,                  -- 如 'ingest.mops', 'predict.run', 'api.query'
    resource     VARCHAR(200),
    result       VARCHAR(20)  NOT NULL CHECK (result IN ('SUCCESS', 'FAILURE')),
    source_ip    VARCHAR(45),                             -- IPv4/IPv6，Phase 03 安全檢核新增（構面2項次19）
    detail       JSONB,
    occurred_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE audit_logs IS '🔒 構面 2：事件日誌與可歸責性';
CREATE INDEX idx_audit_logs_occurred_at ON audit_logs (occurred_at DESC);

-- ---------------------------------------------------------------------------
-- 8. job_runs — 排程任務最新一次執行狀況（REQ_013，/admin 頁面用）
-- ---------------------------------------------------------------------------
CREATE TABLE job_runs (
    task_name     VARCHAR(40)  PRIMARY KEY,                 -- 對應 scheduler.py 之 job id
    status        VARCHAR(10)  NOT NULL CHECK (status IN ('success', 'failure')),
    trigger_mode  VARCHAR(10)  NOT NULL CHECK (trigger_mode IN ('scheduled', 'manual')),
    started_at    TIMESTAMPTZ  NOT NULL,
    finished_at   TIMESTAMPTZ  NOT NULL,
    detail        VARCHAR(1000)                              -- 失敗時之錯誤訊息摘要，成功時為 NULL
);
COMMENT ON TABLE job_runs IS 'REQ_013：每個排程任務僅保留最新一筆執行結果（非歷史紀錄），執行時 upsert 覆寫';

-- ---------------------------------------------------------------------------
-- 9. admin_users — /admin 頁面帳號密碼登入（REQ_014）
-- ---------------------------------------------------------------------------
CREATE TABLE admin_users (
    user_id        BIGSERIAL PRIMARY KEY,
    username        VARCHAR(50)  NOT NULL UNIQUE,
    password_hash   VARCHAR(100) NOT NULL,          -- bcrypt 雜湊值，明文密碼從不落地
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE admin_users IS 'REQ_014：/admin 頁面帳號密碼登入用之後台管理者帳號，與 api_keys 分開管理';

-- ---------------------------------------------------------------------------
-- 10. trained_models — 已持久化之訓練模型（REQ_004：版本化模型檔案，Migration 005）
-- ---------------------------------------------------------------------------
CREATE TABLE trained_models (
    model_name     VARCHAR(40)  PRIMARY KEY,        -- 目前僅 "factor_model"
    model_version  VARCHAR(40)  NOT NULL,
    trained_at     TIMESTAMPTZ  NOT NULL,
    sample_size    INTEGER      NOT NULL,
    artifact       BYTEA        NOT NULL             -- pickle 序列化後之模型內容
);
COMMENT ON TABLE trained_models IS 'REQ_004：model_retrain 訓練後持久化之模型，weekly_predict 優先載入推論，每個 model_name 僅保留最新一筆';
