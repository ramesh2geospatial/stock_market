# Milestone 4: Cross-Validation & Hallucination Defense Engine — Technical Design & Analysis Report

**Author**: Explorer Subagent (Milestone 4)  
**Working Directory**: `d:\GeoNagrik\Dev\git\stock_market\.agents\explorer_m4\`  
**Project Root**: `d:\GeoNagrik\Dev\git\stock_market\`  
**Date**: 2026-07-24  

---

## 1. Executive Summary

Milestone 4 establishes the **Cross-Validation & Hallucination Defense Engine** for the Indian Stock Market Research Platform. Concall transcripts processed by Large Language Models (Gemini 2.5 Flash) contain critical management narrative and quantitative guidance. However, LLMs can hallucinate or misextract financial numbers (e.g. confusing quarterly vs annual numbers, standalone vs consolidated figures, or Lakhs vs Crores). 

This milestone introduces an automated, multi-source defense layer that validates AI-extracted concall financials against ground-truth metrics derived from **official BSE/NSE filings/PDFs** (`GroundTruthFinancials`) and **Screener.in quarterly tables** (`QuarterlyResult`).

### Key Features Designed:
1. **Tiered Metric Divergence Calculation**: Relative numeric divergence ($\frac{|C - G|}{G}$) for absolute figures (Revenue, EBITDA, PAT, Capex) and percentage point divergence ($|C - G|$) for EBITDA margin %.
2. **Automated Baseline Auto-Correction**: Replaces AI values with official ground-truth numbers whenever divergence exceeds **15%** (or **3.0 pp** for margins).
3. **AI Hallucination Alerts**: Detects and logs severe discrepancies ($>50\%$ relative divergence or $>10.0\text{ pp}$ margin diff).
4. **3-Tier Confidence Badge System**:
   - 🟢 **High Confidence (`"high"`)**: Max relative divergence $\le 5\%$ AND margin divergence $\le 1.0\text{ pp}$.
   - 🟡 **Medium Confidence (`"medium"`)**: $5\% < \text{Max relative divergence} \le 15\%$ OR $1.0\text{ pp} < \text{Margin divergence} \le 3.0\text{ pp}$.
   - 🔴 **Low Confidence (`"low"`)**: Max relative divergence $> 15\%$ OR margin divergence $> 3.0\text{ pp}$ (auto-correction triggered), or hallucination alert.
5. **SQLite Persistence Schema & Storage Methods**: A dedicated `cross_validation_results` table and API methods in `SQLiteStore`.

---

## 2. Current Architecture & Gap Analysis

### 2.1 File & Module Inventory

| File Path | Component | Current Role |
| :--- | :--- | :--- |
| `analyzers/cross_validator.py` | `CrossValidator` | Basic validation comparing 3 fields (`revenue_absolute`, `pat_absolute`, `ebitda_margin_pct`) against Screener `QuarterlyResult`. |
| `models/analysis.py` | `SentimentResult` | Structured Pydantic output from concall analysis, containing `revenue_absolute`, `ebitda_absolute`, `pat_absolute`, `capex_actual_cr`, `ebitda_margin_pct`, `data_confidence`, `corrections`. |
| `models/ground_truth.py` | `GroundTruthFinancials` | Ground-truth metrics extracted from official PDFs: `revenue_cr`, `ebitda_cr`, `pat_cr`, `ebitda_margin_pct`, `capex_cr`. |
| `models/stock.py` | `QuarterlyResult` | Screener.in quarterly table row: `revenue`, `operating_profit`, `opm_percent`, `net_profit`. |
| `providers/pdf_extraction_provider.py` | `PDFGroundTruthExtractor` | Extracts official PDF text & tables, normalizes units (Lakhs/Millions -> INR Cr). |
| `storage/sqlite_store.py` | `SQLiteStore` | Stores `concall_analysis` and `ground_truth_financials` tables. Currently lacks dedicated `cross_validation_results` table methods. |
| `tests/test_cross_validator.py` | Unit Tests | Basic tests for revenue divergence and margin difference against Screener. |

---

### 2.2 Identified Gaps & Deficiencies in Current Implementation

1. **Input Interface Limitation**:
   - `CrossValidator.validate_and_correct` currently only accepts `list[QuarterlyResult]` (Screener.in format). It cannot directly ingest `GroundTruthFinancials` (the primary PDF ground-truth source from BSE/NSE filings).
2. **Missing Field Validations**:
   - Current validator checks `revenue_absolute`, `pat_absolute`, and `ebitda_margin_pct`.
   - Missing: `ebitda_absolute` (vs `ebitda_cr` / `operating_profit`) and `capex_actual_cr` (vs `capex_cr`).
3. **Flawed Confidence Badge Mapping**:
   - In current `cross_validator.py` (lines 86–92):
     ```python
     if not corrections:
         corrected.data_confidence = "high"
     ```
   - **Bug/Deficiency**: If a revenue divergence is **12%**, it does NOT exceed the 15% auto-correction threshold, so `corrections` remains empty. Current logic sets `data_confidence = "high"`!
   - **Correct Milestone 4 Rule**: 12% divergence must be mapped to 🟡 **Medium Confidence** (5% < divergence $\le$ 15%), NOT High Confidence.
4. **Lack of Detailed Divergence Audit Metrics**:
   - `SentimentResult` only tracks fields that triggered auto-corrections. It does not record measured divergences for matching fields (e.g. 3% divergence that passed). downstream UI cannot display exact divergence % without this data.
5. **SQLite Persistence Gap**:
   - `SQLiteStore` has tables for `concall_analysis` and `ground_truth_financials`, but no standalone `cross_validation_results` table or `save_cross_validation_result` / `get_cross_validation_result` methods to track historical validation audits.

---

## 3. Milestone 4 Engine Specification

### 3.1 Divergence Formulas & Metrics Matrix

Let $C$ be the Gemini Concall Extracted Value, and $G$ be the Official Ground-Truth Baseline Value.

#### 1. Relative Numeric Divergence (Absolute Figures)
Applies to: `revenue` (Rs Cr), `ebitda` (Rs Cr), `net_profit` / `pat` (Rs Cr), `capex` (Rs Cr).
$$D_{\text{rel}} = \frac{|C - G|}{|G|} \times 100\%$$

*Special Edge Case Rules*:
- **Zero Ground Truth ($G = 0$)**: If $G = 0$ and $C \ne 0$, $D_{\text{rel}} = 100.0\%$. If $C = 0$, $D_{\text{rel}} = 0.0\%$.
- **Negative Financials (Losses)**: For Net Profit or EBITDA where $G < 0$ or $C < 0$, relative divergence uses absolute magnitude denominator $|G|$.
- **Missing Metrics**: If either $C$ or $G$ is `None`, skip divergence calculation for that field.

#### 2. Margin Percentage Point Divergence
Applies to: `ebitda_margin_pct` (%).
$$D_{\text{margin}} = |C - G| \text{ percentage points (pp)}$$

---

### 3.2 Automated Auto-Correction Engine Rules

| Metric Category | Field Name | Auto-Correction Threshold | Action on Breach |
| :--- | :--- | :--- | :--- |
| **Revenue** | `revenue_absolute` | $D_{\text{rel}} > 15.0\%$ | Replace $C$ with $G$; record correction |
| **EBITDA** | `ebitda_absolute` | $D_{\text{rel}} > 15.0\%$ | Replace $C$ with $G$; record correction |
| **Net Profit (PAT)**| `pat_absolute` | $D_{\text{rel}} > 15.0\%$ | Replace $C$ with $G$; record correction |
| **Capex** | `capex_actual_cr` | $D_{\text{rel}} > 15.0\%$ | Replace $C$ with $G$; record correction |
| **EBITDA Margin** | `ebitda_margin_pct` | $D_{\text{margin}} > 3.0\text{ pp}$ | Replace $C$ with $G$; record correction |

---

### 3.3 AI Hallucination Defense & Alerting Rules

A severe divergence indicates potential LLM hallucination or unit mismatch (e.g. mistaking Lakhs for Crores):
- **Hallucination Alert Threshold**: $D_{\text{rel}} > 50.0\%$ OR $D_{\text{margin}} > 10.0\text{ pp}$.
- **Action**:
  1. Flag correction severity as `"hallucination"`.
  2. Log console/logger alert: `[Hallucination Alert] {symbol} {quarter} {field}: Concall={C}, GroundTruth={G}, Divergence={D}%`.
  3. Force Data Confidence Badge to 🔴 **Low Confidence (`"low"`)**.

---

### 3.4 3-Tier Confidence Badge System Matrix

Let $D_{\text{rel\_max}} = \max(\{D_{\text{rel\_revenue}}, D_{\text{rel\_ebitda}}, D_{\text{rel\_pat}}, D_{\text{rel\_capex}}\})$  
Let $D_{\text{margin\_max}} = D_{\text{margin\_ebitda}}$

```
+-----------------------------------------------------------------------------+
|                            CONFIDENCE BADGE TIERS                           |
+-------------------+-----------------------------+---------------------------+
| Badge Level       | Relative Divergence (D_rel) | Margin Diff (D_margin)    |
+-------------------+-----------------------------+---------------------------+
| 🟢 High           | D_rel_max <= 5.0%           | D_margin_max <= 1.0 pp    |
| 🟡 Medium         | 5.0% < D_rel_max <= 15.0%   | 1.0 pp < D_margin <= 3.0pp|
| 🔴 Low            | D_rel_max > 15.0%           | D_margin_max > 3.0 pp     |
|                   | (Auto-Correction Applied)   | (Auto-Correction Applied) |
+-------------------+-----------------------------+---------------------------+
```

*Note*: If any single metric triggers auto-correction or hallucination alert, overall confidence IMMEDIATELY falls to 🔴 **Low**.

---

### 3.5 Unified Adapter for Ground-Truth Data Sources

To support both PDF Ground-Truth (`GroundTruthFinancials`) and Screener.in (`QuarterlyResult` or dict):

```python
class GroundTruthAdapter:
    """Adapts various ground-truth data models into a unified interface."""
    
    def __init__(self, data: GroundTruthFinancials | QuarterlyResult | dict):
        if isinstance(data, GroundTruthFinancials):
            self.revenue = data.revenue_cr
            self.ebitda = data.ebitda_cr
            self.pat = data.pat_cr
            self.margin = data.ebitda_margin_pct
            self.capex = data.capex_cr
            self.quarter = data.quarter
        elif isinstance(data, QuarterlyResult):
            self.revenue = data.revenue
            self.ebitda = data.operating_profit
            self.pat = data.net_profit
            self.margin = data.opm_percent
            self.capex = None
            self.quarter = data.quarter
        elif isinstance(data, dict):
            self.revenue = data.get("revenue") or data.get("revenue_cr")
            self.ebitda = data.get("ebitda") or data.get("ebitda_cr") or data.get("operating_profit")
            self.pat = data.get("pat") or data.get("pat_cr") or data.get("net_profit")
            self.margin = data.get("ebitda_margin_pct") or data.get("opm_percent")
            self.capex = data.get("capex") or data.get("capex_cr")
            self.quarter = data.get("quarter", "")
