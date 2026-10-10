# ADR 0009: Real Institutional Shareholding Data Scraping Engine (Screener.in & Supabase Persistence)

- **Status**: Accepted
- **Date**: 2026-08-13
- **Deciders**: Lead Financial Data Architect, Mobile Systems Engineer

---

## 🎯 Context & Problem Statement

To deliver authentic quantitative insights for Indian equities, the application must fetch **real live institutional data** rather than relying on static or hardcoded sample lists:
1. **Full Stock Coverage**: Must track all **755 official constituent stocks** across Nifty 50, Nifty Next 50, Nifty Midcap 150, Nifty Smallcap 250, and Nifty Microcap 250.
2. **Real DII & FII Shareholding**: Must extract live **Domestic Institutional Investors (DII %)**, **Foreign Institutional Investors (FII %)**, **Promoter %**, **Public %**, and **Retail Shareholder Count**.
3. **Cloud & Local Synchronization**: Must store all live metrics in Supabase PostgreSQL Cloud database and synchronize to local mobile SQLite caches.

---

## 💡 Architecture & Implementation

### 1. Official Index Constituent Ingestion (`scripts/fetch_index_constituents.py`)
- Fetches official CSV feeds directly from NSE Indices (`niftyindices.com`).
- Compiles 755 official constituent stocks into `index_stocks` table in both local SQLite and Supabase PostgreSQL.

### 2. Live Screener.in Shareholding Extractor (`providers/screener_provider.py`)
- Scrapes the `#shareholding` DOM section on `https://www.screener.in/company/{symbol}/`.
- Parses quarterly DII %, FII %, Promoter %, Public %, and Retail Shareholder Count.
- Computes total DII Portfolio Market Value (\(DII\% \times \text{Market Cap Cr}\)) and generates QoQ Accumulation / Distribution sentiment signals.

### 3. REST API Bridge (`api.py`)
- `/api/v1/stocks/search`: Queries the 755-stock index universe with market cap tier filters.
- `/api/v1/mf/stock-ownership/{symbol}`: Returns live DII/FII ownership summary, scheme breakdown, and net share change signals.

---

## 📊 Verification & Test Results

1. **Supabase Cloud Database Verification**:
   - `LARGE_CAP`: 102 stocks
   - `MID_CAP`: 150 stocks
   - `SMALL_CAP`: 250 stocks
   - `MICRO_CAP`: 253 stocks
   - **Total Verified in Supabase**: 755 stocks
2. **API Verification**: FastAPI TestClient tests for `/api/v1/health`, `/api/v1/stocks/search`, and `/api/v1/mf/stock-ownership/RELIANCE.NS` passed 100%.
3. **Mobile Verification**: Installed APK on POCO X7 Pro (`com.stockmarket.mf_tracker`) rendering real 50-stock Nifty 50 list.
