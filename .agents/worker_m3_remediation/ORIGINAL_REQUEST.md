## 2026-07-24T15:46:18Z
You are Worker 4 tasked with remediation of Milestone 3 (Ground-Truth PDF Metric Extraction Engine).

Working Directory: d:\GeoNagrik\Dev\git\stock_market\.agents\worker_m3_remediation\
Project Root: d:\GeoNagrik\Dev\git\stock_market\

Challenger Feedback & Required Fixes in `providers/pdf_extraction_provider.py`:
1. Negative Numbers & Loss Figures:
   - Update numeric regex capture groups to handle negative values `-1,200.00` and parenthesis loss figures `(1,200.00)`. Convert `(1200)` to `-1200.0`.
2. Billions / Bn Unit Scale:
   - Add `billion`, `billions`, `bn` to `UNIT_SCALES` with multiplier `100.0` (1 Billion = 100 Crores).
3. Thousands Scale Factor Correction:
   - Fix `Thousands` / `th` multiplier from `0.00001` to `0.0001` (10,000 Thousands = 1 Crore -> 1 Thousand = 0.0001 Crore).
4. Unit Scale Detection Range:
   - Expand `detect_unit_scale()` text search limit from 3,000 characters to full document text (or first 15,000 characters) so slide/page 2-3 unit headers (e.g. `₹ in Lakhs`) are detected.
5. ASCII NUL Byte Typo Fix:
   - Fix regex typo `operating\0 profit` in `pdf_extraction_provider.py` line 207 to `operating profit`.
6. Verbal Phrasing Patterns:
   - Add regex patterns for narrative disclosures such as `"Revenue / EBITDA / Net Profit / PAT stood at / reached / recorded at / came in at X Cr"`.

Verification Requirements:
- Run pytest (`python -m pytest -o pythonpath=.`).
- Add unit tests in `tests/test_pdf_ground_truth_extractor.py` covering negative numbers, Billions scale, Thousands scale correction, full-text unit detection, NUL byte fix, and verbal phrasing.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

When completed, write `changes.md` and `handoff.md` in your working directory and notify parent via send_message.
