# CHALLENGE REPORT — Milestone 2 (Multi-Source Document Ingestion Engine)

**Role**: Challenger 2 (Empirical Challenger)  
**Date**: 2026-07-24  
**Target Module**: `providers/multi_source_doc_fetcher.py`, `storage/sqlite_store.py` (`documents_index`), `tests/test_multi_source_doc_fetcher.py`  
**Verdict**: **FAIL**

---

## 1. Executive Summary

While the default pytest test suite (`97 passed in 28.37s`) passes existing shallow unit tests, empirical stress testing using a dedicated adversarial harness (`empirical_test_m2.py`) uncovered **3 critical failure modes** in `MultiSourceDocFetcher` and local document persistence.

---

## 2. Empirical Verification Findings

### 🔴 Bug 1 (CRITICAL): Over-Deduplication of Distinct Documents of Same Category
- **Location**: `providers/multi_source_doc_fetcher.py`, lines 184–190
- **Observation**:
  `deduplicate_documents` creates two key sets:
  ```python
  key = (doc.symbol, norm_q, doc.category, doc.title)
  key_coarse = (doc.symbol, norm_q, doc.category)
  if key not in seen_keys and key_coarse not in seen_keys:
      seen_keys.add(key)
      seen_keys.add(key_coarse)
      deduped.append(doc)
  ```
- **Failure Scenario**:
  If a company releases **2 distinct documents** in the same quarter for the same category (e.g. *Q1 FY26 Concall Transcript - Main Call* and *Q1 FY26 Analyst Meet Transcript*, OR *Unaudited Financial Results* and *Audited Financial Results* under `financial_results`, OR *Investor Presentation* and *Product Presentation* under `presentation`), `key_coarse` causes the 2nd document to be **silently dropped and discarded**.
- **Empirical Test Result**:
  ```
  AssertionError: 1 != 2 : Multiple distinct documents in same quarter/category should NOT be dropped
  [Empirical Check] Deduplication count for 2 distinct transcripts in same quarter: 1
  ```

---

### 🔴 Bug 2 (HIGH): Corrupted / Soft-404 Non-PDF Ingestion into Storage Index
- **Location**: `providers/multi_source_doc_fetcher.py`, lines 208–234
- **Observation**:
  `download_and_store` checks HTTP status using `resp.raise_for_status()`, but performs **no content/magic-byte validation** on the downloaded bytes.
- **Failure Scenario**:
  When a remote server returns HTTP 200 OK containing HTML content (such as soft 404 error pages, Cloudflare/WAF JS challenge pages, or "Access Denied" HTML notices):
  1. `download_and_store` writes raw HTML bytes into a file named `.pdf` (e.g., `presentation_BSE_cca48c62.pdf`).
  2. It sets `doc.extraction_status = "success"`.
  3. It records the file path, size, and MD5 in SQLite `documents_index`.
- **Empirical Test Result**:
  ```
  [Empirical Check] Corrupted/HTML PDF response status: success, local_path: ...\presentation_BSE_cca48c62.pdf
  [Empirical Check] Saved file header magic bytes: b'<htm'
  [Empirical Check] Is valid PDF magic header? False
  ```
- **Blast Radius**: Downstream PDF parsers (`pdfplumber`, `pypdf`, `fitz`) will throw unhandled syntax errors when attempting to parse corrupt HTML files stored as `.pdf`.

---

### 🟠 Bug 3 (MEDIUM): Tier Fallback Short-Circuit in `fetch_documents`
- **Location**: `providers/multi_source_doc_fetcher.py`, lines 121 & 150
- **Observation**:
  ```python
  if not all_docs:
      # Try Screener
  if not all_docs:
      # Try NSE
  ```
- **Failure Scenario**:
  If Tier 1 (BSE) returns even **one single document** (e.g. 1 old presentation), `all_docs` is non-empty. As a result, Tier 2 (Screener) and Tier 3 (NSE) are **never queried at all**, leaving all missing quarters or document categories completely empty.

---

## 3. Stress Test Results Summary

| Test Case | Scenario | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :--- | :--- |
| `test_dedup_cross_source_priority` | BSE, Screener, NSE duplicates | Keep BSE version | Kept BSE version | **PASS** |
| `test_dedup_multiple_distinct_docs_same_category` | 2 distinct transcripts in Q1 FY26 | Retain both distinct transcripts | 2nd transcript dropped | **FAIL** |
| `test_quarter_normalization` | Date/Month strings | "Jul 2025" -> "Q1 FY26" | Correct normalization | **PASS** |
| `test_local_file_caching_and_sqlite` | Valid PDF download | Save to `data/documents/{sym}/{qtr}/` and index in DB | Directory & DB updated correctly | **PASS** |
| `test_sqlite_db_cache_lookup` | `force_refresh=False` | Return DB records without calling external APIs | Returned DB records | **PASS** |
| `test_edge_case_http_error_404` | HTTP 404 on URL download | Set `extraction_status = "failed"` | Set `extraction_status = "failed"` | **PASS** |
| `test_edge_case_corrupted_pdf_header` | HTTP 200 OK soft 404 HTML | Mark `extraction_status = "failed"` or validate magic bytes | Saved HTML as `.pdf`, marked `success` | **FAIL** |
| `test_edge_case_empty_url` | Document with empty URL | Handled cleanly | Handled cleanly | **PASS** |

---

## 4. Pytest Test Suite Results

- Command executed: `python -m pytest -o pythonpath=.`
- Test count: **97 passed** (28.37s)
- Note: Standard unit tests pass because they use isolated mocks and do not check edge-case payloads or multi-document quarters.

---

## 5. Recommended Mitigations

1. **Fix Deduplication Key**:
   Remove `key_coarse` or deduplicate by matching normalized title similarity / URL MD5 hash rather than dropping all documents of the same category.
2. **Add PDF Magic Byte Validation**:
   In `download_and_store`, verify if content starts with `%PDF-` when target extension is `.pdf`. If not, set `extraction_status = "corrupted"` or `"failed"`.
3. **Fix Tier Aggregation / Fallback**:
   Query Screener and NSE to fill missing categories/quarters rather than stopping completely when BSE returns a single document.
