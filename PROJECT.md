# Project: Indian Stock Market Research Platform - Concall Engine Upgrade

## Architecture
- **Dashboard UI (`app.py`)**: Streamlit-based 11-tab platform featuring concall analysis, cross-quarter intelligence, spider charts, valuation, and confidence badges.
- **Orchestrator (`stock_analyzer.py`)**: Central coordinator connecting data providers, analyzers, storage layers, and prediction engine.
- **Data Providers (`providers/`)**:
  - `screener_provider.py`: Financial tables, quarterly balance sheets, P&L, concall transcripts.
  - `bse_provider.py` / `document_fetcher.py` (New/Upgraded): Multi-source ingestion (BSE Corporate Announcements API -> Screener.in -> NSE Filings fallback) for transcripts, investor presentation PDFs, and financial result PDFs.
  - `yfinance_provider.py`: Real-time quotes, historical price series, valuation metrics.
  - `vahan_provider.py`: MoRTH electric vehicle registration data.
  - `insider_data_provider.py`: Promoter buying, bulk deals, delivery volume %.
  - `local_llm_provider.py`: Local Ollama API / Gemini 2.5 Flash fallback.
- **Analyzers (`analyzers/`)**:
  - `gemini_analyzer.py`: AI concall transcript extraction & structured sentiment parsing.
  - `pdf_ground_truth_extractor.py` (New): Financial metric extraction (Revenue, EBITDA, Net Profit, Segment Results, Capex, Guidance) from Investor Presentation & BSE/NSE Result PDFs.
  - `cross_validator.py` (New): Metric divergence calculator, auto-correction engine (>15% divergence threshold), and confidence badge generator (🟢 high, 🟡 medium, 🔴 low).
  - `intelligence_engine.py`: 10-quarter cross-quarter synthesis, promise delivery tracking, credibility index.
  - `consensus_analyzer.py`: Consensus Expectation Surprise Delta.
  - `prediction_engine.py`: 10-Signal Matrix aggregation.
- **Storage Layer (`storage/`)**:
  - `sqlite_store.py`: Persistent database storing watchlists, notes, concall analysis, milestone tracks, cashflow caches, ground truth metrics, and cross-validation flags.
  - `cache.py`: FileCache TTL JSON storage for API network responses.

## Code Layout
```
d:/GeoNagrik/Dev/git/stock_market/
├── app.py
├── stock_analyzer.py
├── providers/
│   ├── screener_provider.py
│   ├── document_fetcher.py (or bse_provider.py / multi_source_fetcher.py)
│   ├── yfinance_provider.py
│   ├── vahan_provider.py
│   ├── insider_data_provider.py
│   └── local_llm_provider.py
├── analyzers/
│   ├── gemini_analyzer.py
│   ├── pdf_ground_truth_extractor.py
│   ├── cross_validator.py
│   ├── intelligence_engine.py
│   ├── consensus_analyzer.py
│   └── prediction_engine.py
├── storage/
│   ├── sqlite_store.py
│   └── cache.py
└── tests/
    ├── test_*.py
```

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration & Architecture Mapping | Codebase discovery, file structure mapping, test suite audit | None | DONE |
| 2 | Multi-Source Document Ingestion Engine | BSE -> Screener -> NSE fallback fetching for transcripts, presentations & result PDFs | M1 | DONE |
| 3 | Ground-Truth PDF Metric Extraction Engine | Financial metric extraction from Investor Presentation & Result PDFs | M1 | DONE |
| 4 | Cross-Validation & Hallucination Defense | Metric divergence calculation, >15% auto-correction, SQLite schema update | M2, M3 | DONE |
| 5 | Streamlit UI Integration & Badging | `app.py` update with confidence badges (🟢, 🟡, 🔴) & ground truth display | M4 | DONE |
| 6 | E2E Test Suite Verification & Hardening | 100% test coverage for all modules, 193 unit & integration tests passing | M1-M5 | DONE |
| 7 | Full System Audit & Multi-Client Hardening | Complete web & mobile audit, 0 flutter lints, ADR 0017 governance | M6 | DONE |

## System Audit & Documentation Links
- **Master System Audit & Functionality Inventory:** [`docs/COMPLETE_SYSTEM_AUDIT_AND_FUNCTIONALITY_INVENTORY.md`](file:///d:/GeoNagrik/Dev/git/stock_market/docs/COMPLETE_SYSTEM_AUDIT_AND_FUNCTIONALITY_INVENTORY.md)
- **Quad-Layer Feature Mapping & Differences:** [`docs/FEATURE_MAPPING_AND_DIFFERENCES.md`](file:///d:/GeoNagrik/Dev/git/stock_market/docs/FEATURE_MAPPING_AND_DIFFERENCES.md)
- **Architecture Decision Record 0017:** [`docs/adr/0017-comprehensive-system-audit-and-improvement-roadmap.md`](file:///d:/GeoNagrik/Dev/git/stock_market/docs/adr/0017-comprehensive-system-audit-and-improvement-roadmap.md)


## Interface Contracts
### `document_fetcher` (Provider) ↔ `stock_analyzer`
- `fetch_latest_documents(ticker: str, period: str = None) -> Dict[str, Any]`
  - Output dict keys: `concall_transcript_url`, `investor_presentation_url`, `quarterly_results_pdf_url`, `source_used` ('BSE', 'Screener', 'NSE'), `raw_pdf_bytes` / local paths.

### `pdf_ground_truth_extractor` (Analyzer) ↔ `cross_validator`
- `extract_ground_truth_from_pdf(pdf_source: Union[str, bytes], doc_type: str) -> Dict[str, Any]`
  - Output dict keys: `revenue`, `ebitda`, `net_profit`, `segment_results`, `capex`, `guidance`, `extraction_confidence`.

### `cross_validator` (Analyzer) ↔ `app.py` / `sqlite_store`
- `cross_validate_concall(concall_data: Dict[str, Any], ground_truth_data: Dict[str, Any]) -> Dict[str, Any]`
  - Output dict keys: `divergence_map`, `confidence_badge` ('🟢 High Confidence', '🟡 Medium Confidence', '🔴 Low Confidence'), `auto_corrected_data`, `is_autocorrected` (True/False).
