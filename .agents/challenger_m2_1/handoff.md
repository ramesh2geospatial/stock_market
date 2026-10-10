# Handoff Report — Challenger 1 (Milestone 2)

## 1. Observation

Direct observations and empirical evidence collected during adversarial review:

1. **Live Retrieval Failure for TATAMOTORS**:
   - Command: `python .agents/challenger_m2_1/test_tatamotors_live.py`
   - Output:
     ```
     [BSEProvider] Error fetching announcements for 500570: Expecting value: line 3 column 1 (char 4)
     Total documents fetched for TATAMOTORS across all 3 tiers: 0
     ```
   - Path: `providers/multi_source_doc_fetcher.py`, lines 111-158.

2. **Screener Slug 404 vs Scrip Code 200 OK**:
   - Command: `python .agents/challenger_m2_1/test_screener_scrip.py`
   - Output:
     ```
     URL https://www.screener.in/company/TATAMOTORS/ -> Status: 404
     URL https://www.screener.in/company/500570/ -> Status: 200 OK
     ```
   - Path: `providers/screener_provider.py`, line 34: `url = SCREENER_COMPANY_URL.format(symbol=base)`.

3. **Uncaught AttributeError in BSEProvider**:
   - Path: `providers/bse_provider.py`, lines 232-237:
     ```python
     announcements = self.fetch_announcements(scrip_code)
     for item in announcements:
         headline = item.get("HEADLINE", "")
     ```
   - Command: `python .agents/challenger_m2_1/stress_test_m2.py`
   - Output: `[BUG CONFIRMED] fetch_documents crashed on string announcements: 'str' object has no attribute 'get'`

4. **Quarter Mapping Month Conflict**:
   - Filing date: `"2026-03-15"`
   - `BSEProvider.resolve_quarter_from_filing_date("2026-03-15")` -> `"Q3 FY26"` (`providers/bse_provider.py`, lines 198-201).
   - `normalize_quarter_label("15 Mar 2026")` -> `"Q4 FY26"` (`providers/multi_source_doc_fetcher.py`, lines 61-64).

5. **Partial Tier 1 Coverage Bypasses Fallback**:
   - Path: `providers/multi_source_doc_fetcher.py`, line 122: `if not all_docs:`
   - When BSE returns 1 document (e.g. financial results), `all_docs` is non-empty, skipping Screener and losing all Concall Transcripts.

---

## 2. Logic Chain

1. **Observation 1 & 2**: Live BSE API calls fail due to Cloudflare/headers returning non-JSON HTML, falling back to Screener. However, `ScreenerProvider` constructs URLs using symbol strings (`/company/TATAMOTORS/`), which returns HTTP 404 on Screener.in. Because `ScreenerProvider` does not attempt the BSE 6-digit scrip code (`/company/500570/`), Screener returns 0 documents. Consequently, Tier 1, Tier 2, and Tier 3 all return 0 documents for major equities like `TATAMOTORS`.
2. **Observation 3**: `BSEProvider.fetch_announcements` returns `data.get("Table")`. If BSE returns a string or non-dict list, `BSEProvider.fetch_documents()` iterates over elements without validating `isinstance(item, dict)`. Calling `item.get(...)` on non-dicts raises an uncaught `AttributeError`.
3. **Observation 4**: In `bse_provider.py`, March (Month 3) filing dates map to Q3 FYxx, whereas in `multi_source_doc_fetcher.py`, March filing dates map to Q4 FYxx. This produces divergent quarter labels in SQLite index for the exact same filing date.
4. **Observation 5**: `MultiSourceDocFetcher` checks `if not all_docs:` before invoking Tier 2 (Screener). If Tier 1 returns a single document (e.g. Financial Results PDF), Tier 2 is skipped completely, causing the engine to miss all Concall Transcripts.

---

## 3. Caveats

- **Network Flakiness**: BSE India API blocking can vary by IP address/headers. However, fallback logic MUST be resilient regardless of BSE API block status.
- **Screener HTML Structure**: Screener.in HTML structure may evolve, but using numeric scrip code fallback (`/company/{scrip_code}/`) is confirmed to return 200 OK.

---

## 4. Conclusion

The Multi-Source Document Ingestion Engine (`providers/multi_source_doc_fetcher.py` and `providers/bse_provider.py`) **FAILS** adversarial stress verification. While happier paths pass basic unit tests, live execution and edge cases reveal total document retrieval failure for Nifty 50 stocks like `TATAMOTORS`, uncaught crashes on non-dict BSE responses, and conflicting quarter label calculations.

---

## 5. Verification Method

To independently verify these findings, run the following stress test commands from project root:

```bash
# 1. Run empirical stress harness
python .agents/challenger_m2_1/stress_test_m2.py

# 2. Run live endpoint verification
python .agents/challenger_m2_1/live_stress_m2.py

# 3. Inspect challenge report
cat .agents/challenger_m2_1/challenge.md
```
