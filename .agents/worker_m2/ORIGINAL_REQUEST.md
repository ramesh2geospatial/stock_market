## 2026-07-24T15:27:00Z
<USER_REQUEST>
You are Worker 1 implementing Milestone 2: Multi-Source Document Ingestion Engine.

Working Directory: d:\GeoNagrik\Dev\git\stock_market\.agents\worker_m2\
Project Root: d:\GeoNagrik\Dev\git\stock_market\

Reference Reports from Milestone 1:
- Explorer 1 Report: d:\GeoNagrik\Dev\git\stock_market\.agents\explorer_m1_1\handoff.md and analysis.md
- PROJECT.md at project root

Task Requirements:
1. Implement `providers/bse_provider.py`:
   - BSE India Corporate Announcements API query support for corporate filings.
   - Mapping dictionary for common NSE tickers to 6-digit BSE scrip codes (HDFCBANK -> 500180, RELIANCE -> 500325, INFY -> 500209, etc.) with ticker fallback logic.
   - Parsing of announcement links for concall transcripts, investor presentations, and financial result PDFs.
2. Implement `providers/multi_source_doc_fetcher.py`:
   - 3-tier fallback fetching strategy: Tier 1 (BSE India Announcements API) -> Tier 2 (Screener.in) -> Tier 3 (NSE India Filings API / fallback).
   - Cross-source deduplication engine (avoiding duplicate documents for the same quarter).
   - Local document file persistence under `data/documents/{symbol}/{quarter}/`.
3. Update `models/stock.py`:
   - Add/update `UnifiedDocument` or `DocumentLink` Pydantic model to include `symbol`, `quarter`, `title`, `url`, `source_used` ('BSE'|'SCREENER'|'NSE'), `category` ('transcript'|'presentation'|'financial_results'), `local_path`, `checksum`, `filing_date`.
4. Update `storage/sqlite_store.py`:
   - Create `documents_index` table schema if not exists.
   - Implement `save_document_index`, `get_documents_index`, `get_documents_by_symbol_and_quarter`.
5. Integrate `MultiSourceDocFetcher` into `stock_analyzer.py`:
   - Update `fetch_documents` to use `MultiSourceDocFetcher`.
6. Write 100% unit tests:
   - Create `tests/test_bse_provider.py` and `tests/test_multi_source_doc_fetcher.py` with full unit test coverage.
   - Verify all existing unit tests pass cleanly (`python -m pytest -o pythonpath=.`).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

When finished, write `changes.md` and `handoff.md` in your working directory and notify parent via send_message.

</USER_REQUEST>
