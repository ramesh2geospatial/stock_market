# Indian Mutual Fund Activity & Holdings Discovery — Domain Model Glossary

This document defines the canonical domain terminology, ubiquitous language, and product vision for the **Mutual Fund Holdings & Smart Money Tracker** platform.

---

## 🎯 App Vision & Core Goal: Retail Investor Smart Money Tracker

### 💡 Core Mission
The primary objective of the app is to empower retail Indian stock market investors to **track Smart Money (Mutual Fund buying & selling trends)** in real time so they can:
1. **Discover High-Conviction Institutional Accumulations**: See which stocks top fund managers (*Parag Parikh*, *SBI Bluechip*, *Nippon Small Cap*, *HDFC*) are aggressively buying across **Large, Mid, Small, and Micro Cap** tiers.
2. **Avoid Institutional Dumps & Liquidations**: Spot stocks where mutual funds are reducing stakes or executing complete exits.
3. **Build Winning Personal Portfolios**: Use institutional consensus, stock-level fund ownership metrics, and fund-to-fund overlap analysis to build and rebalance a robust stock portfolio.

---

## 🏛️ Market Capitalization Tiers & Categorization (SEBI Framework)

### 1. Large-Cap Stocks (Rank 1 – 100)
Top 100 Indian companies by market capitalization (e.g. *Reliance*, *HDFC Bank*, *TCS*, *Zomato*). High liquidity, low volatility, heavily held by Large Cap, Index, and Flexi Cap mutual funds.

### 2. Mid-Cap Stocks (Rank 101 – 250)
Companies ranked 101st to 250th in market capitalization (e.g. *Polycab*, *L&T Technology Services*). Growth phase companies held by Mid Cap, Large & Mid Cap, and Multi Cap funds.

### 3. Small-Cap Stocks (Rank 251 – 500)
Companies ranked 251st to 500th in market capitalization (e.g. *BSE Ltd.*, *CDSL*). Higher growth potential with elevated volatility, held by Small Cap and Sectoral funds.

### 4. Micro-Cap Stocks (Rank 501+)
Companies ranked beyond 500th in market capitalization (e.g. *Senco Gold*). Niche companies, emerging turnaround plays, and high-conviction small fund positions.

---

## 📊 Stock-Level Mutual Fund Ownership Metrics

### 1. Pure Mutual Fund Ownership % vs. Total DII Ownership %
- **Pure Mutual Fund Ownership %**: The percentage of outstanding equity held specifically by SEBI-registered Asset Management Companies (Mutual Funds), excluding Insurance, NPS, and Banks:
\[
\text{Pure MF \%} = \frac{\sum \text{Shares Held by Pure MF Schemes}}{\text{Total Outstanding Shares}} \times 100
\]
- **Total DII Ownership %**: The comprehensive domestic institutional ownership as reported in stock exchange LODR Regulation 31 disclosures, encompassing 4 distinct domestic tiers:
\[
\text{Total DII \%} = \text{Pure MF \%} + \text{Insurance/LIC \%} + \text{Pension/NPS Trusts \%} + \text{Banks/Domestic FIs \%}
\]

### 2. Free-Float Institutional Absorption %
The percentage of the company's publicly tradable float (excluding non-tradable Promoter & Government lock-ins) absorbed by mutual funds:
\[
\text{Free-Float MF Absorption \%} = \frac{\sum \text{Shares Held by MF Schemes}}{\text{Total Shares} - (\text{Promoter Shares} + \text{Government Shares})} \times 100
\]

### 3. Active Alpha Funds vs. Passive Index/ETFs
- **Active Alpha Schemes**: Actively managed funds (Flexi Cap, Large & Mid Cap, Small Cap, Focus Funds) where buying/selling represents a fund manager's explicit conviction stock-picking decision.
- **Passive Index / ETFs**: Rule-based tracking funds (Nifty 50 ETF, BSE Sensex ETF) where holding changes are purely mandated by benchmark rebalancing and systematic SIP inflows, carrying zero stock-picking Alpha signal.
- **Active Smart Money Conviction Score**:
\[
\text{Active Conviction Score} = \sum (\text{Active Fund Net Share Additions} \times \text{Fund Portfolio Weight \%})
\]

