# HANDOFF REPORT — Challenger 2 for Milestone 2

**Agent**: Challenger 2 (Empirical Challenger)  
**Target Milestone**: Milestone 2 (Multi-Source Document Ingestion Engine)  
**Verdict**: **FAIL**  
**Date**: 2026-07-24  

---

## 1. Observation

1. **Test Suite Execution**:
   - `python -m pytest -o pythonpath=.` executed across entire repo: **97 tests passed** (28.37s).
   - `tests/test_multi_source_doc_fetcher.py` ran 7 tests, all 7 passed.

2. **Empirical Stress Harness Results (`empirical_test_m2.py`)**:
   - **Deduplication Over-Filtering**: Executed `test_dedup_multiple_distinct_docs_same_category` with two distinct documents from BSE for the same symbol ("TCS"), quarter ("Q1 FY26"), and category ("transcript").
     - *Code*: `providers/multi_source_doc_fetcher.py`, lines 184–190.
     - *Result*: `deduplicate_documents` returned only 1 document (`AssertionError: 1 != 2`). The second document was dropped due to `key_coarse = (doc.symbol, norm_q, doc.category)`.
   - **Corrupted PDF Soft-404 Ingestion**: Executed `test_edge_case_corrupted_pdf_header` downloading a PDF URL that returns HTTP 200 OK with HTML content (`b'<html>...</html>'`).
     - *Code*: `providers/multi_source_doc_fetcher.py`, lines 208–234.
     - *Result*: `download_and_store` wrote HTML bytes into `presentation_BSE_cca48c62.pdf`, set `extraction_status = "success"`, and persisted the record in SQLite `documents_index`. File magic bytes header was `b'<htm'`, failing PDF specification.
   - **Tier Fallback Logic**: Inspected lines 121 & 150 of `providers/multi_source_doc_fetcher.py`.
     - *Result*: `if not all_docs:` prevents Screener and NSE from being fetched if BSE returns even a single document.

---

## 2. Logic Chain

1. **Deduplication Defect**:
   - The design intent of `deduplicate_documents` is to resolve duplicates across multiple sources (BSE, Screener, NSE).
   - However, by filtering on `key_coarse = (symbol, quarter, category)` in addition to exact title match, it treats any second document within the same quarter and category as a duplicate regardless of title or source.
   - Therefore, valid distinct filings (e.g. Earnings Call Transcript + Analyst Day Transcript, or Audited vs Unaudited Financial Results) are lost during ingestion.

2. **PDF Header & Soft-404 Vulnerability**:
   - Web servers for financial portals frequently return HTTP 200 OK with HTML error pages when session tokens expire or WAF rate limits trigger.
   - `MultiSourceDocFetcher.download_and_store` relies solely on `requests.get().raise_for_status()`, which passes on HTTP 200.
   - Without magic byte validation (`%PDF-`), invalid HTML responses are stored locally as `.pdf` files and indexed as successful.
   - Downstream parsing engines expecting binary PDFs will fail when attempting to read these corrupted files.

3. **Tier Fallback Logic**:
   - `fetch_documents` relies on `if not all_docs:` before executing Tier 2 and Tier 3 providers.
   - If Tier 1 returns 1 file for an old quarter, Tier 2 and 3 are skipped, causing incomplete document collection for all other quarters.

---

## 3. Caveats

- The current implementation passes all 97 pre-existing unit tests because standard tests do not test multiple distinct documents of the same category per quarter or soft-404 HTML responses.
- Real remote network calls to BSE/NSE APIs were mocked in tests to ensure repeatable, offline empirical verification.

---

## 4. Conclusion

The Milestone 2 implementation for `MultiSourceDocFetcher` and local document persistence **FAILS** empirical validation due to:
1. Over-deduplication dropping legitimate distinct filings within the same category.
2. Ingestion of soft-404 HTML error pages as valid `.pdf` files into `data/documents/` and SQLite `documents_index`.
3. Short-circuiting fallback logic preventing full quarter coverage across sources.

---

## 5. Verification Method

To independently verify these findings:
1. Run the empirical stress test harness:
   `python .agents/challenger_m2_2/empirical_test_m2.py`
2. Observe test failure in `test_dedup_multiple_distinct_docs_same_category` (AssertionError: 1 != 2).
3. Observe print outputs confirming HTML magic bytes (`b'<htm'`) saved under `.pdf` extension with `extraction_status = "success"`.
4. Inspect `providers/multi_source_doc_fetcher.py` lines 184–190 and 208–234.
