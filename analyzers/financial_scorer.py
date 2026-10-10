"""
Financial scorer — computes normalized 0-100 spider chart scores
from raw quarterly financial data.
"""
from models.stock import QuarterlyResult
from models.analysis import SpiderMetric, QuarterSpiderData
from config import SPIDER_DIMENSIONS


class FinancialScorer:
    """
    Converts raw quarterly financials into normalized 0-100 scores
    for each spider chart dimension.
    """

    def compute_spider_data(
        self, quarters: list[QuarterlyResult]
    ) -> list[QuarterSpiderData]:
        """
        Given a list of QuarterlyResult (oldest first),
        compute SpiderMetric scores for each quarter.
        """
        if not quarters:
            return []

        results = []
        for i, q in enumerate(quarters):
            metrics = []

            # 1. Revenue Growth (YoY or QoQ if not enough data)
            rev_score, rev_trend = self._revenue_growth(quarters, i)
            metrics.append(SpiderMetric(
                name="Revenue Growth",
                score=rev_score,
                raw_value=f"₹{q.revenue:,.0f} Cr",
                trend=rev_trend,
            ))

            # 2. Profitability (OPM%)
            prof_score, prof_trend = self._profitability(quarters, i)
            metrics.append(SpiderMetric(
                name="Profitability",
                score=prof_score,
                raw_value=f"{q.opm_percent:.1f}%",
                trend=prof_trend,
            ))

            # 3. EBITDA Trend (Operating Profit direction)
            ebitda_score, ebitda_trend = self._ebitda_trend(quarters, i)
            metrics.append(SpiderMetric(
                name="EBITDA Trend",
                score=ebitda_score,
                raw_value=f"₹{q.operating_profit:,.0f} Cr",
                trend=ebitda_trend,
            ))

            # 4. Debt Management (Interest / Revenue)
            debt_score, debt_trend = self._debt_management(quarters, i)
            int_pct = (q.interest / q.revenue * 100) if q.revenue else 0
            metrics.append(SpiderMetric(
                name="Debt Management",
                score=debt_score,
                raw_value=f"{int_pct:.1f}% of Rev",
                trend=debt_trend,
            ))

            # 5. EPS Growth
            eps_score, eps_trend = self._eps_growth(quarters, i)
            metrics.append(SpiderMetric(
                name="EPS Growth",
                score=eps_score,
                raw_value=f"₹{q.eps:.2f}",
                trend=eps_trend,
            ))

            # 6. Operational Efficiency (Expenses/Revenue ratio improvement)
            eff_score, eff_trend = self._operational_efficiency(quarters, i)
            exp_pct = (q.expenses / q.revenue * 100) if q.revenue else 100
            metrics.append(SpiderMetric(
                name="Operational Efficiency",
                score=eff_score,
                raw_value=f"{100 - exp_pct:.1f}% savings",
                trend=eff_trend,
            ))

            overall = sum(m.score for m in metrics) / len(metrics) if metrics else 0
            results.append(QuarterSpiderData(
                quarter=q.quarter,
                metrics=metrics,
                overall_score=round(overall, 1),
            ))

        return results

    # --- Individual dimension scorers ---

    def _revenue_growth(self, qs: list[QuarterlyResult], i: int) -> tuple[float, str]:
        """Score revenue growth. YoY preferred, QoQ fallback."""
        curr = qs[i].revenue
        if curr == 0:
            return 50.0, "flat"

        # YoY (4 quarters back)
        if i >= 4 and qs[i - 4].revenue > 0:
            pct = (curr - qs[i - 4].revenue) / qs[i - 4].revenue * 100
        elif i >= 1 and qs[i - 1].revenue > 0:
            pct = (curr - qs[i - 1].revenue) / qs[i - 1].revenue * 100
        else:
            return 50.0, "flat"

        # Normalize: -20% → 0, 0% → 50, +30% → 100
        score = self._normalize(pct, -20, 30)
        trend = self._trend(qs, i, lambda q: q.revenue)
        return score, trend

    def _profitability(self, qs: list[QuarterlyResult], i: int) -> tuple[float, str]:
        """Score OPM%. Higher margin = better."""
        opm = qs[i].opm_percent
        # Normalize: -5% → 0, 15% → 50, 35% → 100
        score = self._normalize(opm, -5, 35)
        trend = self._trend(qs, i, lambda q: q.opm_percent)
        return score, trend

    def _ebitda_trend(self, qs: list[QuarterlyResult], i: int) -> tuple[float, str]:
        """Score EBITDA (operating profit) growth."""
        curr = qs[i].operating_profit
        if i >= 1 and qs[i - 1].operating_profit != 0:
            prev = qs[i - 1].operating_profit
            if prev != 0:
                pct = (curr - prev) / abs(prev) * 100
            else:
                pct = 0
        else:
            pct = 0

        score = self._normalize(pct, -30, 30)
        trend = self._trend(qs, i, lambda q: q.operating_profit)
        return score, trend

    def _debt_management(self, qs: list[QuarterlyResult], i: int) -> tuple[float, str]:
        """Score interest/revenue ratio. Lower = better (inverted)."""
        if qs[i].revenue == 0:
            return 50.0, "flat"
        ratio = qs[i].interest / qs[i].revenue * 100
        # Normalize inverted: 15% interest → 0, 5% → 50, 0% → 100
        score = self._normalize(ratio, 15, 0, invert=True)
        trend = self._trend(qs, i, lambda q: q.interest / q.revenue * 100 if q.revenue else 0, invert=True)
        return score, trend

    def _eps_growth(self, qs: list[QuarterlyResult], i: int) -> tuple[float, str]:
        """Score EPS growth YoY or QoQ."""
        curr = qs[i].eps
        if i >= 4 and qs[i - 4].eps != 0:
            pct = (curr - qs[i - 4].eps) / abs(qs[i - 4].eps) * 100
        elif i >= 1 and qs[i - 1].eps != 0:
            pct = (curr - qs[i - 1].eps) / abs(qs[i - 1].eps) * 100
        else:
            return 50.0, "flat"

        score = self._normalize(pct, -50, 50)
        trend = self._trend(qs, i, lambda q: q.eps)
        return score, trend

    def _operational_efficiency(self, qs: list[QuarterlyResult], i: int) -> tuple[float, str]:
        """Score expense/revenue ratio. Lower ratio = better (inverted)."""
        if qs[i].revenue == 0:
            return 50.0, "flat"
        ratio = qs[i].expenses / qs[i].revenue * 100
        # Normalize inverted: 110% → 0, 90% → 50, 70% → 100
        score = self._normalize(ratio, 110, 70, invert=True)
        trend = self._trend(qs, i, lambda q: q.expenses / q.revenue * 100 if q.revenue else 100, invert=True)
        return score, trend

    # --- Helpers ---

    @staticmethod
    def _normalize(value: float, low: float, high: float, invert: bool = False) -> float:
        """Normalize a value to 0-100 range given expected low and high."""
        if invert:
            # For inverted metrics (lower is better): swap interpretation
            score = (low - value) / (low - high) * 100 if low != high else 50
        else:
            score = (value - low) / (high - low) * 100 if high != low else 50
        return round(max(0, min(100, score)), 1)

    @staticmethod
    def _trend(qs: list[QuarterlyResult], i: int,
               extractor, invert: bool = False) -> str:
        """Determine 3-quarter trend direction."""
        if i < 2:
            return "flat"
        try:
            vals = [extractor(qs[j]) for j in range(max(0, i - 2), i + 1)]
            if len(vals) < 3:
                return "flat"
            direction = vals[-1] - vals[0]
            if invert:
                direction = -direction
        except (ZeroDivisionError, TypeError):
            return "flat"

        if direction > 0.5:
            return "up"
        elif direction < -0.5:
            return "down"
        return "flat"
