# ADR 0016: Quad-Layer Feature Mapping & Divergence Governance

## Context & Problem Statement
The Indian Stock Market Research Platform operates across four distinct technical environments:
1. **Local Python Analysis Engine & Streamlit Dashboard** (`app.py`, `stock_analyzer.py`, SQLite `data/portfolio.db`)
2. **Flutter Mobile Application** (`flutter_stock_market/`, `mobile_app/`)
3. **Supabase Cloud PostgreSQL & Edge Layer** (`docs/supabase_schema.sql`, Edge Functions)
4. **Website & Web Assets Layer** (`index.html`, Glassmorphic SPA, Streamlit Web)

As new features are developed (e.g., Ground-Truth PDF Metric Extraction, 10-Signal Institutional Trajectory Matrix, Dual-Metric Ownership, and On-Device CAS Parsing), each layer had evolved varying levels of fidelity, compute models, and persistence mechanisms. A formal architectural decision is required to define the boundary contracts, data ownership, compute distribution, and feature divergence rules across all four layers.

## Decision Drivers
- **Separation of Concerns**: Heavy PDF binary parsing and long-running scrapers must not run on mobile client devices.
- **Privacy First**: Retail investor CAS (Consolidated Account Statements) must remain 100% on-device and never touch cloud or backend databases.
- **Low Latency (<50ms)**: Mobile and Web UI reads must be served from Supabase PostgREST edge caches or inlined datasets rather than hitting slow upstream exchange servers.
- **Single Source of Truth**: Database schemas, column definitions, and ENUMs must remain strictly reconciled across PostgreSQL, SQLite, and Dart models.

## Considered Options
1. **Monolithic Backend Model**: Force all features (mobile, web, local) to route through a single centralized Python backend server.
2. **Disconnected Independent Apps**: Allow mobile, web, and local tools to evolve separate schemas and distinct APIs independently.
3. **Quad-Layer Hybrid Edge Architecture (Selected)**: Centralize master storage and pre-aggregated summaries in Supabase Cloud PostgreSQL, run heavy compute/scrapers in Local Python workers, execute client-side math and privacy parsers on Mobile Dart, and deliver ultra-fast glassmorphic experiences on Web/Mobile.

## Decision Outcome
Adopted **Option 3: Quad-Layer Hybrid Edge Architecture**.

### Layer Responsibilities & Governance:
| Layer | Primary Responsibility | Compute Model | Data Persistence |
| :--- | :--- | :--- | :--- |
| **🖥️ Local Python Engine** | Heavy document ingestion, PDF metric extraction, multi-source scraping, batch screener | Python 3.11+, PyMuPDF, Local Ollama / Gemini, FastAPI | Local SQLite (WAL), Parquet Store, FileCache |
| **📱 In-App Mobile (Flutter)** | Interactive UI, stock exploration, scheme drilldown, personal portfolio CAS parsing | Flutter / Dart, `DuPontCalculator`, `SignalMatrix`, Client Gemini API | In-memory cache, Drift / SQLite offline replica |
| **☁️ Supabase Cloud** | Centralized catalog, relational joins, pre-computed analytics, edge crawling | PostgreSQL 15+ PL/pgSQL, Deno Serverless Edge Workers | Relational DB, Materialized Views, RLS Policies |
| **🌐 Website & Web Assets** | High-performance responsive showcase, instant index navigation, retail discovery | Vanilla JS, Web Standards, CSS Glassmorphism, Streamlit Web | PostgREST API / Inlined JSON fixtures |

### Boundary Rules & Divergence Governance:
1. **Heavy Binary Extraction**: PDF ground truth parsing is restricted to the Local Python Engine; mobile clients consume structured JSON summaries with confidence badges.
2. **CAS Privacy Guarantee**: CAS PDF parsing is strictly isolated to on-device Dart execution (`cas_parser_service.dart`). No CAS data may be sent to Supabase or external APIs.
3. **Delta Sync Compliance**: All mobile queries for synchronization must use the `updated_at=gt.{watermark}` parameter.

## Consequences
### Positive:
- Mobile app remains ultra-lightweight (<30MB) while offering sub-50ms query speeds.
- Full privacy compliance with Indian data privacy norms for personal investor statements.
- Complete feature audit and schema parity documented in [`docs/FEATURE_MAPPING_AND_DIFFERENCES.md`](file:///d:/GeoNagrik/Dev/git/stock_market/docs/FEATURE_MAPPING_AND_DIFFERENCES.md).

### Negative / Trade-offs:
- Requires maintaining Dart mathematical calculators (`DuPontCalculator`) in sync with Python equivalents (`financial_scorer.py`).
- Requires periodic batch runs to keep Supabase predictions and materialized views fresh.
