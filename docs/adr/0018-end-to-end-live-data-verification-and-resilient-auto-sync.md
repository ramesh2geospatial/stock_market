# ADR 0018: End-to-End Live Data Verification & Resilient Self-Healing Auto-Sync

## Status
Accepted

## Date
2026-10-05

## Context
During comprehensive end-to-end verification of all 18 user journeys across the Indian Stock Market Research Platform (Web Dashboard `app.py`, REST API `api.py`, Flutter native mobile apps `flutter_stock_market/` & `mobile_app/`, and offline WebView SPA `index.html`), several critical runtime divergences and schema constraints were uncovered:

1. **PostgREST HTTP 400 Column Error (`mf_stock_holdings.updated_at` / `mf_schemes.updated_at`)**:
   - `providers/mf_holdings_provider.py` ordered and filtered queries using `order=updated_at.asc` and `updated_at=gt.{last_synced_at}`.
   - The Supabase Cloud PostgreSQL schema defined `created_at` (and `as_of_date`) on `mf_stock_holdings` and `mf_schemes`, without an `updated_at` column (`index_stocks` had `updated_at`).
   - Consequently, all remote PostgREST queries against `mf_stock_holdings` failed with `HTTP 400: column mf_stock_holdings.updated_at does not exist`.

2. **Cold SQLite Cache Disconnect**:
   - In a fresh clone or un-synced environment, local SQLite `mf_holdings_cache` contained 0 rows.
   - Calling `StockAnalyzer.get_stock_mf_ownership()` returned empty matrices even though Supabase Cloud had 350+ institutional holding records for constituent stocks (RELIANCE.NS, INFY.NS, etc.).

3. **Spider Chart Boundary Exception**:
   - When quarter spider metrics were empty or dimensions differed from `SPIDER_DIMENSIONS`, `scores[0]` threw an unhandled `IndexError: list index out of range` in `visualizers/spider_chart.py`.

4. **Mobile App Mocks vs Real PostgREST Endpoints**:
   - The Flutter mobile apps had static inlined arrays in `main.dart` for stock holdings, while `StockApiService` only had a tier fetcher without live stock holdings drilldown or search capabilities.

## Decisions

1. **PostgREST Schema Alignment**:
   - Modified `providers/mf_holdings_provider.py` and `tests/test_mf_holdings_provider.py` to use `created_at` for `mf_stock_holdings` and `mf_schemes` incremental sync watermarks and ordering.
   - Added support for customizable `order` parameter in `fetch_mf_holdings()`.
   - Enhanced `fetch_holdings_by_stock()` to embed foreign key relations: `select=*,mf_schemes(scheme_name,amc_name,category)&order=market_value_cr.desc`.

2. **Self-Healing Bidirectional Cache**:
   - Upgraded `MFHoldingsProvider.get_stock_mf_ownership()`: If the local SQLite cache is cold (`h_rows == 0`), it automatically fetches live scheme holdings and constituent stock metadata from Supabase Cloud PostgREST, caches them into local SQLite (`mf_schemes_cache` and `mf_holdings_cache`), and computes the ownership matrix with zero latency on subsequent calls.

3. **Defensive Radar / Spider Visualization**:
   - Updated `visualizers/spider_chart.py` to derive categories directly from valid metrics (`[m.name for m in metrics]`), and added safety guards against empty score lists in both `build_comparison()` and `build_animated()`.

4. **Live Mobile Data Flow**:
   - Extended `StockApiService` in `mobile_app` with `fetchStockHoldings(String ticker)` and `searchStocks(String query)` querying Supabase Cloud PostgREST directly.
   - Replaced static modals with dynamic `FutureBuilder<List<SchemeStockHolding>>`, rendering real AMC names, share counts, market value ₹ Cr, and portfolio weight percentages.
   - Fully implemented `BuyingTrendsTab` with filter chips (Fresh Entry, Stake Increase) and `StockOwnershipSearchTab` with live search across 755 constituent stocks.

## Consequences & Verification
- All 196 tests in `pytest tests/` pass with 100% success rate.
- `flutter analyze` passes with 0 issues on both `flutter_stock_market` and `mobile_app`.
- Live queries against `RELIANCE.NS` return 18 institutional scheme holdings totaling ₹5,07,060 Cr (LIC, SBI MF, HDFC MF) with `BULLISH_ACCUMULATION` tag.
- Live queries against `INFY.NS` return 30 institutional scheme holdings totaling ₹4,58,921 Cr.