```

---

## 4. SQLite Persistence Architecture

### 4.1 Proposed Database Schema

To enable complete auditability of cross-validation results across quarters, we introduce a new SQLite table in `storage/sqlite_store.py`:

```sql
CREATE TABLE IF NOT EXISTS cross_validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    quarter TEXT NOT NULL,
    confidence_badge TEXT NOT NULL,          -- 'high', 'medium', 'low'
    max_relative_divergence REAL DEFAULT 0.0,
    max_margin_divergence_pp REAL DEFAULT 0.0,
    divergences_json TEXT,                   -- JSON object with all field divergences
    corrections_json TEXT,                   -- JSON array of applied corrections
    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, quarter)
);
```

### 4.2 Required `SQLiteStore` Methods

```python
def save_cross_validation_result(
    self, symbol: str, quarter: str, confidence_badge: str,
    max_rel_div: float, max_margin_div: float,
    divergences: dict, corrections: list
) -> bool:
    """Insert or replace cross-validation audit record."""
    conn = self._conn()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO cross_validation_results (
                symbol, quarter, confidence_badge, max_relative_divergence,
                max_margin_divergence_pp, divergences_json, corrections_json, validated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            symbol, quarter, confidence_badge, max_rel_div, max_margin_div,
            json.dumps(divergences, ensure_ascii=False),
            json.dumps(corrections, ensure_ascii=False)
        ))
        conn.commit()
        return True
    finally:
        conn.close()

