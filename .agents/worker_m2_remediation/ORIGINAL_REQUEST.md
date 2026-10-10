## 2026-07-24T15:33:15Z
<USER_REQUEST>
You are Worker 2 tasked with remediation of Milestone 2 (Multi-Source Document Ingestion Engine).

Working Directory: d:\GeoNagrik\Dev\git\stock_market\.agents\worker_m2_remediation\
Project Root: d:\GeoNagrik\Dev\git\stock_market\

Challenger Feedback & Required Fixes:
1. Deduplication Fix (`providers/multi_source_doc_fetcher.py`):
   - Update `deduplicate_documents()` so that multiple distinct filings in the same quarter for a category (e.g., Analyst Meet Transcript vs Concall Transcript) are NOT dropped. Deduplicate using a finer key incorporating normalized document title or URL.
2. PDF Magic-Byte & Soft-404 Validation (`providers/multi_source_doc_fetcher.py`):
   - In `download_and_store()`, validate that downloaded content begins with PDF magic bytes `%PDF-` before saving as `.pdf` and setting `extraction_status = "success"`. If content is HTML or error text, flag extraction error and do not save corrupted HTML into PDF store.
3. Fallback Short-Circuiting Fix (`providers/multi_source_doc_fetcher.py`):
   - Update `fetch_documents()` so Tier 2 (Screener) and Tier 3 (NSE) are NOT completely skipped if Tier 1 (BSE) only returns a subset of required document categories (e.g. results only, missing transcripts/presentations). Ensure Tier 2 and Tier 3 are queried for missing categories.
4. Screener BSE Scrip Code Fallback (`providers/screener_provider.py` / `multi_source_doc_fetcher.py`):
   - When fetching Screener company page by symbol returns HTTP 404 (e.g. TATAMOTORS), attempt fallback using BSE Scrip code URL (e.g., `https://www.screener.in/company/{bse_scrip_code}/`).
5. BSE API Error Response Robustness (`providers/bse_provider.py`):
   - Ensure `BSEProvider.fetch_documents()` checks `isinstance(announcements, list)` and `isinstance(item, dict)` to avoid uncaught `AttributeError` when BSE API returns string error payloads.
6. Quarter Label Normalization Alignment (`providers/bse_provider.py`):
   - Align `resolve_quarter_from_filing_date()` so March filing dates (e.g. `2026-03-15`) map to `Q4` (e.g. `Q4 FY26`), matching `normalize_quarter_label()`.

Verification Requirements:
- Run pytest (`python -m pytest -o pythonpath=.`) to ensure all unit tests pass cleanly.
- Add unit tests in `tests/test_multi_source_doc_fetcher.py` and `tests/test_bse_provider.py` covering these 6 edge cases.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

When completed, write `changes.md` and `handoff.md` in your working directory and notify parent via send_message.

</USER_REQUEST>