### 4. Dynamic Live Float Valuation
Calculates current real-time holding value by multiplying statutory disclosed shares by live market price:
\[
\text{Live Holding Value (₹ Cr)} = \frac{\text{Statutory Disclosed Shares} \times \text{Live Stock Price}}{10^7}
\]
Preserves the statutory snapshot value as the historical baseline for MoM unrealized gains/losses.

### 5. Scheme Count (MF Diversity Index)
The total number of distinct mutual fund schemes that hold at least 1 share of the target stock in their portfolio disclosure.

### 6. MoM Net Institutional Drift
The net change in aggregate shares held by all mutual funds between Month \(T\) and Month \(T-1\):
\[
\text{Net Drift} = \sum \text{Shares}_i(T) - \sum \text{Shares}_i(T-1)
\]

### 7. High-Conviction Micro/Small-Cap Gem
A Micro-Cap or Small-Cap stock where mutual fund scheme ownership is concentrated in 3 or fewer schemes, but holds >2% of the scheme's portfolio weight (signifying a high-conviction bet by a fund manager).


---

## 🏛️ Institutional Mutual Fund Buying & Selling Terminology

### 1. Scheme Holdings Snapshot
The complete list of underlying securities (stock names, ISINs, share quantities, market values, and portfolio weight %) held by a mutual fund scheme as disclosed in statutory monthly disclosures by the 10th of every month.

