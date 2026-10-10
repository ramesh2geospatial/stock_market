# Adversarial Challenge Report — Milestone 3: Ground-Truth PDF Metric Extraction Engine

## Challenge Summary

**Overall risk assessment**: **HIGH**

Empirical stress testing of `PDFGroundTruthExtractor` (`providers/pdf_extraction_provider.py`) revealed **5 critical failure modes** when processing real-world quarterly financial announcements and investor presentations. While the extractor passes basic happy-path unit tests, it fails on standard financial reporting conventions (such as net losses in parentheses, `Billions` unit scales, unit headers beyond page 1, and natural phrasing like "stood at" or "reached").

---

## Challenges

### [High] Challenge 1: Loss / Negative Financial Figures Formatted in Parentheses `(1,200.00)`
- **Assumption challenged**: Financial metrics (PAT, EBITDA) are always positive numbers without parentheses formatting.
- **Attack scenario**: Financial statements present net losses or negative EBITDA in parentheses e.g. `PAT: (1,200.00)` or `Profit After Tax: (450.50)`.
- **Blast radius**: The regex patterns `r"([\d,]+\.?\d*)"` fail to match numbers starting with `(`, causing `pat_cr` or `ebitda_cr` to return `None` or lose the negative sign. If `_clean_number` receives `"(1,200.00)"`, it strips non-digits and returns `+1200.00`, turning a ₹1,200 Cr net loss into a ₹1,200 Cr net profit!
- **Mitigation**: Update regexes to support optional parentheses `r"(?:\(|\-|minus\s*)?([\d,]+\.?\d*)\)?"` and update `_clean_number` to recognize parentheses as negative floats.

### [High] Challenge 2: Lack of Support for `Billions` / `Bn` Unit Scale
- **Assumption challenged**: Indian corporate presentations only use Lakhs, Millions, Thousands, USD Millions, or Crores.
- **Attack scenario**: Multi-national Indian conglomerates or global tech/auto firms report in Billions (e.g. `(₹ in Billions)` or `Amounts in Rs. Bn`).
- **Blast radius**: `detect_unit_scale` does not contain rules for `billion`/`billions`/`bn`. It falls back to default `1.0` (Crores). Since 1 Billion = 100 Crores, revenue of 50.0 Billions is extracted as 50.0 Crores instead of 5,000.0 Crores — a **100x error in financial magnitude**!
- **Mitigation**: Add `"billion": 100.0`, `"billions": 100.0`, `"bn": 100.0` to `UNIT_SCALES` and regex patterns in `detect_unit_scale`.

### [High] Challenge 3: 3,000-Character Truncation in Unit Scale Detection (`text[:3000]`)
- **Assumption challenged**: The reported unit scale statement (e.g. `(₹ in Lakhs)`) always appears within the first 3,000 characters of the PDF.
- **Attack scenario**: Investor presentations or BSE result filings often contain cover pages, table of contents, corporate announcements, or disclaimers exceeding 3,000 characters before the financial table.
- **Blast radius**: `detect_unit_scale` uses `text_sample = text[:3000].lower()`. If the unit header `(₹ in Lakhs)` appears at character 3,500, `detect_unit_scale` returns fallback `1.0` (Crores). A ₹50,00,000 Lakhs revenue figure is extracted as 50,00,000 Crores — a **100x inflation of financial figures**!
- **Mitigation**: Expand unit detection search window across the entire document or search each table page dynamically.

### [Medium] Challenge 4: Extraction Regex Fails on Natural Language Phrasing ("stood at", "reached", "was")
- **Assumption challenged**: Financial metrics are separated from numbers by simple delimiters like `:`, `-`, or `|`.
- **Attack scenario**: Investor presentation text contains commentary like `"Deferred Revenue stood at 200.0 Cr"`, `"Total Revenue from Operations reached 5,000.0 Cr"`, or `"In Q1 FY26 PAT was 250 Cr"`.
- **Blast radius**: Regex patterns require `[:\-\|]?`, causing lines with verbal linkers ("stood at", "reached", "was") to fail extraction (`None`).
- **Mitigation**: Enhance regex patterns to match optional verbal linkers like `(?:was|reached|stood\s+at|came\s+in\s+at|of)?\s*[:\-\|]?`.

### [Medium] Challenge 5: Conflict Priority in Unit Scale Detection Regexes
- **Assumption challenged**: Document unit declarations can be reliably determined by fixed regex matching order.
- **Attack scenario**: Document states `Financial Results (₹ in Crores)`, but includes a footnote `"Prior period audit fee was Rs 50 Lakhs"`.
- **Blast radius**: `detect_unit_scale` evaluates `Lakhs` before `Crores`. If `Lakhs` appears anywhere in `text[:3000]`, it overrides `Crores`, misinterpreting the entire Crores table as Lakhs.
- **Mitigation**: Search for formal table header patterns e.g. `r"\b(?:in|figures\s+in|rs\.?\s*in)\s+(crores?|lakhs?|millions?|billions?)\b"` with explicit section weightings.

---

## Stress Test Results

| Test Scenario | Input Description | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Negative Numbers in Parentheses** | `PAT: (1,200.00)` | `pat_cr = -1200.0` | `pat_cr = None` (failed to match) | **FAIL** |
| **Billions Unit Scale** | `FINANCIAL RESULTS (₹ in Billions)` | `scale = 100.0` | `scale = 1.0` (fallback) | **FAIL** |
| **Unit Scale Past 3,000 Chars** | `(₹ in Lakhs)` at char 3,600 | `scale = 0.01` | `scale = 1.0` (fallback) | **FAIL** |
| **Natural Language Phrasing** | `Total Revenue reached 5,000.0 Cr` | `revenue_cr = 5000.0` | `revenue_cr = None` | **FAIL** |
| **Prior vs Current Quarter Text** | Commentary with Q1 FY25 vs Q1 FY26 | `revenue_cr = 1500.0` | `revenue_cr = None` | **FAIL** |
| **Scanned / Textless PDF** | Empty page text | `confidence = 0.0` | `confidence = 0.0` | **PASS** |
| **Corrupted PDF Stream** | Non-PDF binary stream | Returns `""`, no crash | Returns `""`, no crash | **PASS** |
| **Malformed Segment Line** | `Segment reporting note Ind AS 108` | Exclude accounting notes | Exclude accounting notes | **PASS** |
| **Crores Unit Scale** | `Financial Results (₹ in Crores)` | `scale = 1.0` | `scale = 1.0` | **PASS** |
| **Standard Lakhs Extraction** | `(₹ in Lakhs)` with colon separator | `revenue_cr = 50000.0` | `revenue_cr = 50000.0` | **PASS** |

---

## Unchallenged Areas

- **OCR for Scanned Image PDFs**: Tesseract / OCR capability is not implemented in `PDFGroundTruthExtractor` (returns 0 text for scanned PDFs). Out of scope for current PyPDF implementation.