def get_cross_validation_result(self, symbol: str, quarter: str) -> Optional[dict]:
    """Fetch saved cross-validation audit record for ticker and quarter."""
    conn = self._conn()
    try:
        row = conn.execute("""
            SELECT confidence_badge, max_relative_divergence, max_margin_divergence_pp,
                   divergences_json, corrections_json, validated_at
            FROM cross_validation_results WHERE symbol = ? AND quarter = ?
        """, (symbol, quarter)).fetchone()
        if row:
            return {
                "confidence_badge": row[0],
                "max_relative_divergence": row[1],
                "max_margin_divergence_pp": row[2],
                "divergences": json.loads(row[3]) if row[3] else {},
                "corrections": json.loads(row[4]) if row[4] else [],
                "validated_at": row[5]
            }
        return None
    finally:
        conn.close()
```

---

## 5. Implementation Plan & Proposed Code Modifications

### 5.1 Upgrade `analyzers/cross_validator.py`

#### Proposed Implementation Code Sketch:

```python
"""
Cross-Validation & Hallucination Defense Engine for Concall AI Extractions.
Validates Gemini extracted financials against official Ground-Truth PDF data or Screener.in tables.
"""
from __future__ import annotations

from typing import Optional, Union, Any
from models.analysis import SentimentResult
from models.ground_truth import GroundTruthFinancials
from models.stock import QuarterlyResult