### 6. Institutional MF Holdings Drilldown Modal (`MFDrilldownSheet`)
An interactive slide-up bottom sheet modal providing institutional-grade ownership intelligence across 4 dedicated analytical views: Summary & Free-Float metrics, Scheme Master Table with multi-column sorting, AMC Concentration Matrix, and 6-Month Historical Accumulation Drift. Documented in [ADR 0011](file:///d:/GeoNagrik/Dev/git/stock_market/docs/adr/0011-institutional-mf-holdings-drilldown-modal.md).

### 7. Provider Rate-Limit Shield & Opportunistic Ingestion Architecture
A hybrid two-tier ingestion domain model decoupling low-frequency jittered background watermark sync from crowdsourced opportunistic edge cache-warming. Guarantees zero upstream IP blacklisting by limiting central requests to $< 0.001\text{ req/sec}$ while serving all mobile clients from Supabase Cloud PostgREST in $\le 50\text{ ms}$. Documented in [ADR 0012](file:///d:/GeoNagrik/Dev/git/stock_market/docs/adr/0012-anti-blocking-distributed-ingestion-architecture.md).

### 2. Month-over-Month (MoM) Portfolio Diff
The quantitative delta calculated by comparing a scheme's portfolio snapshot at Month \(T\) against Month \(T-1\):
\[
\Delta \text{Quantity}_i = \text{Quantity}_i(T) - \text{Quantity}_i(T-1)
\]

### 3. Fresh Addition (New Entry)
A security where \(\text{Quantity}(T-1) = 0\) and \(\text{Quantity}(T) > 0\). Indicates a fund manager initiating a new position in a company.

### 4. Complete Exit (Total Dump)
A security where \(\text{Quantity}(T-1) > 0\) and \(\text{Quantity}(T) = 0\). Indicates a fund manager completely liquidating a stock holding.

### 5. Stake Increase (Accumulation / Buying)
A security where \(\Delta \text{Quantity}_i > 0\). Represents incremental buying or averaging up by fund managers.

### 6. Stake Reduction (Distribution / Selling)
A security where \(\Delta \text{Quantity}_i < 0\). Represents profit-taking or trim actions by fund managers.

---

## 🏗️ Storage & Data Pipeline Architecture

### 1. Benchmark Index Universe (NSE & BSE)
The system structures its equity universe directly on official SEBI/AMFI benchmark indices:
- **Nifty 50 & Nifty Next 50** (Large Cap: 102 Official Stocks)
- **Nifty Midcap 150** (Mid Cap: 150 Official Stocks)
- **Nifty Smallcap 250** (Small Cap: 250 Official Stocks)
- **Nifty Microcap 250 & BSE Allcap** (Micro Cap: 253 Official Stocks)

Auto-fetching pipelines (`scripts/fetch_index_constituents.py`) sync official NSE CSV constituent feeds to ensure 100% full coverage (755 total listed stocks) across all listed NSE & BSE companies held by mutual funds.

### 2. Live Data Scraping & Institutional Shareholding Engine
- **Screener.in Real Shareholding Integration**: Dynamically scrapes live quarterly/yearly shareholding patterns (`#shareholding` section on Screener.in), extracting real-time **DII Ownership %**, **FII Ownership %**, **Government %**, **Public %**, and **Retail Shareholder Count**.
- **Real Institutional Ownership Valuation**: Computes exact DII holding market value in ₹ Cr (\(DII\% \times \text{Market Cap Cr}\)) and tracks QoQ/MoM institutional accumulation vs distribution signals.
- **Dynamic yfinance Fallback**: On-demand ticker resolution for any newly listed or unindexed stock, automatically calculating market cap tier, sector, and baseline ownership metrics.

### 3. Supabase Cloud + Local SQLite Hybrid Persistence
- **Supabase Cloud (PostgreSQL)**: Central source of truth hosting normalized relational tables (`index_stocks`, `mf_schemes`, `mf_stock_holdings`, `stock_financials`, `stock_predictions`, `concall_analyses`), Materialized Views (`mv_stock_mf_summary`), and PL/pgSQL stored procedures.
- **Local Phone Storage (SQLite / Drift)**: Client-side replica enabling sub-millisecond offline querying with delta sync watermarks.

### 4. Supabase Ingestion Tiers & RPC Contracts
- **Tier 1: Scheduled Jittered Ingestion (`scripts/sync_real_mf_holdings.py`)**: External Python worker executing periodic stealth crawls (<0.001 req/sec) and upserting data via PostgREST.
- **Tier 2: Serverless Cloud Edge Ingestion (`supabase/functions/fetch-mf-holdings`)**: Deno-based on-demand cloud worker fetching external disclosures upon cache miss and writing atomically to PostgreSQL.
- **Atomic Snapshot Contribution RPC (`contribute_stock_holding_snapshot`)**: Secure PL/pgSQL `SECURITY DEFINER` function accepting `(p_symbol TEXT, p_holdings JSONB)` that atomically creates missing scheme records, updates holdings, and logs audit timestamps.
- **Materialized View Concurrent Refresh (`refresh_mv_stock_mf_summary`)**: Background database procedure refreshing `mv_stock_mf_summary` concurrently to serve pre-aggregated dashboard queries with zero table locking.

### 6. Cross-Layer Entity Reconciliation & Sync Watermarking Protocol
- **Cross-Layer Alignment**: Synchronized entity names, column definitions, and JSON structures across Flutter UI, Local SQLite (`storage/sqlite_store.py`), Supabase PostgreSQL DDL (`docs/supabase_schema.sql`), and Cloud Edge Functions (`fetch-mf-holdings`).
- **Compatibility View Layer**: Exposes PostgreSQL view `stock_concalls` over `concall_analyses` to guarantee 100% backwards compatibility for legacy and modern mobile clients.
- **`updated_at` Watermarking**: All incremental delta synchronization requests use `updated_at=gt.{last_synced_at}` to capture in-place row revisions alongside newly inserted records without data loss. Documented in [ADR 0015](file:///d:/GeoNagrik/Dev/git/stock_market/docs/adr/0015-cross-layer-schema-alignment-and-sync-contracts.md).


---

## 🔄 Sync & Cache Architecture

### 1. Incremental Sync
Protocol where client sends last sync timestamp and server returns only rows with `created_at > timestamp`, minimizing bandwidth and latency. Implemented via PostgREST query parameter `?created_at=gt.{last_synced_at}`.

### 2. Sync Watermark
The `last_synced_at` timestamp stored in the `sync_metadata` SQLite table, representing the high-water mark of successfully synced data. Each table (mf_schemes, mf_stock_holdings, index_stocks) tracks its own watermark independently.

### 3. Holdings Summary
Aggregated stock-level view showing total MF schemes holding a stock, total shares held across all schemes, net MoM change, and action distribution (fresh entry count, increase count, decrease count, exit count). Computed from `mf_holdings_cache` via GROUP BY aggregation.

### 4. Dominant Action
The most frequent `holding_action_type` across all schemes for a given stock in a reporting period. If 3 schemes increased and 1 decreased, the dominant action is ACCUMULATION (🟢). Used as the primary signal indicator in the dashboard summary table.

---

## 🗺️ Quad-Layer System Mapping & Feature Governance

The platform architecture bridges four synchronized execution layers:
1. **Local Python Engine & Streamlit Dashboard**: Heavy data scraping, PyMuPDF financial metric extraction, local Ollama / Gemini LLM reasoning, Plotly visualizers, and 12-tab analysis platform (`app.py`).
2. **In-App Mobile (Flutter & Riverpod)**: Fast, native mobile UI, 5 analytical tabs, 4-view institutional drilldown modal (`MFDrilldownSheet`), and on-device privacy-first CAS parser (`cas_parser_service.dart`).
3. **Supabase Cloud PostgreSQL & Edge Layer**: Normalized relational schema (`index_stocks`, `mf_schemes`, `mf_stock_holdings`, `stock_financials`, `stock_predictions`, `concall_analyses`), Materialized Views, PL/pgSQL atomic RPCs, and Deno Edge Functions.
4. **Website & Web Assets Layer**: Responsive HTML5 glassmorphic single-page app (`assets/www/index.html`), 755 constituent stock explorer, and live web dashboards.

Comprehensive feature mapping, schema cross-reconciliation, and divergence governance are formally documented in [Master Feature Documentation](file:///d:/GeoNagrik/Dev/git/stock_market/docs/FEATURE_MAPPING_AND_DIFFERENCES.md) and [ADR 0016](file:///d:/GeoNagrik/Dev/git/stock_market/docs/adr/0016-quad-layer-feature-mapping-and-divergence-governance.md).

---

## 🔍 System Operational Baseline & Improvement Roadmap

The complete operational verification, test health matrix (200/200 tests passed), Flutter clean architecture status (0 issues), and prioritized improvement roadmap (P0/P1/P2) are codified in:
- [Comprehensive System Audit & Functionality Inventory](file:///d:/GeoNagrik/Dev/git/stock_market/docs/COMPLETE_SYSTEM_AUDIT_AND_FUNCTIONALITY_INVENTORY.md)
- [ADR 0017: Comprehensive System Audit, Operational Baseline & Improvement Governance](file:///d:/GeoNagrik/Dev/git/stock_market/docs/adr/0017-comprehensive-system-audit-and-improvement-roadmap.md)
- [ADR 0018: End-to-End Live Data Verification & Resilient Auto-Sync Protocol](file:///d:/GeoNagrik/Dev/git/stock_market/docs/adr/0018-end-to-end-live-data-verification-and-resilient-auto-sync.md)
- [ADR 0019: Eradication of Dummy Data & Live Feed Integration](file:///d:/GeoNagrik/Dev/git/stock_market/docs/adr/0019-eradication-of-dummy-data-and-live-feed-integration.md)


