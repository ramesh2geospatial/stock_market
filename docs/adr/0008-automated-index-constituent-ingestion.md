# ADR 0008: Automated Index Constituent Ingestion Pipeline (NSE Indices & Supabase Storage)

- **Status**: Proposed / Under Review (Grill-with-Docs Session)
- **Date**: 2026-08-13
- **Deciders**: Lead Financial Data Architect, Mobile Systems Engineer

---

## 🎯 Context & Problem Statement

Users expect to see **100% full constituent stock lists** for every benchmark index across all mobile and web UI screens:
- **Nifty 50**: Exactly 50 stocks (e.g. *Reliance*, *HDFC Bank*, *ICICI Bank*, *TCS*, *Infosys*, *ITC*, *State Bank of India*, *Bharti Airtel*, *L&T*, *Tata Motors*, etc.).
- **Nifty Next 50**: Exactly 50 stocks (e.g. *Zomato*, *DLF*, *HAL*, *REC*, *PFC*, *InterGlobe Aviation*, etc.).
- **Nifty Midcap 150**: All 150 mid-cap constituent stocks.
- **Nifty Smallcap 250**: All 250 small-cap constituent stocks.
- **Nifty Microcap 250 & BSE 500**: All 250 micro-cap and 500 BSE constituent stocks.

Relying on hardcoded sample lists (~18 stocks) leaves 95%+ of mutual fund stock holdings invisible to users.

---

## 💡 Proposed Architecture & Data Pipeline

### 1. Official Ingestion Sources (NSE Indices CSV Feeds)
An automated ingestion worker script (`scripts/fetch_index_constituents.py`) fetches official CSV feeds directly from **NSE Indices (niftyindices.com)**:
- `ind_nifty50list.csv` (Nifty 50)
- `ind_niftynext50list.csv` (Nifty Next 50)
- `ind_niftymidcap150list.csv` (Nifty Midcap 150)
- `ind_niftysmallcap250list.csv` (Nifty Smallcap 250)
- `ind_niftymicrocap250_list.csv` (Nifty Microcap 250)

### 2. Dual Database Ingestion (Supabase Cloud + Local SQLite Cache)
- **Supabase Cloud (PostgreSQL)**: Upserts all ~1,000 constituent stocks with `symbol`, `company_name`, `isin`, `index_name`, `market_cap_tier`, and `sector`.
- **Local SQLite Persistence**: Synchronizes the 1,000-stock master index onto the user's local SQLite database for instant zero-latency offline browsing and filtering.

### 3. Dynamic UI Binding (FastAPI + Flutter + Streamlit)
- **FastAPI Endpoint (`/api/v1/stocks/market-cap-tier/{tier}`)**: Serves paginated/filtered constituent stock lists directly from the database.
- **Streamlit & Flutter UIs**: Replace all static hardcoded arrays with dynamic state loaded directly from the backend API/SQLite store.

---

## 📋 Verification & Testing Plan

1. **Ingestion Verification**: Verify `scripts/fetch_index_constituents.py` downloads and populates:
   - Exactly 50 stocks in Nifty 50.
   - Exactly 50 stocks in Nifty Next 50.
   - Exactly 150 stocks in Nifty Midcap 150.
   - Exactly 250 stocks in Nifty Smallcap 250.
2. **Database Verification**: Query Supabase PostgreSQL and local SQLite database to confirm `COUNT(*)` matches 1,000+ stocks.
3. **UI Verification**: Confirm mobile app and web app scroll through full 50 Nifty 50 stocks without truncating.
