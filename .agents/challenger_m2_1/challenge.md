# Challenge Report — Milestone 2: Multi-Source Document Ingestion Engine

**Verdict**: **FAIL**
**Target Files**: `providers/multi_source_doc_fetcher.py`, `providers/bse_provider.py`
**Challenger**: Challenger 1 (`.agents/challenger_m2_1/`)
**Date**: 2026-07-24

---

## Challenge Summary

**Overall Risk Assessment**: **HIGH**

Empirical stress testing and live endpoint verification revealed multiple critical and high-severity defects in the Multi-Source Document Ingestion Engine:
1. **Total Ingestion Engine Blackout for Major Equities (e.g. `TATAMOTORS`)**: 0 documents retrieved across all 3 tiers.
2. **Uncaught Runtime Crash (`AttributeError`) in `BSEProvider.fetch_documents()`**: Occurs when BSE API returns string/non-list data structures.
3. **Quarter Normalization Month Conflict**: Inconsistent financial quarter calculation between BSE Provider and MultiSourceDocFetcher for boundary filing months (e.g., March).
4. **Partial Tier 1 Coverage Bypasses Fallback**: When BSE returns only 1 document (e.g. financial results), Tier 2 (Screener) is skipped, losing all Concall Transcripts.
5. **Hardcoded 50-Stock BSE Scrip Code Limit**: No dynamic scrip code lookup mechanism for stocks outside the top 50 blue chips.

---

## Challenges & Empirical Findings

### [HIGH] Challenge 1: Total Document Retrieval Blackout for Tickers like `TATAMOTORS`

- **Assumption Challenged**: Multi-source 3-tier fallback ensures high availability for Indian equities.
- **Attack Scenario**: Call `fetch_documents("TATAMOTORS")` on `MultiSourceDocFetcher`.
- **Observed Behavior**:
  - Tier 1 (BSE API): Fails with `JSONDecodeError: Expecting value: line 3 column 1` because BSE blocks raw API requests without cookies.
  - Tier 2 (Screener): `ScreenerProvider` requests `https://www.screener.in/company/TATAMOTORS/`, which returns **HTTP 404 Not Found**. (However, using BSE Scrip code `https://www.screener.in/company/500570/` returns **200 OK**!). `ScreenerProvider` returns 0 documents.
  - Tier 3 (NSE API): Returns empty/blocked payload.
  - **Result**: `MultiSourceDocFetcher.fetch_documents("TATAMOTORS")` returns **0 documents**.
- **Blast Radius**: High. Major Indian equities fail to ingest any quarterly concall transcripts or investor presentations.
- **Suggested Defense**: Modify `ScreenerProvider` to fallback to BSE scrip code (e.g. `500570`) when ticker slug yields 404 on Screener.in.

---

### [HIGH] Challenge 2: Uncaught Runtime Crash (`AttributeError`) on Non-List Announcements

- **Assumption Challenged**: `BSEProvider.fetch_documents()` safely handles arbitrary response formats from BSE API.
- **Attack Scenario**: Mock `fetch_announcements()` to return `data.get("Table")` as a string (`"Server Maintenance Error"`) or list of primitives (`[123, 456]`).
- **Observed Behavior**:
  - `fetch_documents()` loops `for item in announcements:` (line 232) and executes `item.get("HEADLINE", "")`.
  - Calling `.get()` on string `'S'` or int `123` raises `AttributeError: 'str' object has no attribute 'get'`.
  - Process crashes unhandled.
- **Blast Radius**: High. API schema changes or error responses from BSE crash the worker thread.
- **Suggested Defense**: Add `if not isinstance(item, dict): continue` inside `fetch_documents()` iteration loop.

---

### [MEDIUM] Challenge 3: Inconsistent Quarter Calculation for Boundary Filing Months

- **Assumption Challenged**: `BSEProvider.resolve_quarter_from_filing_date()` and `multi_source_doc_fetcher.normalize_quarter_label()` produce identical financial quarter labels for given filing dates.
- **Attack Scenario**: Pass filing date `"2026-03-15T00:00:00"` to both resolvers.
- **Observed Behavior**:
  - `BSEProvider.resolve_quarter_from_filing_date("2026-03-15")` returns **`Q3 FY26`**.
  - `normalize_quarter_label("15 Mar 2026")` returns **`Q4 FY26`**.
- **Blast Radius**: Medium. Leads to mismatched SQLite index records and duplicate documents stored under different quarter names (`Q3 FY26` vs `Q4 FY26`).
- **Suggested Defense**: Unify month-to-quarter mapping rules across `bse_provider.py` and `multi_source_doc_fetcher.py`.

---

### [MEDIUM] Challenge 4: Partial Tier 1 Coverage Bypasses Fallback Engine

- **Assumption Challenged**: Fallback engine ensures all document categories (transcripts, presentations, financial results) are fetched.
- **Attack Scenario**: BSE API returns only 1 `financial_results` PDF, but no `transcript` PDFs.
- **Observed Behavior**:
  - `bse_docs` is non-empty (`len == 1`), so `all_docs` is non-empty.
  - `MultiSourceDocFetcher` executes `if not all_docs:` to decide whether to trigger Tier 2 (Screener).
  - Since `all_docs` is not empty, Screener is skipped entirely. Concall transcripts available on Screener are lost.
- **Blast Radius**: Medium. Missing concall transcripts when BSE API provides incomplete filing records.
- **Suggested Defense**: Trigger category-aware fallbacks (e.g. if `category == 'transcript'` is missing in Tier 1, query Tier 2 for missing categories).

---

### [LOW] Challenge 5: Downloader Treats 0-Byte PDF as Success

- **Assumption Challenged**: `download_and_store()` validates non-empty payload before marking status as `success`.
- **Attack Scenario**: Server responds with HTTP 200 OK but 0 content bytes (`b""`).
- **Observed Behavior**:
  - Downloader writes 0 bytes to file system and sets `extraction_status = "success"` with MD5 `d41d8cd98f00b204e9800998ecf8427e`.
- **Blast Radius**: Low. Empty files indexed as valid documents.
- **Suggested Defense**: Check `if len(content) == 0: doc.extraction_status = "failed"`.

---

## Stress Test Results

| Scenario | Expected Behavior | Actual Behavior | Pass/Fail |
| :--- | :--- | :--- | :--- |
| `fetch_documents("HDFCBANK")` (Live API) | Fetch filings across BSE/Screener | BSE API blocks (HTML JSONDecodeError), Screener fallback fetches 58 docs | **PASS** (Fallback worked) |
| `fetch_documents("TATAMOTORS")` (Live API) | Fetch filings across BSE/Screener | 0 docs fetched across all 3 tiers (Screener 404 on slug) | **FAIL** |
| Malformed announcement string item | Gracefully skip string item | Uncaught `AttributeError` crash | **FAIL** |
| March 15 filing date quarter calculation | Identical quarter label | `BSEProvider` yields `Q3 FY26`, `normalize_quarter_label` yields `Q4 FY26` | **FAIL** |
| Unmapped ticker (ZOMATO) | Fallback to Screener via Scrip Code | 0 docs fetched (Screener slug 404, scrip code not tried) | **FAIL** |
| HTTP 404 on document download | Mark `extraction_status = "failed"` | Marked `extraction_status = "failed"` | **PASS** |

---

## Unchallenged Areas

- Audio recording streaming / transcript speech-to-text conversion (Out of scope for Milestone 2 document fetcher).
