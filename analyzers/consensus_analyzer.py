"""
Consensus Expectation Analyzer.
Calculates the Consensus Surprise Delta (Actual vs. Expected Market Consensus):
Surprise Delta = (Actual - Expected) / max(|Expected|, 0.01)
Stocks move on expectation beats/misses rather than absolute growth numbers.
"""
from typing import Dict, Any


class ConsensusAnalyzer:
    """Evaluates earnings surprise deltas against market consensus estimates."""

    def __init__(self):
        pass

    def compute_surprise_delta(self, actual_pat_cr: float, expected_pat_cr: float, actual_rev_cr: float, expected_rev_cr: float) -> Dict[str, Any]:
        """
        Compute earnings beat/miss surprise deltas with zero-division epsilon smoothing.
        """
        pat_denom = max(abs(expected_pat_cr), 0.01)
        rev_denom = max(abs(expected_rev_cr), 0.01)

        pat_surprise_pct = ((actual_pat_cr - expected_pat_cr) / pat_denom) * 100.0
        rev_surprise_pct = ((actual_rev_cr - expected_rev_cr) / rev_denom) * 100.0

        # Weighted surprise score (-100 to +100)
        surprise_score = (pat_surprise_pct * 0.7) + (rev_surprise_pct * 0.3)
        surprise_score = max(-100.0, min(100.0, surprise_score))

        category = "Massive Beat" if surprise_score >= 15.0 else ("Beat" if surprise_score >= 5.0 else ("Inline" if surprise_score >= -5.0 else "Miss"))

        return {
            "pat_surprise_pct": round(pat_surprise_pct, 2),
            "rev_surprise_pct": round(rev_surprise_pct, 2),
            "surprise_score": round(surprise_score, 1),
            "category": category
        }
