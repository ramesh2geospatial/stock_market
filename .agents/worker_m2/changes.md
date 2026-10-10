# Summary of Changes - Milestone 2: Multi-Source Document Ingestion Engine

## 1. New Provider Modules Created
- **`providers/bse_provider.py`**:
  - Implements `BSEProvider` interfacing with BSE Corporate Submission API (`https://api.bseindia.com/BseIndiaAPI/api/CorporateSubmission/w`).
  - Contains `NSE_TO_BSE_MAPPING` mapping common Indian equities (HDFCBANK -> 500180, RELIANCE -> 500325, INFY -> 500209, etc.) with 6-digit passthrough and suffix stripping (`.NS`/`.BO`).
  - Implements headline classification (`classify_announcement`) into `transcript`, `presentation`, `financial_results`, `annual_report`, `credit_rating`.
  - Implements Indian FY quarter calculation (`resolve_quarter_from_filing_date`) based on filing timestamp.
  - Constructs absolute BSE Live attachment URLs (`https://www.bseindia.com/xml-data/corpfiling/AttachLive/{ATTACHMENTNAME}`).

- **`providers/nse_provider.py`**:
  - Implements `NSEProvider` interfacing with NSE India Corporate Announcements API (`https://www.nseindia.com/api/corporate-announcements`) with cookie management as Tier 3 fallback.

- **`providers/multi_source_doc_fetcher.py`**:
  - Implements `MultiSourceDocFetcher` orchestrating 3-tier fallback fetching: Tier 1 (BSE API) -> Tier 2 (Screener.in) -> Tier 3 (NSE API).
  - Implements cross-source deduplication (`deduplicate_documents`) prioritizing official Exchange API filings over aggregators.
  - Implements quarter normalization (`normalize_quarter_label`).
  - Implements local document persistence (`download_and_store`) storing files under `data/documents/{symbol}/{quarter}/`.
  - Computes MD5 checksums and tracks file byte size, local file path, and extraction status.
  - Integrates with SQLite `documents_index` catalog store.

## 2. Model & Storage Updates
- **`models/stock.py`**:
  - Added `UnifiedDocument` Pydantic model (`symbol`, `quarter`, `title`, `url`, `source_used`, `category`, `local_path`, `checksum`, `filing_date`, `bse_scrip_code`, `file_size_bytes`, `extraction_status`).
  - Updated `DocumentLink` to support optional metadata fields for backward compatibility.

- **`storage/sqlite_store.py`**:
  - Added `documents_index` table schema creation in `_init_db`.
  - Implemented `save_document_index`, `get_documents_index`, and `get_documents_by_symbol_and_quarter`.

## 3. Orchestrator Integration
- **`stock_analyzer.py`**:
  - Imported and initialized `MultiSourceDocFetcher` in `StockAnalyzer`.
  - Updated `fetch_documents` to use `MultiSourceDocFetcher` for multi-source document ingestion while maintaining caching and return contracts.

## 4. Unit Testing
- **`tests/test_bse_provider.py`**:
  - Unit tests covering scrip code resolution, suffix stripping, headline classification, filing date quarter resolution, and API response parsing.
- **`tests/test_multi_source_doc_fetcher.py`**:
  - Unit tests covering 3-tier fallback execution (Tier 1 -> Tier 2 -> Tier 3), cross-source deduplication, quarter normalization, local PDF persistence, MD5 checksum calculation, and SQLite document indexing.

## 5. Verification Results
- Executed `python -m pytest -o pythonpath=.`:
  - Total tests run: 97 passed out of 97 (0 failures, 100% pass rate).
