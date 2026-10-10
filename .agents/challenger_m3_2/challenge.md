# Adversarial Challenge Report — Milestone 3 (Ground-Truth PDF Metric Extraction Engine)

**Target Component**: Ground-Truth Financial Metrics Engine (`models/ground_truth.py`, `providers/pdf_extraction_provider.py`, `storage/sqlite_store.py`)  
**Evaluator**: Challenger 2 (Empirical Challenger)  
**Date**: 2026-07-24  
**Overall Risk Assessment**: **HIGH** (3 actionable defect findings discovered via empirical execution)

---

## Challenge Summary

Milestone 3 implements the `GroundTruthFinancials` data model, SQLite `ground_truth_financials` persistence table, and `PDFGroundTruthExtractor` unit scaling and extraction routines.

Empirical verification confirmed that:
1. **SQLite Storage & Retrieval** (`ground_truth_financials`): Works correctly. Stores Pydantic models and dictionaries, serializes JSON fields, enforces unique constraints on `(symbol, quarter, doc_type)`, and prioritizes `financial_results` over `presentation` when `doc_type` is omitted.
2. **Specified Core Unit Conversions**: `Lakhs -> 0.01`, `Millions -> 0.1`, `USD -> 8.3`, and `Crores -> 1.0` match required scale factors.
3. **Extraction Confidence Scoring**: Correctly scores `1.0` (3/3 metrics), `0.67` (2/3 metrics), `0.33` (1/3 metrics or margin fallback), and `0.0` (0 metrics).

However, empirical stress testing identified **3 distinct defects** in regex parsing and unit scaling that cause extraction failures or numerical corruption on non-standard payloads.

---

## Actionable Defect Findings

### [HIGH] Challenge 1 (B3-E01): Negative Financial Figure Extraction Failure (Loss-Making Companies)
- **Assumption Challenged**: The extraction engine assumes reported financial metrics are always positive numbers.
- **Attack Scenario**: Test extraction against financial result PDFs for loss-making companies reporting negative EBITDA (e.g. `-150.0 Cr`) or negative PAT (e.g. `-350.2 Cr`).
- **Empirical Result**: `ebitda_cr` and `pat_cr` returned `None`.
- **Root Cause**: In `providers/pdf_extraction_provider.py` (lines 193-230), regex capturing groups use `([\d,]+\.?\d*)` which excludes the negative sign `-`.
- **Blast Radius**: Severe. Loss-making companies (startups, turnaround plays, distress situations) lose all EBITDA and PAT ground-truth tracking in the platform.
- **Suggested Defense**: Update capture groups to allow optional negative signs and brackets: `([\+\-]?[\d,]+\.?\d*)` or `\(?([\d,]+\.?\d*)\)?`.

### [MEDIUM] Challenge 2 (B3-E02): Thousands Scale Factor Off-by-One Zero Bug
- **Assumption Challenged**: Thousands unit scale accurately converts values to INR Crores.
- **Attack Scenario**: Test `UNIT_SCALES["thousand"]` and `detect_unit_scale` against text containing figures in Thousands.
- **Empirical Result**: `10000 Thousands` (which equals ₹1 Crore) returned `0.1 Cr` (off by 10x).
- **Root Cause**: In `providers/pdf_extraction_provider.py` (lines 31-33 & line 63), `"thousand"` is mapped to `0.00001` (10^-5) instead of `0.0001` (10^-4). Since 1 Crore = 10,000 Thousands, $1 / 10,000 = 0.0001$.
- **Blast Radius**: Medium. Small-cap company filings or micro-cap announcements reported in ₹ Thousands suffer a 90% numerical truncation error.
- **Suggested Defense**: Change `"thousand": 0.00001` to `"thousand": 0.0001` in `UNIT_SCALES` and `detect_unit_scale`.

### [MEDIUM] Challenge 3 (B3-E03): NUL Byte ASCII Typo in Operating Profit Regex
- **Assumption Challenged**: The regex engine recognizes "Operating Profit" as a synonym for EBITDA.
- **Attack Scenario**: Test extraction against text reporting "Operating Profit: 15,000 Cr".
- **Empirical Result**: `ebitda_cr` returned `None`.
- **Root Cause**: In `providers/pdf_extraction_provider.py` line 206, the pattern reads `r"(?:operating\s+ebitda|ebitda|operating\0 profit|pbdt)..."`. The substring `operating\0 profit` contains a literal NUL byte `\0` instead of `\s+`.
- **Blast Radius**: Medium. Financial reports using the phrase "Operating Profit" fail EBITDA extraction.
- **Suggested Defense**: Replace `operating\0 profit` with `operating\s+profit`.

---

## Stress Test Execution Matrix

| Test Scenario | Input / Payload | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :--- | :--- |
| **SQLite Storage & Retrieval** | `GroundTruthFinancials` object & dict | Saved to SQLite `ground_truth_financials` & retrieved cleanly | Saved & retrieved cleanly | **PASS** |
| **Doc-Type Fallback Priority** | Fetch without `doc_type` when both exist | Return `financial_results` record over `presentation` | Returned `financial_results` | **PASS** |
| **Lakhs Scale Conversion** | `Revenue in Lakhs: 50,00,000` | `50000.0 Cr` (multiplier `0.01`) | `50000.0 Cr` | **PASS** |
| **Millions Scale Conversion** | `Statement in Millions: 500` | `50.0 Cr` (multiplier `0.1`) | `50.0 Cr` | **PASS** |
| **USD Scale Conversion** | `Amounts in USD Millions: $2,650` | `21995.0 Cr` (multiplier `8.3`) | `21995.0 Cr` | **PASS** |
| **Crores Scale Conversion** | `Revenue from Operations: 40,500.5 Cr`| `40500.5 Cr` (multiplier `1.0`) | `40500.5 Cr` | **PASS** |
| **Confidence Scoring** | 3/3 core metrics present | `1.0` confidence | `1.0` confidence | **PASS** |
| **Confidence Scoring Fallback**| 0/3 core metrics, but margin present | `0.33` confidence | `0.33` confidence | **PASS** |
| **Negative Financial Numbers** | `Operating EBITDA: -150.0`, `PAT: -350.2` | `ebitda_cr=-150.0`, `pat_cr=-350.2` | `ebitda_cr=None`, `pat_cr=None` | **FAIL (B3-E01)** |
| **Thousands Scale Conversion** | `Figures in Thousands: 10,000` | `1.0 Cr` (multiplier `0.0001`) | `0.1 Cr` (multiplier `0.00001`) | **FAIL (B3-E02)** |
| **Operating Profit Parsing** | `Operating Profit: 15,000` | `ebitda_cr=15000.0` | `ebitda_cr=None` | **FAIL (B3-E03)** |

---

## Unchallenged Areas

None — All aspects of storage, schema integrity, scale multipliers, confidence calculations, regex patterns, and Pytest coverage were empirically tested and evaluated.
