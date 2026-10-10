# ADR 0006: Live FastAPI Sync & SQLite Cache for 500+ NSE/BSE Stocks

## Status
Accepted

## Context
The initial client prototype contained a sample subset of stocks. Users require access to the full universe of 500+ Indian equities (including ICICI Prudential, RBL Bank, SBI, TCS, Infosys, Tata Motors, L&T) categorized by SEBI market cap ranks, along with mutual fund holdings and trade actions (`FRESH_ENTRY`, `STAKE_INCREASE`, `STAKE_REDUCTION`, `COMPLETE_EXIT`).

## Decision
1. **Dynamic Backend Sync**: The mobile app fetches dynamic JSON payloads from the local/remote FastAPI server (`/api/v1/stocks/market-cap-tier`, `/api/v1/mf/stock-ownership`, `/api/v1/mf/search`).
2. **Comprehensive Pre-built Index**: The app bundles an extended offline cache of all 500+ NSE/BSE listed companies across Large, Mid, Small, and Micro Cap tiers to ensure instant real-time search even when offline.
3. **Local SQLite Persistence**: Holdings diffs and AMFI NAV updates are cached in SQLite for zero-latency local searching.

## Consequences
- Retail investors can search any Indian stock (e.g. ICICI Prudential, RBL Bank, SBI, HDFC) and instantly view all mutual fund schemes holding or trading the stock.
- The UI remains hyper-responsive without loading spinners during searches.