# Divergence Threshold Constants
CORRECTION_THRESHOLD_REL = 0.15     # 15% relative divergence triggers auto-correction
CORRECTION_THRESHOLD_MARGIN = 3.0   # 3.0 percentage points triggers margin auto-correction
HALLUCINATION_THRESHOLD_REL = 0.50  # 50% relative divergence triggers hallucination alert
HALLUCINATION_THRESHOLD_MARGIN = 10.0 # 10.0 pp triggers margin hallucination alert

CONFIDENCE_HIGH_REL = 0.05          # <= 5% for High confidence
CONFIDENCE_HIGH_MARGIN = 1.0       # <= 1.0 pp for High confidence


class GroundTruthAdapter:
    """Unified wrapper around GroundTruthFinancials, QuarterlyResult, or dict."""
    def __init__(self, data: GroundTruthFinancials | QuarterlyResult | dict):
        if isinstance(data, GroundTruthFinancials):
            self.revenue = data.revenue_cr
            self.ebitda = data.ebitda_cr
            self.pat = data.pat_cr
            self.margin = data.ebitda_margin_pct
            self.capex = data.capex_cr
            self.quarter = data.quarter
        elif isinstance(data, QuarterlyResult):
            self.revenue = data.revenue
            self.ebitda = data.operating_profit
            self.pat = data.net_profit
            self.margin = data.opm_percent
            self.capex = None
            self.quarter = data.quarter
        elif isinstance(data, dict):
            self.revenue = data.get("revenue_cr") if "revenue_cr" in data else data.get("revenue")
            self.ebitda = data.get("ebitda_cr") if "ebitda_cr" in data else data.get("ebitda", data.get("operating_profit"))
            self.pat = data.get("pat_cr") if "pat_cr" in data else data.get("pat", data.get("net_profit"))
            self.margin = data.get("ebitda_margin_pct") if "ebitda_margin_pct" in data else data.get("opm_percent")
            self.capex = data.get("capex_cr") if "capex_cr" in data else data.get("capex")
            self.quarter = data.get("quarter", "")
        else:
            raise ValueError(f"Unsupported ground-truth data type: {type(data)}")


