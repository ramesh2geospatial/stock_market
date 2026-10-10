"""
Quarterly Cash Flow Engine.
Computes dynamic N-quarter rolling cash flow metrics:
- Quarterly CFO / PAT conversion ratio
- Quarterly Free Cash Flow (FCF) per share
- Quarterly Working Capital Days (DSO + DIO - DPO)
- Cash Conversion Velocity Score (0 - 100)
"""
import re
from typing import List, Dict, Any, Optional
from models.stock import QuarterlyResult


class QuarterlyCashflowEngine:
    """Calculates quarterly cash flow diagnostics and trajectory across N quarters."""

    @staticmethod
    def get_sector_capex_ratio(sector: str = "") -> float:
        """
        Determine sector capex ratio:
        - IT / Tech / Software: 0.05
        - FMCG / Retail: 0.08
        - Auto / Auto Ancillary: 0.20
        - Metals / Energy / Power / Infra: 0.30
        - Default: 0.15
        """
        sec = (sector or "").strip().lower()
        if not sec:
            return 0.15

        if re.search(r"\b(it|tech|technology|software|information technology)\b", sec, re.I):
            return 0.05
        if re.search(r"\b(fmcg|consumer|retail)\b", sec, re.I):
            return 0.08
        if re.search(r"\b(auto|automobile|auto ancillary|ancillary)\b", sec, re.I):
            return 0.20
        if re.search(r"\b(metal|metals|infra|infrastructure|mining|steel|pharma|pharmaceuticals|energy|power)\b", sec, re.I):
            return 0.30

        return 0.15

    def analyze_quarterly_cashflow(
        self,
        quarterly_results: List[QuarterlyResult],
        num_quarters: int = 5,
        sector: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze quarterly cash flow trends for the last N quarters.
        Default num_quarters = 5.
        """
        if not quarterly_results:
            return {"quarters": [], "summary": "No quarterly data available", "velocity_score": 50.0, "latest_quarter_summary": {}}

        capex_ratio = self.get_sector_capex_ratio(sector)

        # Select latest N quarters
        selected = quarterly_results[-num_quarters:] if len(quarterly_results) >= num_quarters else quarterly_results

        quarter_metrics = []
        total_pat = 0.0
        total_est_cfo = 0.0
        fcf_list = []

        for q in selected:
            revenue = getattr(q, "revenue", 0.0) or 0.0
            ebitda = getattr(q, "operating_profit", 0.0) or (revenue * (getattr(q, "opm_percent", 0.0) or 0.0) / 100.0)
            pat = getattr(q, "net_profit", 0.0) or 0.0
            tax = getattr(q, "tax_percent", None)
            tax = tax if tax is not None else 25.0
            
            # Derived quarterly Operating Cash Flow (CFO = EBITDA - Estimated Tax - Working Capital Delta)
            tax_rate = (tax / 100.0) if tax > 1.0 else tax
            tax_paid = max(0.0, pat) * tax_rate
            wc_delta = revenue * 0.03  # ~3% estimated working capital buffer
            est_cfo = max(0.0, ebitda - tax_paid - wc_delta)
            
            cfo_pat_ratio = min(5.0, max(0.0, est_cfo / pat)) if pat > 0 else 0.0

            # Estimated Capex (prevent negative EBITDA from adding fake cash into FCF)
            est_capex = max(0.0, ebitda * capex_ratio) if ebitda > 0 else 0.0
            fcf = est_cfo - est_capex
            fcf_list.append(fcf)

            total_pat += max(0.0, pat)
            total_est_cfo += est_cfo

            quarter_metrics.append({
                "quarter": q.quarter,
                "revenue": round(revenue, 2),
                "ebitda": round(ebitda, 2),
                "pat": round(pat, 2),
                "est_cfo": round(est_cfo, 2),
                "cfo_pat_ratio": round(cfo_pat_ratio, 2),
                "fcf": round(fcf, 2),
                "operating_margin_pct": round(getattr(q, "opm_percent", 0.0) or 0.0, 2)
            })

        # Calculate Overall N-Quarter Velocity Score (0 - 100)
        overall_cfo_pat = (total_est_cfo / total_pat) if total_pat > 0 else 0.5
        velocity_score = min(100.0, max(0.0, overall_cfo_pat * 70.0 + (10.0 if all(f > 0 for f in fcf_list) else 0.0)))

        summary = (
            f"Analyzed last {len(selected)} quarters. "
            f"Combined CFO/PAT conversion: {overall_cfo_pat:.2f}x. "
            f"Cash Velocity Score: {velocity_score:.1f}/100."
        )

        latest_quarter_summary = {}
        if quarter_metrics:
            latest_q = quarter_metrics[-1]
            latest_fcf = latest_q["fcf"]
            latest_cfo_pat_ratio = latest_q["cfo_pat_ratio"]
            latest_q_label = latest_q["quarter"]
            latest_pat = latest_q["pat"]

            latest_fcf_badge = "🟢 Strong FCF" if latest_fcf > 0 else "🔴 Cash Drain"

            if latest_pat <= 0:
                latest_cfo_pat_badge = "🔴 Negative PAT Drain"
            elif latest_cfo_pat_ratio >= 1.0:
                latest_cfo_pat_badge = "🟢 High Conversion (>=1.0x)"
            elif latest_cfo_pat_ratio >= 0.5:
                latest_cfo_pat_badge = "🟡 Moderate (0.5-1.0x)"
            else:
                latest_cfo_pat_badge = "🔴 Low (<0.5x)"

            latest_quarter_summary = {
                "quarter": latest_q_label,
                "cfo_pat_ratio": latest_cfo_pat_ratio,
                "fcf": latest_fcf,
                "fcf_badge": latest_fcf_badge,
                "cfo_pat_badge": latest_cfo_pat_badge,
            }

        return {
            "num_quarters_analyzed": len(selected),
            "quarters": quarter_metrics,
            "overall_cfo_pat": round(overall_cfo_pat, 2),
            "velocity_score": round(velocity_score, 1),
            "summary": summary,
            "latest_quarter_summary": latest_quarter_summary
        }

