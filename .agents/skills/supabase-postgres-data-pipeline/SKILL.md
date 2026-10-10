---
name: supabase-postgres-data-pipeline
description: Supabase PostgreSQL data pipeline, schema design, PL/pgSQL RPC functions, RLS security hardening, and high-performance financial data ingestion. Use when reviewing, building, or auditing Supabase databases, writing Edge Functions, designing delta sync protocols, or optimizing PostgreSQL queries.
---

# Supabase & PostgreSQL Data Pipeline Engineering Skill

This skill defines institutional standards, design patterns, and audit workflows for **Supabase PostgreSQL Cloud Storage & Ingestion Pipelines** in financial market platforms.

---

## 🏛️ 1. Architecture & Ingestion Strategy

### Tiered Ingestion Framework
1. **Tier 1: Scheduled Batch ETL (`scripts/`)**:
   - Central Python workers executing stealth, jittered crawling (`3.5s - 6.5s` delays, rotating user-agents).
   - Ingests large datasets (NSE index constituent CSVs, monthly AMFI disclosures) using batch PostgREST requests.
2. **Tier 2: Serverless Cloud Edge Ingestion (`supabase/functions/`)**:
   - Supabase Deno Edge Functions triggered on-demand by client apps on cache misses.
   - Executes external API queries, parses HTML/JSON payloads, and writes atomically to PostgreSQL using `service_role` credentials.
3. **Storage & Persistence Tier (PostgreSQL Cloud)**:
   - Houses normalized tables (`index_stocks`, `mf_schemes`, `mf_stock_holdings`, `stock_financials`, `stock_predictions`, `concall_analyses`).
   - Serves reads to Flutter/Web clients via PostgREST with sub-50ms latency.
4. **Client-Side Storage (SQLite / Drift)**:
   - Local phone replica utilizing incremental timestamp watermarks (`GET /rest/v1/table?created_at=gt.{last_synced_at}`).

---

## 🛡️ 2. PostgreSQL Security & Row Level Security (RLS) Rules

### ❌ Anti-Pattern: Permissive Public Writes
```sql
-- DANGEROUS: Grants full write/delete permissions to anyone holding the public anon key!
CREATE POLICY p_all ON my_table FOR ALL TO public USING (true) WITH CHECK (true);
```

### ✅ Best Practice: Least-Privilege Separation
```sql
-- 1. Enable RLS on all public tables
ALTER TABLE my_table ENABLE ROW LEVEL SECURITY;

-- 2. Read-only access for anonymous and authenticated clients
CREATE POLICY p_read_my_table ON my_table
    FOR SELECT TO anon, authenticated
    USING (true);

-- 3. Restrict mutations (INSERT, UPDATE, DELETE) strictly to service_role
CREATE POLICY p_admin_my_table ON my_table
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);
```

---

## ⚡ 3. High-Performance Indexing & Query Optimization

### Indexing Guidelines for Financial Time-Series
- **Fuzzy Autocomplete**: Use `pg_trgm` GIN indexes for ticker symbols and company names:
  ```sql
  CREATE EXTENSION IF NOT EXISTS "pg_trgm";
  CREATE INDEX idx_stocks_symbol_trgm ON index_stocks USING gin (symbol gin_trgm_ops);
  ```
- **Incremental Delta Sync**: Always index `created_at` and `updated_at` to avoid full table scans:
  ```sql
  CREATE INDEX idx_holdings_created_at ON mf_stock_holdings (created_at);
  CREATE INDEX idx_holdings_updated_at ON mf_stock_holdings (updated_at);
  ```
- **Compound Lookup & Sorting**:
  ```sql
  CREATE INDEX idx_holdings_symbol_date ON mf_stock_holdings (symbol, as_of_date DESC);
  ```
- **JSONB Containment**: GIN indexes on unstructured prediction and sentiment objects:
  ```sql
  CREATE INDEX idx_predictions_signals_gin ON stock_predictions USING gin (signal_matrix);
  ```

---

## 🧩 4. PL/pgSQL Stored Procedures & Atomic RPC Pattern

When performing multi-table writes from external crawlers or mobile clients, use `SECURITY DEFINER` RPCs with `search_path` lockdown:

```sql
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
    v_clean_symbol CITEXT := UPPER(TRIM(p_symbol));
    v_item JSONB;
    v_inserted INT := 0;
BEGIN
    FOR v_item IN SELECT * FROM jsonb_array_elements(p_holdings)
    LOOP
        -- Upsert logic here
        v_inserted := v_inserted + 1;
    END LOOP;

    RETURN jsonb_build_object('success', true, 'records_synced', v_inserted);
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object('success', false, 'error', SQLERRM);
END;
$$;
```

---

## 📊 5. Materialized Views & Concurrent Refresh

For heavy aggregations (e.g. stock-level MF ownership sums across 150,000+ records):
1. Define a Materialized View with a unique index:
   ```sql
   CREATE MATERIALIZED VIEW mv_stock_mf_summary AS
   SELECT symbol, as_of_date, COUNT(DISTINCT scheme_id) AS scheme_count, SUM(shares_held) AS total_shares
   FROM mf_stock_holdings
   GROUP BY symbol, as_of_date;

   CREATE UNIQUE INDEX idx_mv_summary_symbol_date ON mv_stock_mf_summary (symbol, as_of_date);
   ```
2. Refresh concurrently to prevent table read locks:
   ```sql
   CREATE OR REPLACE FUNCTION refresh_mv_stock_mf_summary()
   RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER AS $$
   BEGIN
       REFRESH MATERIALIZED VIEW CONCURRENTLY mv_stock_mf_summary;
   END;
   $$;
   ```