class CrossValidator:
    """Validates and auto-corrects Gemini financial numbers against Ground-Truth data."""

    def validate_and_correct(
        self,
        analysis: SentimentResult,
        ground_truth: Union[GroundTruthFinancials, list[QuarterlyResult], dict],
    ) -> SentimentResult:
        """
        Validate concall analysis against ground-truth baseline.
        Returns a corrected copy of SentimentResult with data_confidence and corrections list.
        """
        if not ground_truth:
            return analysis

        # Handle list of QuarterlyResults
        target_gt: Optional[GroundTruthAdapter] = None
        if isinstance(ground_truth, list):
            matched = self._match_quarter(analysis.quarter, ground_truth)
            if not matched:
                return analysis
            target_gt = GroundTruthAdapter(matched)
        else:
            target_gt = GroundTruthAdapter(ground_truth)

        corrected = analysis.model_copy(deep=True)
        corrections = []
        divergences = {}

        # 1. Revenue
        if corrected.revenue_absolute is not None and target_gt.revenue is not None:
            div, corr = self._evaluate_metric(
                field="revenue_absolute",
                concall_val=corrected.revenue_absolute,
                gt_val=target_gt.revenue,
                is_margin=False
            )
            divergences["revenue_absolute"] = div
            if corr:
                corrections.append(corr)
                corrected.revenue_absolute = target_gt.revenue

        # 2. EBITDA
        if corrected.ebitda_absolute is not None and target_gt.ebitda is not None:
            div, corr = self._evaluate_metric(
                field="ebitda_absolute",
                concall_val=corrected.ebitda_absolute,
                gt_val=target_gt.ebitda,
                is_margin=False
            )
            divergences["ebitda_absolute"] = div
            if corr:
                corrections.append(corr)
                corrected.ebitda_absolute = target_gt.ebitda

        # 3. PAT (Net Profit)
        if corrected.pat_absolute is not None and target_gt.pat is not None:
            div, corr = self._evaluate_metric(
                field="pat_absolute",
                concall_val=corrected.pat_absolute,
                gt_val=target_gt.pat,
                is_margin=False
            )
            divergences["pat_absolute"] = div
            if corr:
                corrections.append(corr)
                corrected.pat_absolute = target_gt.pat

        # 4. Capex
        if corrected.capex_actual_cr is not None and target_gt.capex is not None:
            div, corr = self._evaluate_metric(
                field="capex_actual_cr",
                concall_val=corrected.capex_actual_cr,
                gt_val=target_gt.capex,
                is_margin=False
            )
            divergences["capex_actual_cr"] = div
            if corr:
                corrections.append(corr)
                corrected.capex_actual_cr = target_gt.capex

        # 5. EBITDA Margin %
        if corrected.ebitda_margin_pct is not None and target_gt.margin is not None:
            div, corr = self._evaluate_metric(
                field="ebitda_margin_pct",
                concall_val=corrected.ebitda_margin_pct,
                gt_val=target_gt.margin,
                is_margin=True
            )
            divergences["ebitda_margin_pct"] = div
            if corr:
                corrections.append(corr)
                corrected.ebitda_margin_pct = target_gt.margin

        # 3-Tier Confidence Badge Calculation
        corrected.corrections = corrections
        corrected.data_confidence = self._compute_confidence_badge(divergences, corrections)
        return corrected

    @staticmethod
    def _evaluate_metric(
        field: str, concall_val: float, gt_val: float, is_margin: bool = False
    ) -> tuple[float, Optional[dict]]:
        """Calculates divergence and returns (divergence_value, correction_dict_if_any)."""
        if is_margin:
            diff_pp = round(abs(concall_val - gt_val), 2)
            if diff_pp <= CORRECTION_THRESHOLD_MARGIN:
                return diff_pp, None
            
            severity = "hallucination" if diff_pp > HALLUCINATION_THRESHOLD_MARGIN else "correction"
            if severity == "hallucination":
                print(f"[CrossValidator] HALLUCINATION ALERT for {field}: Concall={concall_val}%, GroundTruth={gt_val}%, Diff={diff_pp}pp")

            return diff_pp, {
                "field": field,
                "gemini_value": concall_val,
                "screener_value": gt_val,
                "divergence_pct": diff_pp,
                "severity": severity,
                "is_margin": True
            }
        else:
            if gt_val == 0:
                div_pct = 100.0 if concall_val != 0 else 0.0
            else:
                div_pct = round((abs(concall_val - gt_val) / abs(gt_val)) * 100, 2)

            if div_pct <= CORRECTION_THRESHOLD_REL * 100:
                return div_pct, None

            severity = "hallucination" if div_pct > HALLUCINATION_THRESHOLD_REL * 100 else "correction"
            if severity == "hallucination":
                print(f"[CrossValidator] HALLUCINATION ALERT for {field}: Concall={concall_val}, GroundTruth={gt_val}, Divergence={div_pct}%")

            return div_pct, {
                "field": field,
                "gemini_value": concall_val,
                "screener_value": gt_val,
                "divergence_pct": div_pct,
                "severity": severity,
                "is_margin": False
            }

    @staticmethod
    def _compute_confidence_badge(divergences: dict[str, float], corrections: list[dict]) -> str:
        """
        Computes 3-tier confidence badge:
        - "high": max rel div <= 5% AND max margin diff <= 1.0 pp, no corrections
        - "medium": 5% < max rel div <= 15% OR 1.0 pp < max margin diff <= 3.0 pp, no corrections
        - "low": any correction applied (rel div > 15% or margin diff > 3.0 pp) or hallucination
        """
        if any(c.get("severity") == "hallucination" for c in corrections):
            return "low"
        if len(corrections) > 0:
            return "low"

        # Check uncorrected divergences
        rel_divs = [v for k, v in divergences.items() if k != "ebitda_margin_pct"]
        margin_divs = [v for k, v in divergences.items() if k == "ebitda_margin_pct"]

        max_rel = max(rel_divs) if rel_divs else 0.0
        max_margin = max(margin_divs) if margin_divs else 0.0

        if max_rel <= CONFIDENCE_HIGH_REL * 100 and max_margin <= CONFIDENCE_HIGH_MARGIN:
            return "high"
        elif max_rel <= CORRECTION_THRESHOLD_REL * 100 and max_margin <= CORRECTION_THRESHOLD_MARGIN:
            return "medium"
        else:
            return "low"
