"""
Multi-Quarter Financial Divergence Analyzer.
Computes QoQ and YoY financial divergence matrices, margin expansion/compression,
and revenue acceleration/deceleration over dynamic N quarters.
"""
from typing import List, Dict, Any
from models.stock import QuarterlyResult


class MultiQuarterDivergenceAnalyzer:
    """Calculates multi-quarter divergence metrics and growth trajectory badges."""

    def compute_divergence(
        self,
        quarterly_results: List[QuarterlyResult],
        num_quarters: int = 5
    ) -> Dict[str, Any]:
        """
        Compute QoQ and YoY divergence matrix for the last N quarters.
        Default num_quarters = 5.
        """
        if not quarterly_results or len(quarterly_results) < 2:
            return {
                "num_quarters": 0,
                "matrix": [],
                "trajectory_badge": "🟡 Insufficient Data",
                "summary": "At least 2 quarters required for divergence calculation."
            }

        # Select latest N quarters
        start_idx = max(0, len(quarterly_results) - num_quarters)
        selected = quarterly_results[start_idx:]

        matrix = []
        margin_deltas = []
        revenue_growths = []
        turnaround_flag = False

        for i in range(len(selected)):
            curr = selected[i]
            full_idx = start_idx + i
            prev = quarterly_results[full_idx - 1] if full_idx > 0 else None

            curr_rev = getattr(curr, "revenue", 0.0) or 0.0
            curr_margin = getattr(curr, "opm_percent", 0.0) or 0.0
            curr_pat = getattr(curr, "net_profit", 0.0) or 0.0

            if prev:
                prev_rev = getattr(prev, "revenue", 0.0) or 0.0
                prev_margin = getattr(prev, "opm_percent", 0.0) or 0.0
                prev_pat = getattr(prev, "net_profit", 0.0) or 0.0

                if prev_pat < 0 and curr_pat > 0:
                    turnaround_flag = True

                raw_rev_pct = ((curr_rev - prev_rev) / prev_rev * 100.0) if prev_rev > 0 else 0.0
                raw_pat_pct = ((curr_pat - prev_pat) / abs(prev_pat) * 100.0) if prev_pat != 0 else 0.0
                qoq_rev_pct = min(500.0, max(-500.0, raw_rev_pct))
                qoq_pat_pct = min(500.0, max(-500.0, raw_pat_pct))
                margin_bps_delta = (curr_margin - prev_margin) * 100.0  # Percentage points to bps
            else:
                qoq_rev_pct = 0.0
                qoq_pat_pct = 0.0
                margin_bps_delta = 0.0

            margin_deltas.append(margin_bps_delta)
            revenue_growths.append(qoq_rev_pct)

            matrix.append({
                "quarter": curr.quarter,
                "revenue": round(curr_rev, 2),
                "qoq_revenue_growth_pct": round(qoq_rev_pct, 2),
                "ebitda_margin_pct": round(curr_margin, 2),
                "ebitda_margin_delta_bps": round(margin_bps_delta, 1),
                "net_profit": round(curr_pat, 2),
                "qoq_pat_growth_pct": round(qoq_pat_pct, 2),
                "eps": round(curr.eps or 0.0, 2)
            })

        # Determine Trajectory Badge based on last 3 quarters
        recent_rev = revenue_growths[-3:] if revenue_growths else [0.0]
        recent_margin = margin_deltas[-3:] if margin_deltas else [0.0]
        avg_rev_growth = sum(recent_rev) / len(recent_rev)
        avg_margin_delta = sum(recent_margin) / len(recent_margin)

        if avg_rev_growth > 5.0 and avg_margin_delta >= 0:
            badge = "🚀 Accelerating Growth & Margin Expansion"
        elif avg_rev_growth < -3.0 or avg_margin_delta < -100:
            badge = "⚠️ Decelerating Growth / Margin Pressure"
        else:
            badge = "⚖️ Stable Performance Trajectory"

        latest_pat = getattr(selected[-1], "net_profit", 0.0) or 0.0
        if turnaround_flag and latest_pat > 0:
            badge = f"{badge} | 🔄 Loss-to-Profit Turnaround"

        summary = (
            f"Analyzed {len(selected)} quarters. "
            f"Avg 3-quarter QoQ Revenue Growth: {avg_rev_growth:.1f}%, "
            f"Avg Margin Change: {avg_margin_delta:.0f} bps."
        )

        return {
            "num_quarters": len(selected),
            "matrix": matrix,
            "trajectory_badge": badge,
            "turnaround_flag": turnaround_flag,
            "avg_rev_growth_pct": round(avg_rev_growth, 2),
            "avg_margin_delta_bps": round(avg_margin_delta, 1),
            "summary": summary
        }
