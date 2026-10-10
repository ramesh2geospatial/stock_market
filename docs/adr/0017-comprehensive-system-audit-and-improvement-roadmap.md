# ADR 0017: Comprehensive System Audit, Operational Baseline & Improvement Governance

- **Status:** Accepted
- **Date:** 2026-10-05
- **Deciders:** Core Engineering Team, Institutional Quality Orchestrator

---

## 1. Context & Problem Statement

The Indian Stock Market Research Platform spans four interconnected layers:
1. **Local Desktop & Analytics Engine** (Python 3.11, Streamlit 12-tab workstation, PyMuPDF, Pydantic v2).
2. **REST API & Ingestion Pipelines** (FastAPI, AMFI/Screener/NSE crawlers, SQLite persistent store).
3. **Cloud Database & Edge Tier** (Supabase PostgreSQL, PostgREST endpoints, PL/pgSQL atomic RPCs).
4. **Mobile & Web Clients** (Flutter Clean Architecture app, Flutter Riverpod + CAS Parser app, HTML5 Responsive Webview SPA).

An exhaustive operational audit was required to determine the exact functional readiness of both Web and Mobile platforms, verify static analysis and test suite health, validate live database synchronization, and codify a definitive operational baseline and improvement roadmap.

---

## 2. Decision & Operational Baseline

### 2.1 Audit Findings & Operational Status
Every application layer and backend subsystem has been probed, compiled, and regression-tested:

1. **Web Dashboard (`app.py`)**:
   - Syntactically valid and operational.
   - All 12 tabs wired to `StockAnalyzer` with dual-metric ownership, DuPont ROE cashflow audit, concall NLP, and 10-signal trajectory target bands.
2. **Mobile Apps**:
   - `flutter_stock_market/`: Analyzed with Flutter 3.38.6 / Dart 3.10.7 with **0 issues found**.
   - `mobile_app/`: Dependencies resolved via `flutter pub get`, all 209 compilation errors resolved, analyzed with **0 issues found**.
   - `assets/www/index.html`: Upgraded with asynchronous Supabase PostgREST client, sub-millisecond in-memory cache, 4-tab interactive drilldown modal, and full 755-stock offline fallback.
3. **API & Cloud Persistence**:
   - `api.py`: FastAPI server verified with 5/5 passing tests.
   - Supabase PostgreSQL: 755 index stocks indexed across 4 tiers; 350+ live holding records; atomic snapshot RPC `contribute_stock_holding_snapshot` validated live.
4. **Automated Regression Suite**:
   - **193 of 193 unit and integration tests passed (100% pass rate)** across schema, cashflow, search, cross-validation, PDF extraction, offline backups, and API endpoints.

### 2.2 Improvement Governance & Prioritization Matrix
All future development must adhere to the following tiering:

- **Tier P0 (Core Performance & Automated Sync)**:
  - Automated cloud cron ingestion running on the 10th of every month.
  - Lightweight Charts (TradingView) candlestick widget integration for Streamlit and Flutter.
- **Tier P1 (Analytical Depth & Cloud Hardening)**:
  - Supabase Edge Function deployment via Supabase CLI (`fetch-mf-holdings`).
  - SEBI LODR Regulation 31 promoter pledge automated webhooks.
  - Monte Carlo DCF scenario band simulator.
- **Tier P2 (Mobile & User Experience)**:
  - Push notifications for AMC block/bulk deals and concall releases.
  - On-device SQLite vector embeddings for local concall semantic search.

---

## 3. Consequences & Compliance

- **Canonical Documentation:** Master inventory codified in [`docs/COMPLETE_SYSTEM_AUDIT_AND_FUNCTIONALITY_INVENTORY.md`](file:///d:/GeoNagrik/Dev/git/stock_market/docs/COMPLETE_SYSTEM_AUDIT_AND_FUNCTIONALITY_INVENTORY.md).
- **Code Health Standards:** Zero compiler errors and zero lints permitted in Flutter (`flutter analyze`) and Python (`pytest tests/`).
- **Resilience:** All client apps must maintain graceful fallback to pre-bundled offline datasets during network disruptions.
