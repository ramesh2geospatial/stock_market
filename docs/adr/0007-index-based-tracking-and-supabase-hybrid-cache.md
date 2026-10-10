# ADR 0007: Index-Based Stock Tracking (NSE/BSE) & Supabase-Local Phone Storage Hybrid Cache

- **Status**: Proposed / Under Review (Grill-with-Docs Session)
- **Date**: 2026-08-13
- **Deciders**: Lead Financial Data Architect, Mobile Systems Engineer

---

## 🎯 Context & Key Architecture Questions

1. **Universe Scope**: Should we track stocks strictly based on official **NSE & BSE Indices** (e.g., Nifty 50, Nifty Next 50, Nifty Midcap 150, Nifty Smallcap 250, BSE 500) instead of ad-hoc market scraping, and auto-fetch/analyze all constituent stocks?
2. **Data Storage & Caching**: Is local phone storage cache (SQLite/Drift) sufficient, or do we need **Supabase (PostgreSQL Cloud)**?
3. **External Rate Limits & Server Load**: How do we prevent rate-limiting (HTTP 429) or heavy load on external data sources (AMCs, AMFI, NSE, BSE, Screener, yfinance)?

---

## 💡 Architectural Decisions & Trade-Off Matrix

### 1. Stock Universe: Index-Based Categorization (NSE & BSE Indices)
- **Decision**: Track all ~1,000+ constituent stocks across SEBI/AMFI benchmark indices:
  - **Large Cap**: Nifty 50, Nifty Next 50 (Rank 1–100)
  - **Mid Cap**: Nifty Midcap 150 (Rank 101–250)
  - **Small Cap**: Nifty Smallcap 250 (Rank 251–500)
  - **Micro Cap**: Nifty Microcap 250 + BSE Allcap (Rank 501+)
- **Auto-Fetching Engine**: Standardized SEBI semi-annual index rebalancing lists auto-update stock tickers and market cap rankings every 6 months.

---

### 2. Hybrid Storage Architecture: Supabase Cloud + Local Phone SQLite Cache
- **Why Pure Local Storage Fails**:
  - AMFI monthly disclosures contain ~44 AMCs $\times$ ~1,500 schemes $\times$ ~100 stocks = **~150,000 holding records/month**.
  - Parsing 44 raw AMC ZIP/Excel files on a phone burns battery, CPU, and downloads ~80MB monthly per device.
- **Proposed Hybrid Solution**:
  - **Supabase Cloud (PostgreSQL)**: Serves as the central ETL engine & single source of truth. Runs a automated monthly worker on the 10th of every month to parse raw disclosures and compute MoM diffs (`STAKE_INCREASE`, `FRESH_ENTRY`, `STAKE_REDUCTION`, `COMPLETE_EXIT`).
  - **Local Phone Storage (SQLite / Drift)**: The mobile app syncs a lightweight (~3-5 MB) compressed SQLite db snapshot or delta updates. All stock searches and MF holding drilldowns execute **100% locally with 0ms latency** on device, fully functional offline!

---

### 3. Rate Limit & External Server Load Prevention Policy
- **External Load Strategy**:
  - **Zero Direct Client Requests**: Mobile clients **NEVER** hit AMC, NSE, or Screener websites directly.
  - **Single Batch ETL Pipeline**: Backend worker fetches AMC portfolio files **ONCE per month** (since disclosures are published monthly).
  - **Rate Limiting Protocol**: Throttled requests (max 2 req/sec), User-Agent header rotation, and HTTP response caching with 30-day TTL.

---

## 📋 Consequences & Verification

- **Latency**: 0ms local search on mobile device.
- **Bandwidth**: Mobile app downloads <5MB/month instead of >80MB.
- **External Compliance**: Zero rate limits or IP blocks from AMC or NSE servers.