```

---

### 5.2 Unit Test Specifications for `tests/test_cross_validator.py`

The test suite in `tests/test_cross_validator.py` must be upgraded to cover all Milestone 4 requirements:

```python
class TestCrossValidatorMilestone4:
    def test_ground_truth_financials_pydantic_model(self, validator):
        """Validate directly against GroundTruthFinancials object from PDF provider."""
        gt = GroundTruthFinancials(
            symbol="TATASTEEL", quarter="Q1 FY25", doc_type="presentation",
            revenue_cr=2500.0, ebitda_cr=500.0, pat_cr=300.0, ebitda_margin_pct=20.0, capex_cr=150.0
        )
        analysis = SentimentResult(
            quarter="Q1 FY25", revenue_absolute=2500.0, ebitda_absolute=500.0,
            pat_absolute=300.0, ebitda_margin_pct=20.0, capex_actual_cr=150.0
        )
        result = validator.validate_and_correct(analysis, gt)
        assert result.data_confidence == "high"
        assert len(result.corrections) == 0

    def test_high_confidence_badge_tier(self, validator):
        """Divergence <= 5% and margin <= 1.0 pp gives High Confidence badge."""
        gt = GroundTruthFinancials(
            symbol="INFY", quarter="Q1 FY25", revenue_cr=1000.0, ebitda_margin_pct=20.0
        )
        analysis = SentimentResult(
            quarter="Q1 FY25", revenue_absolute=1040.0, ebitda_margin_pct=20.8 # 4% rel div, 0.8 pp margin diff
        )
        result = validator.validate_and_correct(analysis, gt)
        assert result.data_confidence == "high"
        assert len(result.corrections) == 0

    def test_medium_confidence_badge_tier(self, validator):
        """Divergence between 5% and 15% (or margin 1.0 to 3.0 pp) gives Medium Confidence badge."""
        gt = GroundTruthFinancials(
            symbol="INFY", quarter="Q1 FY25", revenue_cr=1000.0, ebitda_margin_pct=20.0
        )
        analysis = SentimentResult(
            quarter="Q1 FY25", revenue_absolute=1100.0, ebitda_margin_pct=22.2 # 10% rel div, 2.2 pp margin diff
        )
        result = validator.validate_and_correct(analysis, gt)
        assert result.data_confidence == "medium"
        assert len(result.corrections) == 0
        assert result.revenue_absolute == 1100.0 # Uncorrected (within 15% threshold)

    def test_low_confidence_and_auto_correction(self, validator):
        """Divergence > 15% triggers auto-correction and sets Low Confidence badge."""
        gt = GroundTruthFinancials(
            symbol="RELIANCE", quarter="Q1 FY25", revenue_cr=2000.0
        )
        analysis = SentimentResult(
            quarter="Q1 FY25", revenue_absolute=2400.0 # 20% rel div (>15%)
        )
        result = validator.validate_and_correct(analysis, gt)
        assert result.data_confidence == "low"
        assert len(result.corrections) == 1
        assert result.revenue_absolute == 2000.0 # Auto-corrected to Ground-Truth

    def test_hallucination_alert_logging(self, validator, capsys):
        """Divergence > 50% triggers hallucination alert and low confidence."""
        gt = GroundTruthFinancials(
            symbol="TCS", quarter="Q1 FY25", revenue_cr=1000.0
        )
        analysis = SentimentResult(
            quarter="Q1 FY25", revenue_absolute=1800.0 # 80% rel div
        )
        result = validator.validate_and_correct(analysis, gt)
        captured = capsys.readouterr()
        assert "HALLUCINATION ALERT" in captured.out
        assert result.data_confidence == "low"
        assert result.corrections[0]["severity"] == "hallucination"
