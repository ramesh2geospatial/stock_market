# Challenge Report — Milestone 3 Remediation Re-Verification

**Reviewer**: Challenger 6 (Empirical Challenger)  
**Target File**: `providers/pdf_extraction_provider.py`  
**Worker**: Worker 4  
**Date**: 2026-07-24  

## Challenge Summary

**Overall risk assessment**: LOW (All 6 remediation fixes independently verified and operational; zero regression across full test suite of 129 pytests).

---

## 6 Target Remediation Verification Details

### 1. Negative numbers `-1200` and parenthesis loss figures `(1,200.00)` -> `-1200.0`
- **Mechanism**: `_clean_number` checks for leading `-`, leading `(`, or trailing `)`. Cleans commas/parentheses/dashes and negates positive float if `is_negative` flag is set.
- **Empirical Findings**:
  - `_clean_number("-1200")` -> `-1200.0`
  - `_clean_number("(1,200.00)")` -> `-1200.0`
  - `_clean_number("(1200)")` -> `-1200.0`
  - `_clean_number("( 450.00 )")` -> `-450.0`
  - `_clean_number("(0.00)")` -> `0.0` (zero checked to avoid `-0.0`)
- **Status**: ✅ **PASS**

### 2. `Billions` / `Bn` unit scale factor (`100.0` Cr)
- **Mechanism**: `UNIT_SCALES` dictionary maps `"billion"`, `"billions"`, `"bn"` to `100.0`. `detect_unit_scale` checks regex `r"(?:in|₹|rs\.?|inr)\s*(?:billions?|bn)\b"`.
- **Empirical Findings**:
  - `detect_unit_scale("Financial Results (in Billions)")` -> `100.0`
  - `detect_unit_scale("Figures in Rs. Bn")` -> `100.0`
  - `normalize_unit(12.5, "billions")` -> `1250.0 Cr`
  - Text extraction with Billions scale correctly converted 12.5 Billion Rev to 1250.0 Cr.
- **Status**: ✅ **PASS**

### 3. Thousands unit scale factor (`0.0001` Cr)
- **Mechanism**: `UNIT_SCALES` dictionary maps `"thousand"`, `"thousands"`, `"th"` to `0.0001`. `detect_unit_scale` checks regex `r"(?:in|₹|rs\.?|inr)\s*(?:thousands?|th)\b"`.
- **Empirical Findings**:
  - `detect_unit_scale("Figures in Rs. Thousands")` -> `0.0001`
  - `detect_unit_scale("INR in Th")` -> `0.0001`
  - `normalize_unit(10000.0, "thousand")` -> `1.0 Cr`
  - Text extraction with Thousands scale correctly converted 50,00,000 Thousands Rev to 500.0 Cr.
- **Status**: ✅ **PASS**

### 4. 15,000-character unit scale detection window
- **Mechanism**: `detect_unit_scale` takes `text_sample = text[:15000].lower()`.
- **Empirical Findings**:
  - Text header at 5,000 chars -> scale detected (`0.01`).
  - Text header at 12,000 chars -> scale detected (`100.0`).
  - Text header at 14,500 chars -> scale detected (`0.0001`).
  - Text header past 16,000 chars -> gracefully ignored, falls back to default `1.0`.
- **Status**: ✅ **PASS**

### 5. NUL byte typo fix (`operating profit`)
- **Mechanism**: Checked binary bytes of `providers/pdf_extraction_provider.py` for NUL bytes (`\x00`). Verified regex patterns for EBITDA include `operating profit`.
- **Empirical Findings**:
  - 0 NUL bytes found in source code file.
  - `Operating Profit: 250.0 Cr` -> `ebitda_cr = 250.0`.
  - `Operating Profit reached 520.5 Crores` -> `ebitda_cr = 520.5`.
- **Status**: ✅ **PASS**

### 6. Verbal narrative phrasing patterns (`stood at / reached / recorded at / came in at`)
- **Mechanism**: Regex patterns for Revenue, EBITDA, PAT, and Capex include narrative verbs (`stood at`, `reached`, `recorded at`, `came in at`, `was`, `were`, `reported at`).
- **Empirical Findings**:
  - `Revenue from operations stood at Rs 3,400 Cr` -> `revenue_cr = 3400.0`
  - `Total revenue reached 4,200 Crores` -> `revenue_cr = 4200.0`
  - `Operating Profit reached 520.5 Crores` -> `ebitda_cr = 520.5`
  - `EBITDA recorded at 400 Cr` -> `ebitda_cr = 400.0`
  - `PAT came in at (180) Cr` -> `pat_cr = -180.0`
  - `Capex spent stood at 150 Cr` -> `capex_cr = 150.0`
- **Status**: ✅ **PASS**

---

## Stress Test Results Matrix

| Scenario | Input | Expected Output | Actual Output | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Negative / Parentheses** | `"(1,200.00)"` | `-1200.0` | `-1200.0` | **PASS** |
| **Negative Loss Narrative**| `"PAT came in at (180) Cr"` | `pat_cr = -180.0` | `pat_cr = -180.0` | **PASS** |
| **Billions Scale Detect** | `"Figures in Rs. Bn"` | `100.0` | `100.0` | **PASS** |
| **Billions Normalization**  | `12.5` (in Billions) | `1250.0 Cr` | `1250.0 Cr` | **PASS** |
| **Thousands Scale Detect** | `"Figures in Rs. Thousands"` | `0.0001` | `0.0001` | **PASS** |
| **Thousands Normalization**| `50,00,000` (in Thousands)| `500.0 Cr` | `500.0 Cr` | **PASS** |
| **15k Char Window (14.5k)** | Unit at char pos 14,500 | `0.0001` | `0.0001` | **PASS** |
| **15k Char Window (>15k)** | Unit at char pos 16,000 | `1.0` (fallback) | `1.0` | **PASS** |
| **NUL Byte Check** | File binary check | 0 `\x00` bytes | 0 `\x00` bytes | **PASS** |
| **Operating Profit Parsing**| `"Operating Profit: 250.0 Cr"` | `ebitda_cr = 250.0` | `ebitda_cr = 250.0` | **PASS** |
| **Narrative Phrasing Rev**  | `"Net sales recorded at 1,500 Cr"` | `revenue_cr = 1500.0` | `revenue_cr = 1500.0` | **PASS** |
| **Narrative Phrasing Capex**| `"Capex incurred recorded at 80 Cr"`| `capex_cr = 80.0` | `capex_cr = 80.0` | **PASS** |
| **Pytest Full Suite** | `python -m pytest -o pythonpath=.` | 129 Passed | 129 Passed (36.57s) | **PASS** |

---

## Unchallenged / Outside Scope Areas
- OCR extraction quality from scanned non-searchable image-based PDFs (pypdf text extraction layer limit).

---

## Final Verdict
**PASS** — All 6 remediation targets verified empirically. Code base is solid and all test suites pass.
