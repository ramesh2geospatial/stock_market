# Handoff Report — Challenger 2 (Milestone 3: Ground-Truth PDF Metric Extraction Engine)

**Agent Role**: EMPIRICAL CHALLENGER (critic, specialist)  
**Working Directory**: `d:\GeoNagrik\Dev\git\stock_market\.agents\challenger_m3_2\`  
**Target Milestone**: Milestone 3 — Ground-Truth PDF Metric Extraction Engine  
**Final Verdict**: **FAIL** (Core requirements met; 3 actionable parsing/scaling defects uncovered in edge case payloads)

---

## 1. Observation

Direct observations and evidence collected during empirical test execution:

1. **SQLite Storage & Retrieval (`storage/sqlite_store.py`)**:
   - Table Schema (`ground_truth_financials` lines 208-229): Correctly defines all fields including `revenue_cr`, `ebitda_cr`, `pat_cr`, `revenue_growth_pct`, `ebitda_margin_pct`, `pat_growth_pct`, `segment_results_json`, `capex_cr`, `guidance_numbers_json`, `extraction_confidence`, `extracted_at`, `source_pdf_url`, `source_local_path`, `ground_truth_json`, with `UNIQUE(symbol, quarter, doc_type)`.
   - `save_ground_truth` (lines 744-793): Accepts Pydantic models or dicts, correctly serializes JSON structures, and performs upserts using `INSERT OR REPLACE INTO ground_truth_financials`.
   - `get_ground_truth` (lines 795-832): Correctly queries exact `doc_type` or applies priority fallback (`ORDER BY CASE doc_type WHEN 'financial_results' THEN 1 WHEN 'presentation' THEN 2 ELSE 3 END ASC LIMIT 1`).
   - `get_all_ground_truth_for_symbol` (lines 834-861): Successfully retrieves all ground truth entries for a stock ticker.

2. **Required Unit Conversions (`providers/pdf_extraction_provider.py`)**:
   - `Lakhs -> 0.01`: Verified via `detect_unit_scale` line 53 and `UNIT_SCALES["lakh"]` line 24.
   - `Millions -> 0.1`: Verified via `detect_unit_scale` line 56 and `UNIT_SCALES["million"]` line 28.
   - `USD -> 8.3`: Verified via `detect_unit_scale` line 59 and `UNIT_SCALES["usd_million"]` line 34.
   - `Crores -> 1.0`: Verified via `detect_unit_scale` line 65 and `UNIT_SCALES["crore"]` line 37.

3. **Confidence Scoring (`providers/pdf_extraction_provider.py` lines 304-307)**:
   - Evaluates `[m for m in (revenue_cr, ebitda_cr, pat_cr) if m is not None]`.
   - Returns `1.0` (3/3 metrics), `0.67` (2/3 metrics), `0.33` (1/3 metrics or margin fallback), and `0.0` (0 metrics).

4. **Discovered Defects during Empirical Payload Testing**:
   - **B3-E01 (Negative Financial Numbers)**: In `providers/pdf_extraction_provider.py` lines 193-230, capturing groups use `([\d,]+\.?\d*)` which rejects leading negative signs (`-`). Testing loss-making payloads (`Operating EBITDA: -150.0`, `PAT: -350.2`) returned `ebitda_cr=None` and `pat_cr=None`.
   - **B3-E02 (Thousands Unit Scale Factor)**: In `providers/pdf_extraction_provider.py` lines 31-33 & line 63, `"thousand"` is assigned `0.00001` (10^-5) instead of `0.0001` (10^-4). Since 1 Crore = 10,000 Thousands, converting 10,000 Thousands produced `0.1 Cr` instead of `1.0 Cr` (a 10x error).
   - **B3-E03 (Operating Profit Typo)**: In `providers/pdf_extraction_provider.py` line 206, EBITDA regex contains `r"(?:operating\s+ebitda|ebitda|operating\0 profit|pbdt)..."`. The substring `operating\0 profit` contains an ASCII NUL byte (`\0`), breaking EBITDA extraction when labeled "Operating Profit".

5. **Pytest Execution**:
   - `python -m pytest tests/test_pdf_ground_truth_extractor.py -o pythonpath=.` -> 20/20 passed in 8.23s.
   - Targeted unit test suite -> 52/52 passed in 30.68s.

---

## 2. Logic Chain

1. **Observation 1 & 2** confirm that `GroundTruthFinancials` storage/retrieval in SQLite and the four explicit scale conversions (`Lakhs=0.01`, `Millions=0.1`, `USD=8.3`, `Crores=1.0`) meet all baseline design criteria.
2. **Observation 3 & 5** confirm that confidence scoring operates as specified and all existing unit tests in `tests/test_pdf_ground_truth_extractor.py` pass cleanly without regression.
3. **Observation 4**, however, proves via empirical execution (`python verify_m3_empirical.py`) that real-world financial edge cases fail:
   - Loss-making corporate reports (negative EBITDA / PAT) cannot be extracted because the regex ignores `-`.
   - Filings in ₹ Thousands are undercounted by a factor of 10 due to `0.00001` scale factor.
   - Reports using "Operating Profit" terminology are skipped due to a NUL byte typo in regex.
4. **Conclusion**: Therefore, while storage, core models, and primary conversions pass verification, the overall verdict is **FAIL** pending patches for the 3 discovered parsing defects.

---

## 3. Caveats

- PDF downloading via URL in `extract_text_from_pdf` was tested using mock HTTP responses since external network access is disabled in the execution environment.
- Exchange rate for USD is statically set to `8.3` (Cr / USD Mn) in `UNIT_SCALES`. Dynamic FX rate lookup is out of scope for Milestone 3.

---

## 4. Conclusion

- **SQLite Storage & Retrieval**: **PASS**
- **Unit Scale Conversions (Lakhs, Millions, USD, Crores)**: **PASS**
- **Confidence Scoring**: **PASS**
- **Pytest Suite (`test_pdf_ground_truth_extractor.py`)**: **PASS**
- **Edge Case Payload Robustness**: **FAIL** (Defects B3-E01, B3-E02, B3-E03)
- **Final Verdict**: **FAIL**

---

## 5. Verification Method

To independently reproduce and verify these findings:

1. **Run Empirical Verification Script**:
   ```powershell
   python verify_m3_empirical.py
   ```
   *Expected output*: Shows PASS for Storage, Lakhs/Millions/USD/Crores scale, and Confidence Scoring; reports FAIL for Thousands scale (0.00001), Negative Numbers (loss extraction), and Operating Profit (NUL byte typo).

2. **Run Pytest Suite**:
   ```powershell
   python -m pytest tests/test_pdf_ground_truth_extractor.py -o pythonpath=.
   ```
   *Expected output*: 20 passed.

3. **Inspect Implementation Files**:
   - `providers/pdf_extraction_provider.py` lines 31-33 (thousand scale), line 206 (`operating\0 profit`), lines 193-230 (`[\d,]+\.?\d*` missing `-`).
   - `storage/sqlite_store.py` lines 208-229 (`ground_truth_financials` schema), lines 744-861 (`save_ground_truth` and `get_ground_truth`).
