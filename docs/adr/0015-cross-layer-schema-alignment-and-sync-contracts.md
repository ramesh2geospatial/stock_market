# ADR 0015: Cross-Layer Schema Alignment, Entity Reconciliation, and Delta Watermarking

- **Status**: Accepted
- **Date**: 2026-08-16
- **Deciders**: Lead Financial Data Architect, Mobile Systems Engineer, Backend Database Engineer

---

## 🎯 Context & Problem Statement

An end-to-end architectural audit across the 4 primary application layers:
1. **The App Layer** (Flutter Mobile App & Streamlit Desktop Dashboard)
2. **Local Persistence Layer** (Python SQLite Store `storage/sqlite_store.py` & SQLite cache `data/portfolio.db`)
3. **Cloud Database Layer** (Supabase Cloud PostgreSQL `docs/supabase_schema.sql` & PostgREST REST APIs)
4. **Serverless Edge Layer** (Supabase Edge Function `supabase/functions/fetch-mf-holdings/index.ts`)

revealed critical naming drift and operational discrepancies:
1. **Table Name Divergence**: Flutter requested `/rest/v1/stock_concalls`, whereas Supabase defined `concall_analyses` and SQLite used `concall_analysis`.
2. **Column Naming Asymmetry**:
   - `stock_predictions`: App and live tables expected `current_price`, `stance`, `target_bear`, `target_base`, `target_bull`, `signal_scores`, while DDL defined `trajectory`, `target_price_bull`, `signal_matrix`.
   - `concall_analyses`: App expected `score`, `summary`, `positive_drivers`, `key_risks`, while DDL defined `sentiment_score`, `summary_markdown`, `risk_flags`.
   - `index_stocks`: SQLite used `tier`, `mcap_cr`, while Supabase used `market_cap_tier`, `market_cap_cr`.
3. **Delta Sync Filter Blindspot**: Incremental sync previously filtered on `created_at > last_synced_at`. When holding shares or valuations were revised in-place by subsequent monthly disclosures, `created_at` did not change, causing updated rows to be missed by mobile clients.

---

## 💡 Architectural Decisions

### 1. Unified Entity & Table Compatibility Layer
- **Canonical Table Names**:
  - `index_stocks` (Equities Catalog)
  - `mf_schemes` (Mutual Fund Scheme Metadata)
  - `mf_stock_holdings` (Monthly Scheme Holdings)
  - `stock_financials` (Multi-Year Financial Statements)
  - `stock_predictions` (10-Signal Machine Learning Trajectory Models)
  - `concall_analyses` (AI Earnings Concall Sentiment & Drivers)
- **Zero-Downtime Compatibility View**:
  Created PostgreSQL view `stock_concalls` bridging legacy clients seamlessly to `concall_analyses`:
  ```sql
  CREATE OR REPLACE VIEW stock_concalls AS
  SELECT 
      id, symbol, quarter, transcript_url,
      COALESCE(score, sentiment_score / 100.0, 0.7) AS score,
      sentiment, confidence,
      COALESCE(summary, summary_markdown) AS summary,
      positive_drivers,
      COALESCE(key_risks, risk_flags) AS key_risks,
      COALESCE(guidance_numbers, guidance_notes) AS guidance_numbers,
      created_at, updated_at
  FROM concall_analyses;
  ```

---

### 2. Dual-Column Support & Resilient Deserialization
- Schema DDL and SQLite stores updated with dual-column support:
  - Both `stance` (text) and `trajectory` (enum) supported.
  - Both `target_bear`/`target_base`/`target_bull` and `target_price_bear`/`target_price_base`/`target_price_bull` supported.
  - Both `signal_scores` and `signal_matrix` supported.
- Flutter `UnifiedStockRepository` updated with defensive fallback parsing across all property variants.

---

### 3. `updated_at` Timestamp Watermarking Protocol
- All incremental sync pipelines (`fetch_mf_schemes`, `fetch_mf_holdings`, `fetch_all_holdings_paginated`) updated to filter by `updated_at=gt.{last_synced_at}`.
- Trigger `update_modified_time()` automatically bumps `updated_at` on every row modification, ensuring 100% capture of both new entries and in-place revisions.

---

## 📊 Verification & Test Coverage

- **Automated Regression Suite**:
  ```powershell
  python -m unittest tests/test_supabase_schema.py tests/test_supabase_storage.py tests/test_mf_holdings_provider.py tests/test_offline_storage.py
  ```
  Result: **23/23 tests passing** (100% OK).
