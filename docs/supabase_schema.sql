-- PostgreSQL / Supabase Schema for Indian Stock Market Research Platform
-- Mutual Fund Holdings, Financial Statements, Concall Sentiment & 10-Signal Predictions
-- Adheres to PostgreSQL best practices (CITEXT, TIMESTAMPTZ, ENUMs, GIN pg_trgm indexes, RLS, RPCs)

-- ============================================================================
-- 1. Enable Required PostgreSQL Extensions
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "citext";

-- ============================================================================
-- 2. Define Custom ENUM Types
-- ============================================================================
DO $$ BEGIN
    CREATE TYPE market_cap_tier AS ENUM ('LARGE_CAP', 'MID_CAP', 'SMALL_CAP', 'MICRO_CAP');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE holding_action_type AS ENUM ('STAKE_INCREASE', 'FRESH_ENTRY', 'STAKE_REDUCTION', 'COMPLETE_EXIT');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE prediction_trajectory AS ENUM ('STRONG_BULLISH', 'BULLISH', 'NEUTRAL', 'BEARISH', 'STRONG_BEARISH');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- 3. Table: index_stocks (Master catalog for NSE & BSE index constituents)
-- ============================================================================
CREATE TABLE IF NOT EXISTS index_stocks (
    symbol CITEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    isin TEXT UNIQUE,
    index_name TEXT NOT NULL DEFAULT 'BSE 500',
    market_cap_tier market_cap_tier NOT NULL DEFAULT 'LARGE_CAP',
    market_cap_cr NUMERIC(15, 2) CHECK (market_cap_cr >= 0),
    sector TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Trigram GIN indexes for fast autocomplete and fuzzy search
CREATE INDEX IF NOT EXISTS idx_index_stocks_symbol_trgm ON index_stocks USING gin (symbol gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_index_stocks_name_trgm ON index_stocks USING gin (company_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_index_stocks_tier ON index_stocks (market_cap_tier);
CREATE INDEX IF NOT EXISTS idx_index_stocks_updated_at ON index_stocks (updated_at);

-- ============================================================================
-- 4. Table: mf_schemes (Master catalog for Mutual Fund schemes)
-- ============================================================================
CREATE TABLE IF NOT EXISTS mf_schemes (
    scheme_id BIGINT PRIMARY KEY,
    scheme_name CITEXT NOT NULL,
    amc_name CITEXT NOT NULL,
    category TEXT,
    aum_cr NUMERIC(15, 2) CHECK (aum_cr >= 0),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mf_schemes_amc ON mf_schemes (amc_name);
CREATE INDEX IF NOT EXISTS idx_mf_schemes_name_trgm ON mf_schemes USING gin (scheme_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_mf_schemes_updated_at ON mf_schemes (updated_at);

-- ============================================================================
-- 5. Table: mf_stock_holdings (Monthly snapshot of mutual fund holdings per stock)
-- ============================================================================
CREATE TABLE IF NOT EXISTS mf_stock_holdings (
    id BIGSERIAL PRIMARY KEY,
    scheme_id BIGINT NOT NULL REFERENCES mf_schemes(scheme_id) ON DELETE CASCADE,
    symbol CITEXT NOT NULL REFERENCES index_stocks(symbol) ON DELETE CASCADE,
    as_of_date DATE NOT NULL,
    shares_held BIGINT NOT NULL CHECK (shares_held >= 0),
    market_value_cr NUMERIC(12, 2) CHECK (market_value_cr >= 0),
    portfolio_weight_pct NUMERIC(5, 2) CHECK (portfolio_weight_pct >= 0 AND portfolio_weight_pct <= 100),
    mom_share_change BIGINT DEFAULT 0,
    action_type holding_action_type DEFAULT 'STAKE_INCREASE',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_scheme_symbol_date UNIQUE (scheme_id, symbol, as_of_date)
);

-- Optimized indexes for fast queries and incremental delta sync
CREATE INDEX IF NOT EXISTS idx_holdings_symbol_date ON mf_stock_holdings (symbol, as_of_date DESC);
CREATE INDEX IF NOT EXISTS idx_holdings_scheme_id ON mf_stock_holdings (scheme_id);
CREATE INDEX IF NOT EXISTS idx_holdings_action ON mf_stock_holdings (action_type);
CREATE INDEX IF NOT EXISTS idx_holdings_created_at ON mf_stock_holdings (created_at);
CREATE INDEX IF NOT EXISTS idx_holdings_updated_at ON mf_stock_holdings (updated_at);

-- ============================================================================
-- 6. Table: stock_financials (Multi-year financial statements: P&L, Cash Flow)
-- ============================================================================
CREATE TABLE IF NOT EXISTS stock_financials (
    id BIGSERIAL PRIMARY KEY,
    symbol CITEXT NOT NULL REFERENCES index_stocks(symbol) ON DELETE CASCADE,
    period TEXT NOT NULL, -- e.g. 'FY26', 'FY25', 'Q1_FY26'
    revenue_cr NUMERIC(15, 2) DEFAULT 0.0 CHECK (revenue_cr >= 0),
    ebitda_cr NUMERIC(15, 2) DEFAULT 0.0,
    pat_cr NUMERIC(15, 2) DEFAULT 0.0,
    cfo_cr NUMERIC(15, 2) DEFAULT 0.0,
    revenue_growth_yoy NUMERIC(8, 2) DEFAULT 0.0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_stock_financials_symbol_period UNIQUE (symbol, period)
);

CREATE INDEX IF NOT EXISTS idx_stock_financials_symbol_period ON stock_financials (symbol, period DESC);
CREATE INDEX IF NOT EXISTS idx_stock_financials_updated_at ON stock_financials (updated_at);

-- ============================================================================
-- 7. Table: stock_predictions (Institutional 10-Signal Matrix forward trajectories)
-- ============================================================================
CREATE TABLE IF NOT EXISTS stock_predictions (
    symbol CITEXT PRIMARY KEY REFERENCES index_stocks(symbol) ON DELETE CASCADE,
    current_price NUMERIC(12, 2) DEFAULT 0.0 CHECK (current_price >= 0),
    trajectory_score NUMERIC(5, 2) CHECK (trajectory_score >= 0 AND trajectory_score <= 100),
    stance TEXT NOT NULL DEFAULT 'ACCUMULATE', -- e.g. 'STRONG ACCUMULATION', 'ACCUMULATE', 'HOLD', 'REDUCE'
    trajectory prediction_trajectory DEFAULT 'ACCUMULATE',
    target_bear NUMERIC(12, 2) CHECK (target_bear >= 0),
    target_base NUMERIC(12, 2) CHECK (target_base >= 0),
    target_bull NUMERIC(12, 2) CHECK (target_bull >= 0),
    target_price_bear NUMERIC(12, 2) CHECK (target_price_bear >= 0),
    target_price_base NUMERIC(12, 2) CHECK (target_price_base >= 0),
    target_price_bull NUMERIC(12, 2) CHECK (target_price_bull >= 0),
    signal_scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    signal_matrix JSONB NOT NULL DEFAULT '{}'::jsonb,
    key_drivers JSONB DEFAULT '[]'::jsonb,
    governance_flags JSONB DEFAULT '[]'::jsonb,
    scenario_analysis JSONB DEFAULT '{}'::jsonb,
    model_version TEXT DEFAULT 'FinGPT-RLSP-v2.5',
    calculated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_predictions_stance ON stock_predictions (stance, trajectory_score DESC);
CREATE INDEX IF NOT EXISTS idx_stock_predictions_signals_gin ON stock_predictions USING gin (signal_scores);

-- ============================================================================
-- 8. Table: concall_analyses (AI Concall Sentiment, Credibility & Insights)
-- ============================================================================
CREATE TABLE IF NOT EXISTS concall_analyses (
    id BIGSERIAL PRIMARY KEY,
    symbol CITEXT NOT NULL REFERENCES index_stocks(symbol) ON DELETE CASCADE,
    quarter TEXT NOT NULL, -- e.g. 'Q1_FY26'
    transcript_url TEXT,
    score NUMERIC(5, 2) DEFAULT 0.7,
    sentiment_score NUMERIC(5, 2) CHECK (sentiment_score >= -100 AND sentiment_score <= 100),
    sentiment TEXT DEFAULT 'positive',
    confidence TEXT DEFAULT 'high',
    credibility_index NUMERIC(5, 2) CHECK (credibility_index >= 0 AND credibility_index <= 100),
    summary TEXT,
    summary_markdown TEXT,
    positive_drivers JSONB DEFAULT '[]'::jsonb,
    key_risks JSONB DEFAULT '[]'::jsonb,
    guidance_notes JSONB DEFAULT '[]'::jsonb,
    guidance_numbers JSONB DEFAULT '[]'::jsonb,
    risk_flags JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_concall_analyses_symbol_quarter UNIQUE (symbol, quarter)
);

CREATE INDEX IF NOT EXISTS idx_concall_symbol_quarter ON concall_analyses (symbol, quarter DESC);
CREATE INDEX IF NOT EXISTS idx_concall_guidance_gin ON concall_analyses USING gin (guidance_notes);

-- Legacy and Mobile Compatibility View: stock_concalls
CREATE OR REPLACE VIEW stock_concalls AS
SELECT 
    id,
    symbol,
    quarter,
    transcript_url,
    COALESCE(score, sentiment_score / 100.0, 0.7) AS score,
    sentiment,
    confidence,
    COALESCE(summary, summary_markdown) AS summary,
    positive_drivers,
    COALESCE(key_risks, risk_flags) AS key_risks,
    COALESCE(guidance_numbers, guidance_notes) AS guidance_numbers,
    created_at,
    updated_at
FROM concall_analyses;


-- ============================================================================
-- 9. Trigger Function for Automatic Timestamp Management
-- ============================================================================
CREATE OR REPLACE FUNCTION update_modified_time()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_index_stocks_updated ON index_stocks;
CREATE TRIGGER trg_index_stocks_updated
    BEFORE UPDATE ON index_stocks
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION update_modified_time();

DROP TRIGGER IF EXISTS trg_mf_schemes_updated ON mf_schemes;
CREATE TRIGGER trg_mf_schemes_updated
    BEFORE UPDATE ON mf_schemes
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION update_modified_time();

DROP TRIGGER IF EXISTS trg_mf_holdings_updated ON mf_stock_holdings;
CREATE TRIGGER trg_mf_holdings_updated
    BEFORE UPDATE ON mf_stock_holdings
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION update_modified_time();

DROP TRIGGER IF EXISTS trg_stock_financials_updated ON stock_financials;
CREATE TRIGGER trg_stock_financials_updated
    BEFORE UPDATE ON stock_financials
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION update_modified_time();

DROP TRIGGER IF EXISTS trg_stock_predictions_updated ON stock_predictions;
CREATE TRIGGER trg_stock_predictions_updated
    BEFORE UPDATE ON stock_predictions
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION update_modified_time();

DROP TRIGGER IF EXISTS trg_concall_analyses_updated ON concall_analyses;
CREATE TRIGGER trg_concall_analyses_updated
    BEFORE UPDATE ON concall_analyses
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION update_modified_time();

-- ============================================================================
-- 10. Materialized View for Stock-Level MF Ownership Summary
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_stock_mf_summary AS
SELECT
    h.symbol,
    h.as_of_date,
    s.company_name,
    s.market_cap_tier,
    COUNT(DISTINCT h.scheme_id) AS scheme_count,
    SUM(h.shares_held) AS total_shares_held,
    SUM(h.market_value_cr) AS total_market_value_cr,
    SUM(h.mom_share_change) AS net_mom_change,
    COUNT(*) FILTER (WHERE h.action_type = 'FRESH_ENTRY') AS fresh_entry_count,
    COUNT(*) FILTER (WHERE h.action_type = 'COMPLETE_EXIT') AS exit_count,
    COUNT(*) FILTER (WHERE h.action_type = 'STAKE_INCREASE') AS increase_count,
    COUNT(*) FILTER (WHERE h.action_type = 'STAKE_REDUCTION') AS decrease_count
FROM mf_stock_holdings h
JOIN index_stocks s ON s.symbol = h.symbol
GROUP BY h.symbol, h.as_of_date, s.company_name, s.market_cap_tier;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_summary_symbol_date ON mv_stock_mf_summary (symbol, as_of_date);

-- ============================================================================
-- 11. Stored Procedures & RPC Functions
-- ============================================================================

-- RPC 1: Crowdsourced / Pipeline Snapshot Ingestion Function
CREATE OR REPLACE FUNCTION contribute_stock_holding_snapshot(
    p_symbol TEXT,
    p_holdings JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_clean_symbol CITEXT;
    v_item JSONB;
    v_scheme_id BIGINT;
    v_scheme_name CITEXT;
    v_amc_name CITEXT;
    v_category TEXT;
    v_aum_cr NUMERIC;
    v_as_of_date DATE;
    v_shares BIGINT;
    v_val_cr NUMERIC;
    v_wt_pct NUMERIC;
    v_mom_change BIGINT;
    v_action holding_action_type;
    v_inserted_count INT := 0;
BEGIN
    v_clean_symbol := UPPER(TRIM(p_symbol));

    -- Validate stock existence in index_stocks, create placeholder if missing
    IF NOT EXISTS (SELECT 1 FROM index_stocks WHERE symbol = v_clean_symbol) THEN
        INSERT INTO index_stocks (symbol, company_name, market_cap_tier, market_cap_cr)
        VALUES (v_clean_symbol, REPLACE(v_clean_symbol, '.NS', ''), 'LARGE_CAP', 50000.0)
        ON CONFLICT (symbol) DO NOTHING;
    END IF;

    -- Iterate through holdings array
    FOR v_item IN SELECT * FROM jsonb_array_elements(p_holdings)
    LOOP
        v_scheme_name := TRIM(COALESCE(v_item->>'scheme_name', 'Flagship Institutional Fund'));
        v_amc_name := TRIM(COALESCE(v_item->>'amc_name', 'Leading AMC'));
        v_category := COALESCE(v_item->>'category', 'Equity');
        v_aum_cr := COALESCE((v_item->>'aum_cr')::NUMERIC, 5000.0);
        v_as_of_date := COALESCE((v_item->>'as_of_date')::DATE, CURRENT_DATE);
        v_shares := GREATEST(0, COALESCE((v_item->>'shares_held')::BIGINT, 100000));
        v_val_cr := GREATEST(0, COALESCE((v_item->>'market_value_cr')::NUMERIC, 100.0));
        v_wt_pct := LEAST(100.0, GREATEST(0, COALESCE((v_item->>'portfolio_weight_pct')::NUMERIC, 2.5)));
        v_mom_change := COALESCE((v_item->>'mom_share_change')::BIGINT, 0);

        -- Derive or parse holding action type
        BEGIN
            v_action := (v_item->>'action_type')::holding_action_type;
        EXCEPTION WHEN OTHERS THEN
            v_action := 'STAKE_INCREASE'::holding_action_type;
        END;

        -- Deterministic scheme ID from name hash if not supplied
        v_scheme_id := COALESCE((v_item->>'scheme_id')::BIGINT, ('x' || substr(md5(v_scheme_name), 1, 8))::bit(32)::bigint);

        -- Upsert scheme into mf_schemes
        INSERT INTO mf_schemes (scheme_id, scheme_name, amc_name, category, aum_cr)
        VALUES (v_scheme_id, v_scheme_name, v_amc_name, v_category, v_aum_cr)
        ON CONFLICT (scheme_id) DO UPDATE
        SET scheme_name = EXCLUDED.scheme_name,
            amc_name = EXCLUDED.amc_name,
            category = EXCLUDED.category,
            aum_cr = EXCLUDED.aum_cr,
            updated_at = CURRENT_TIMESTAMP;

        -- Upsert holding into mf_stock_holdings
        INSERT INTO mf_stock_holdings (
            scheme_id, symbol, as_of_date, shares_held, market_value_cr,
            portfolio_weight_pct, mom_share_change, action_type
        )
        VALUES (
            v_scheme_id, v_clean_symbol, v_as_of_date, v_shares, v_val_cr,
            v_wt_pct, v_mom_change, v_action
        )
        ON CONFLICT (scheme_id, symbol, as_of_date) DO UPDATE
        SET shares_held = EXCLUDED.shares_held,
            market_value_cr = EXCLUDED.market_value_cr,
            portfolio_weight_pct = EXCLUDED.portfolio_weight_pct,
            mom_share_change = EXCLUDED.mom_share_change,
            action_type = EXCLUDED.action_type,
            updated_at = CURRENT_TIMESTAMP;

        v_inserted_count := v_inserted_count + 1;
    END LOOP;

    RETURN jsonb_build_object(
        'success', true,
        'symbol', v_clean_symbol,
        'records_synced', v_inserted_count
    );
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'success', false,
        'error', SQLERRM
    );
END;
$$;

-- RPC 2: Concurrent Materialized View Refresh
CREATE OR REPLACE FUNCTION refresh_mv_stock_mf_summary()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_stock_mf_summary;
END;
$$;

-- ============================================================================
-- 12. Row Level Security (RLS) Hardening
-- ============================================================================
ALTER TABLE index_stocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE mf_schemes ENABLE ROW LEVEL SECURITY;
ALTER TABLE mf_stock_holdings ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_financials ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE concall_analyses ENABLE ROW LEVEL SECURITY;

-- 1. Read-Only Public Access (anon and authenticated users can view all stock research)
DROP POLICY IF EXISTS p_read_index_stocks ON index_stocks;
CREATE POLICY p_read_index_stocks ON index_stocks FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS p_read_mf_schemes ON mf_schemes;
CREATE POLICY p_read_mf_schemes ON mf_schemes FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS p_read_mf_stock_holdings ON mf_stock_holdings;
CREATE POLICY p_read_mf_stock_holdings ON mf_stock_holdings FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS p_read_stock_financials ON stock_financials;
CREATE POLICY p_read_stock_financials ON stock_financials FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS p_read_stock_predictions ON stock_predictions;
CREATE POLICY p_read_stock_predictions ON stock_predictions FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS p_read_concall_analyses ON concall_analyses;
CREATE POLICY p_read_concall_analyses ON concall_analyses FOR SELECT TO anon, authenticated USING (true);

-- 2. Write-Access Restricted to service_role (Admin & Backend Ingestion Workers)
DROP POLICY IF EXISTS p_admin_index_stocks ON index_stocks;
CREATE POLICY p_admin_index_stocks ON index_stocks FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS p_admin_mf_schemes ON mf_schemes;
CREATE POLICY p_admin_mf_schemes ON mf_schemes FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS p_admin_mf_stock_holdings ON mf_stock_holdings;
CREATE POLICY p_admin_mf_stock_holdings ON mf_stock_holdings FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS p_admin_stock_financials ON stock_financials;
CREATE POLICY p_admin_stock_financials ON stock_financials FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS p_admin_stock_predictions ON stock_predictions;
CREATE POLICY p_admin_stock_predictions ON stock_predictions FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS p_admin_concall_analyses ON concall_analyses;
CREATE POLICY p_admin_concall_analyses ON concall_analyses FOR ALL TO service_role USING (true) WITH CHECK (true);
