"""
Cross-Validation Engine: validates Gemini-extracted financial numbers
against Screener.in quarterly results data.

Silently corrects numbers that diverge >15% and flags data confidence.
"""
from __future__ import annotations

import copy
from datetime import datetime
from typing import Optional

from models.analysis import SentimentResult
from models.stock import QuarterlyResult


# Divergence thresholds
_CORRECTION_THRESHOLD = 0.15    # 15% — silently correct
_HALLUCINATION_THRESHOLD = 0.50  # 50% — log hallucination warning


class CrossValidator:
    """Validates and corrects Gemini's financial numbers against Screener data."""

    def validate_and_correct(
        self,
        analysis: SentimentResult,
        quarterly_results: list[QuarterlyResult],
    ) -> SentimentResult:
        """
        Compare Gemini's extracted financials with Screener quarterly data.
        Returns a corrected copy of the analysis with confidence flags.

        - Matches the analysis quarter to the closest quarterly result by label
        - Compares revenue_absolute, pat_absolute, ebitda_margin_pct
        - Corrects divergent numbers and sets data_confidence
        """
        if not quarterly_results:
            return analysis

        matched = self._match_quarter(analysis.quarter, quarterly_results)
        if not matched:
            return analysis

        # Work on a copy so we don't mutate the original
        corrected = analysis.model_copy(deep=True)
        corrections = []

        # --- Revenue comparison ---
        if corrected.revenue_absolute is not None and matched.revenue:
            corr = self._check_and_correct(
                field="revenue_absolute",
                gemini_value=corrected.revenue_absolute,
                screener_value=matched.revenue,
            )
            if corr:
                corrections.append(corr)
                corrected.revenue_absolute = matched.revenue

        # --- PAT (Net Profit) comparison ---
        if corrected.pat_absolute is not None and matched.net_profit:
            # Net profit can be negative, use absolute comparison
            corr = self._check_and_correct(
                field="pat_absolute",
                gemini_value=corrected.pat_absolute,
                screener_value=matched.net_profit,
            )
            if corr:
                corrections.append(corr)
                corrected.pat_absolute = matched.net_profit

        # --- EBITDA Margin (OPM%) comparison ---
        if corrected.ebitda_margin_pct is not None and matched.opm_percent:
            corr = self._check_and_correct(
                field="ebitda_margin_pct",
                gemini_value=corrected.ebitda_margin_pct,
                screener_value=matched.opm_percent,
                is_percentage=True,
            )
            if corr:
                corrections.append(corr)
                corrected.ebitda_margin_pct = matched.opm_percent

        # Set confidence
        corrected.corrections = corrections
        if not corrections:
            corrected.data_confidence = "high"
        elif any(c.get("severity") == "hallucination" for c in corrections):
            corrected.data_confidence = "low"
        else:
            corrected.data_confidence = "medium"

        return corrected

    @staticmethod
    def _check_and_correct(
        field: str,
        gemini_value: float,
        screener_value: float,
        is_percentage: bool = False,
    ) -> Optional[dict]:
        """
        Check divergence between Gemini and Screener values.
        Returns a correction dict if divergence exceeds threshold, else None.

        For percentages (margin %), use absolute difference instead of relative.
        """
        if is_percentage:
            # For margin percentages: absolute basis point difference
            abs_diff = abs(gemini_value - screener_value)
            # Treat >3 percentage points as significant divergence
            if abs_diff <= 3.0:
                return None
            divergence_pct = abs_diff  # report as absolute pp difference
            severity = "hallucination" if abs_diff > 10.0 else "correction"
        else:
            # For absolute numbers: relative divergence
            if screener_value == 0:
                return None
            divergence_pct = abs(gemini_value - screener_value) / abs(screener_value)
            if divergence_pct <= _CORRECTION_THRESHOLD:
                return None
            severity = "hallucination" if divergence_pct > _HALLUCINATION_THRESHOLD else "correction"
            divergence_pct = round(divergence_pct * 100, 1)

        label = "Hallucination detected" if severity == "hallucination" else "Corrected"
        print(
            f"[CrossValidator] {label} for {field}: "
            f"Gemini={gemini_value}, Screener={screener_value}, "
            f"divergence={divergence_pct}{'pp' if is_percentage else '%'}"
        )

        return {
            "field": field,
            "gemini_value": gemini_value,
            "screener_value": screener_value,
            "divergence_pct": divergence_pct,
            "severity": severity,
        }

    @staticmethod
    def _match_quarter(
        quarter_label: str,
        quarterly_results: list[QuarterlyResult],
    ) -> Optional[QuarterlyResult]:
        """
        Match a normalized quarter label (e.g., 'Q1 FY25') to the closest
        QuarterlyResult by parsing the quarter field.

        QuarterlyResult.quarter is typically in 'Mon YYYY' format (e.g., 'Jun 2024')
        from the Screener Chart API, or column headers from HTML scraping.
        """
        if not quarterly_results:
            return None

        # Parse the analysis quarter label -> target month/year
        target_date = _parse_quarter_label_to_date(quarter_label)
        if not target_date:
            # Fallback: try fuzzy match on string
            for qr in quarterly_results:
                if quarter_label.lower() in qr.quarter.lower():
                    return qr
            return None

        # Find the closest quarterly result by date proximity
        best_match = None
        best_distance = float("inf")
        for qr in quarterly_results:
            qr_date = _parse_quarter_date(qr.quarter)
            if not qr_date:
                continue
            distance = abs((target_date - qr_date).days)
            if distance < best_distance:
                best_distance = distance
                best_match = qr

        # Only match if within ~120 days (one quarter tolerance)
        if best_match and best_distance <= 120:
            return best_match
        return None


def _parse_quarter_label_to_date(label: str) -> Optional[datetime]:
    """Parse 'Q1 FY25' -> approximate date (middle of quarter).
    Q1 FY25 = Apr-Jun 2024 -> May 2024
    Q2 FY25 = Jul-Sep 2024 -> Aug 2024
    Q3 FY25 = Oct-Dec 2024 -> Nov 2024
    Q4 FY25 = Jan-Mar 2025 -> Feb 2025
    """
    import re
    m = re.match(r"Q(\d)\s*FY\s*(\d{2,4})", label, re.IGNORECASE)
    if not m:
        return None
    q = int(m.group(1))
    fy = int(m.group(2))
    if fy < 100:
        fy += 2000

    # Map quarter to mid-month
    quarter_mid_months = {1: (5, fy - 1), 2: (8, fy - 1), 3: (11, fy - 1), 4: (2, fy)}
    month, year = quarter_mid_months.get(q, (5, fy - 1))
    try:
        return datetime(year, month, 15)
    except ValueError:
        return None


def _parse_quarter_date(date_str: str) -> Optional[datetime]:
    """Parse 'Jun 2024' or 'Mar 2025' into a datetime."""
    for fmt in ("%b %Y", "%B %Y", "%m/%Y", "%Y-%m"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None