```

---

## 6. Actionable Implementation Roadmap

1. **Step 1: Upgrade `analyzers/cross_validator.py`**:
   - Implement `GroundTruthAdapter` to support `GroundTruthFinancials`, `QuarterlyResult`, and `dict`.
   - Add EBITDA and Capex validation logic.
   - Implement strict 3-tier confidence badge mapping (🟢 High $\le 5\% / \le 1.0\text{ pp}$, 🟡 Medium $5\%-15\% / 1.0-3.0\text{ pp}$, 🔴 Low $>15\% / >3.0\text{ pp}$ or corrected).
   - Log hallucination warnings for $>50\%$ relative divergence or $>10.0\text{ pp}$ margin diff.

2. **Step 2: Update `storage/sqlite_store.py`**:
   - Add table `cross_validation_results` in `_init_db()`.
   - Add `save_cross_validation_result(...)` and `get_cross_validation_result(...)` methods.

3. **Step 3: Update Unit Tests in `tests/test_cross_validator.py`**:
   - Add tests for `GroundTruthFinancials` model validation.
   - Add tests for High/Medium/Low 3-tier confidence badges.
   - Add tests for hallucination detection and auto-correction.

4. **Step 4: Verification Execution**:
   - Run `pytest tests/test_cross_validator.py` and `pytest tests/test_sqlite_store.py` to ensure 100% pass rate.
