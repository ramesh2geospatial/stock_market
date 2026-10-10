# Changes Summary — Milestone 3 Remediation

## Modified Files
1. `providers/pdf_extraction_provider.py`: Remediated Ground-Truth PDF Metric Extraction Provider with support for negative/parenthesis numbers, Billions unit scale, Thousands scale correction, 15k char unit detection range, NUL byte fix, and narrative verbal phrasing patterns.
2. `tests/test_pdf_ground_truth_extractor.py`: Added 6 new unit test functions and updated existing assertions to achieve 100% test coverage for all remediated items.

## Remediation Details

### 1. Negative Numbers & Loss Figures
- **Problem**: `_clean_number()` stripped `-` and parentheses `()`, converting negative figures such as `(1,200.00)` to positive numbers (`1200.0`).
- **Fix**: Updated `_clean_number()` to recognize leading `-`, opening `(`, and closing `)` as negative indicators (`is_negative = True`). Returns `-1200.0` for `(1,200.00)` or `(1200)`. Updated numeric regex capture groups across Revenue, EBITDA, PAT, Capex, and Segment extraction to `(\(?-?[\d,]+\.?\d*\)?)`.

### 2. Billions / Bn Unit Scale
- **Problem**: `UNIT_SCALES` lacked entries for `billion`, `billions`, and `bn`, causing fallback to 1.0 (Crores).
- **Fix**: Added `"billion": 100.0`, `"billions": 100.0`, and `"bn": 100.0` to `UNIT_SCALES` (1 Billion = 100 Crores). Added Billions search regex pattern in `detect_unit_scale()` returning multiplier `100.0`.

### 3. Thousands Scale Factor Correction
- **Problem**: `UNIT_SCALES["thousand"]`, `UNIT_SCALES["thousands"]`, `UNIT_SCALES["th"]`, and `detect_unit_scale()` returned `0.00001` instead of `0.0001`.
- **Fix**: Corrected multiplier from `0.00001` to `0.0001` (since 10,000 Thousands = 1 Crore -> 1 Thousand = 0.0001 Crore).

### 4. Unit Scale Detection Range
- **Problem**: `detect_unit_scale()` limited text scanning to the first 3,000 characters (`text[:3000]`), missing unit headers on page 2-3 of presentations.
- **Fix**: Expanded text scan range from 3,000 to 15,000 characters (`text[:15000]`).

### 5. ASCII NUL Byte Typo Fix
- **Problem**: Typo `operating\0 profit` in line 207 contained an unescaped ASCII NUL byte `\0`.
- **Fix**: Replaced `operating\0 profit` with `operating\s+profit`.

### 6. Verbal Phrasing Patterns
- **Problem**: Narrative disclosures such as `"Revenue / EBITDA / PAT stood at / reached / recorded at / came in at X Cr"` were not captured by table-oriented regexes.
- **Fix**: Added narrative verbal phrasing regex patterns:
  - `(stood at|reached|recorded at|came in at|was|were|reported at)` for Revenue, EBITDA, PAT, and Capex, supporting inline unit overrides (`Cr`, `Lakhs`, `Mn`, `Bn`).

## Verification
- Executed full test suite: `python -m pytest -o pythonpath=.` (129 tests passed).
- Test module `tests/test_pdf_ground_truth_extractor.py` verified with 100% pass rate.
