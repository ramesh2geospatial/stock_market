# Changes Report - Milestone 2 Remediation (Worker 2)

## Executive Summary
Remediated 6 critical edge cases in the Multi-Source Document Ingestion Engine (`providers/multi_source_doc_fetcher.py`, `providers/screener_provider.py`, `providers/bse_provider.py`) identified during Challenger evaluation. Added 6 comprehensive unit test functions across `tests/test_multi_source_doc_fetcher.py` and `tests/test_bse_provider.py`.

---

## Code Modifications

### 1. `providers/multi_source_doc_fetcher.py`
- **Deduplication Fix (`deduplicate_documents`)**:
  - Replaced coarse `(symbol, quarter, category)` key truncation with fine-grained title & URL keys: `(symbol, norm_q, category, norm_title)` and `norm_url`.
  - Ensures multiple distinct filings in the same quarter for a category (e.g., Analyst Meet Transcript vs Concall Transcript) are NOT dropped.
- **PDF Magic-Byte & Soft-404 Validation (`download_and_store`)**:
  - Validates `content.startswith(b"%PDF-")` when downloading PDF documents before saving to disk.
  - If content is HTML or soft-404 error text, sets `doc.extraction_status = "failed"`, `doc.local_path = None`, saves status in SQLite index, and avoids writing corrupted HTML into the `.pdf` store.
- **Fallback Short-Circuiting Fix (`fetch_documents`)**:
  - Defined `required_categories = {"transcript", "presentation", "financial_results"}`.
  - Evaluates `required_categories.issubset(found_categories)` after Tier 1 (BSE). If BSE only returns a subset of categories (e.g. results only, missing transcripts/presentations), Tier 2 (Screener) and Tier 3 (NSE) are queried for missing categories rather than being skipped.

### 2. `providers/screener_provider.py`
- **Screener BSE Scrip Code Fallback (`fetch_documents` & `_scrape_section_table`)**:
  - Updated `fetch_documents(self, symbol, bse_scrip_code=None)` and `_scrape_section_table` to check if HTTP GET by ticker symbol returns 404 (e.g., TATAMOTORS).
  - On HTTP 404, attempts fallback request using BSE Scrip code URL (`https://www.screener.in/company/{bse_scrip_code}/`).

### 3. `providers/bse_provider.py`
- **BSE API Error Response Robustness (`fetch_documents` & `fetch_announcements`)**:
  - Updated `fetch_announcements()` to filter and return lists of dictionaries.
  - Updated `fetch_documents()` with `isinstance(announcements, list)` and `isinstance(item, dict)` guards to prevent uncaught `AttributeError` when BSE API returns string error payloads (e.g. rate limit error text) or lists containing non-dict items.
- **Quarter Label Normalization Alignment (`resolve_quarter_from_filing_date`)**:
  - Aligned month mapping so March filing dates (e.g. `2026-03-15`) map to `Q4` (e.g. `Q4 FY26`), matching `normalize_quarter_label()`.

---

## Unit Tests Added

### 1. `tests/test_multi_source_doc_fetcher.py`
- `test_deduplicate_documents_distinct_filings_same_quarter_category`: Tests that Analyst Meet and Concall Transcripts in the same quarter are both retained, while duplicate copies across sources are deduplicated.
- `test_download_and_store_pdf_magic_byte_validation`: Tests that HTML soft-404 payloads fail PDF validation without being written to disk, while valid `%PDF-` content succeeds.
- `test_fallback_not_short_circuited_when_tier1_partial`: Tests that when Tier 1 (BSE) yields only financial results, Tier 2 (Screener) is queried to fetch missing transcripts/presentations.
- `test_screener_bse_scrip_code_fallback`: Tests that when ticker symbol request returns 404, Screener provider falls back to BSE Scrip code URL.

### 2. `tests/test_bse_provider.py`
- `test_bse_api_error_response_robustness`: Tests handling of string error payloads and non-dict items returned by BSE API.
- `test_resolve_quarter_march_filing_date_maps_to_q4`: Tests that March filing dates resolve to `Q4 FYyy`, aligned with `normalize_quarter_label()`.
