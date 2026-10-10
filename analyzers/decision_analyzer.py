"""
Decision-oriented valuation, risk, and thesis helpers.

These rules are intentionally transparent and deterministic. They turn the
existing quote, financial, and quarterly data into a research dashboard view
without introducing another external API dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from models.stock import QuarterlyResult


@dataclass
class RiskFlag:
    severity: str
    category: str
    message: str
    evidence: str


@dataclass
class ValuationSnapshot:
    current_price: float
    eps_ttm: float
    base_multiple: float
    bear_value: float
    base_value: float
    bull_value: float
    margin_of_safety: float
    valuation_state: str
    notes: list[str] = field(default_factory=list)


@dataclass
class ThesisSnapshot:
    stance: str
    score: int
    bull_case: list[str]
    bear_case: list[str]
    watch_items: list[str]


class DecisionAnalyzer:
    """Build valuation, risk, and thesis snapshots from available stock data."""

    def build_research_snapshot(
        self,
        info: dict[str, Any],
        hist_df: pd.DataFrame | None,
        quarters: list[QuarterlyResult],
    ) -> dict[str, Any]:
        valuation = self.build_valuation(info, quarters)
        risks = self.assess_risks(info, hist_df, quarters)
        thesis = self.build_thesis(info, quarters, valuation, risks)
        return {
            "valuation": valuation,
            "risks": risks,
            "thesis": thesis,
        }

    def build_valuation(
        self,
        info: dict[str, Any],
        quarters: list[QuarterlyResult],
    ) -> ValuationSnapshot:
        current_price = self._first_number(
            info.get("currentPrice"),
            info.get("regularMarketPrice"),
            default=0.0,
        )
        eps_ttm = self._estimate_eps_ttm(info, quarters)
        growth = self._yoy_growth([q.eps for q in quarters])
        opm = quarters[-1].opm_percent if quarters else 0.0
        debt_penalty = self._latest_interest_to_revenue(quarters)

        notes = []
        if not eps_ttm or eps_ttm <= 0:
            notes.append("TTM EPS is unavailable or negative; multiple-based fair value is not reliable.")
            return ValuationSnapshot(
                current_price=current_price,
                eps_ttm=eps_ttm,
                base_multiple=0.0,
                bear_value=0.0,
                base_value=0.0,
                bull_value=0.0,
                margin_of_safety=0.0,
                valuation_state="Insufficient Data",
                notes=notes,
            )

        # Transparent, conservative multiple framework:
        # growth and margin expand the multiple, interest burden compresses it.
        base_multiple = 14.0
        if growth is not None:
            base_multiple += max(-5.0, min(10.0, growth * 0.35))
        if opm:
            base_multiple += max(-2.0, min(5.0, (opm - 12.0) * 0.18))
        if debt_penalty:
            base_multiple -= max(0.0, min(5.0, debt_penalty * 0.4))

        trailing_pe = self._first_number(info.get("trailingPE"), default=0.0)
        if trailing_pe:
            base_multiple = (base_multiple * 0.65) + (trailing_pe * 0.35)

        base_multiple = round(max(6.0, min(45.0, base_multiple)), 1)
        bear_multiple = max(5.0, round(base_multiple * 0.7, 1))
        bull_multiple = round(base_multiple * 1.3, 1)

        bear_value = round(eps_ttm * bear_multiple, 2)
        base_value = round(eps_ttm * base_multiple, 2)
        bull_value = round(eps_ttm * bull_multiple, 2)
        margin = ((base_value - current_price) / current_price * 100) if current_price else 0.0

        if margin >= 25:
            state = "Attractive"
        elif margin >= -10:
            state = "Fair"
        else:
            state = "Expensive"

        if growth is None:
            notes.append("Not enough quarterly history for YoY EPS growth; valuation uses margin and market multiple inputs.")
        if trailing_pe:
            notes.append(f"Blended with observed trailing P/E of {trailing_pe:.1f}.")

        return ValuationSnapshot(
            current_price=current_price,
            eps_ttm=round(eps_ttm, 2),
            base_multiple=base_multiple,
            bear_value=bear_value,
            base_value=base_value,
            bull_value=bull_value,
            margin_of_safety=round(margin, 1),
            valuation_state=state,
            notes=notes,
        )

    def assess_risks(
        self,
        info: dict[str, Any],
        hist_df: pd.DataFrame | None,
        quarters: list[QuarterlyResult],
    ) -> list[RiskFlag]:
        risks: list[RiskFlag] = []

        pe = self._first_number(info.get("trailingPE"), default=0.0)
        pb = self._first_number(info.get("priceToBook"), default=0.0)
        beta = self._first_number(info.get("beta"), default=0.0)

        if pe > 60:
            risks.append(RiskFlag("High", "Valuation", "Very high earnings multiple.", f"P/E {pe:.1f}"))
        elif pe > 40:
            risks.append(RiskFlag("Medium", "Valuation", "Elevated earnings multiple.", f"P/E {pe:.1f}"))

        if pb > 12:
            risks.append(RiskFlag("High", "Valuation", "Very high book multiple.", f"P/B {pb:.1f}"))
        elif pb > 8:
            risks.append(RiskFlag("Medium", "Valuation", "Elevated book multiple.", f"P/B {pb:.1f}"))

        if beta > 1.6:
            risks.append(RiskFlag("Medium", "Price Risk", "High market sensitivity.", f"Beta {beta:.2f}"))

        if quarters:
            latest = quarters[-1]
            if latest.operating_profit < 0:
                risks.append(RiskFlag("High", "Profitability", "Latest operating profit is negative.", latest.quarter))
            if latest.eps < 0:
                risks.append(RiskFlag("High", "Earnings", "Latest quarterly EPS is negative.", f"{latest.quarter}: EPS {latest.eps:.2f}"))

            if len(quarters) >= 5:
                rev_growth = self._growth(quarters[-1].revenue, quarters[-5].revenue)
                eps_growth = self._growth(quarters[-1].eps, quarters[-5].eps)
                margin_delta = latest.opm_percent - quarters[-5].opm_percent

                if rev_growth is not None and rev_growth < -10:
                    risks.append(RiskFlag("High", "Growth", "Revenue has declined sharply YoY.", f"{rev_growth:.1f}% YoY"))
                elif rev_growth is not None and rev_growth < 0:
                    risks.append(RiskFlag("Medium", "Growth", "Revenue is down YoY.", f"{rev_growth:.1f}% YoY"))

                if eps_growth is not None and eps_growth < -20:
                    risks.append(RiskFlag("High", "Earnings", "EPS has declined sharply YoY.", f"{eps_growth:.1f}% YoY"))
                elif eps_growth is not None and eps_growth < 0:
                    risks.append(RiskFlag("Medium", "Earnings", "EPS is down YoY.", f"{eps_growth:.1f}% YoY"))

                if margin_delta < -5:
                    risks.append(RiskFlag("High", "Margins", "Operating margin has compressed materially YoY.", f"{margin_delta:.1f} pp"))
                elif margin_delta < -2:
                    risks.append(RiskFlag("Medium", "Margins", "Operating margin is weaker YoY.", f"{margin_delta:.1f} pp"))

            interest_ratio = self._latest_interest_to_revenue(quarters)
            if interest_ratio > 10:
                risks.append(RiskFlag("High", "Debt Service", "Interest burden is high versus revenue.", f"{interest_ratio:.1f}% of revenue"))
            elif interest_ratio > 5:
                risks.append(RiskFlag("Medium", "Debt Service", "Interest burden needs monitoring.", f"{interest_ratio:.1f}% of revenue"))

        drawdown = self._drawdown_from_high(hist_df)
        if drawdown is not None and drawdown < -35:
            risks.append(RiskFlag("Medium", "Price Risk", "Stock is in a large drawdown from its available-period high.", f"{drawdown:.1f}%"))

        if not risks:
            risks.append(RiskFlag("Low", "Quality Check", "No major deterministic red flags detected from available data.", "Review filings manually."))

        severity_order = {"High": 0, "Medium": 1, "Low": 2}
        return sorted(risks, key=lambda item: severity_order.get(item.severity, 3))

    def build_thesis(
        self,
        info: dict[str, Any],
        quarters: list[QuarterlyResult],
        valuation: ValuationSnapshot,
        risks: list[RiskFlag],
    ) -> ThesisSnapshot:
        score = 50
        bull_case: list[str] = []
        bear_case: list[str] = []
        watch_items: list[str] = []

        if valuation.valuation_state == "Attractive":
            score += 15
            bull_case.append("Base fair value is meaningfully above the current price.")
        elif valuation.valuation_state == "Expensive":
            score -= 15
            bear_case.append("Current price is above the base multiple-derived fair value.")

        if quarters:
            latest = quarters[-1]
            if latest.opm_percent >= 18:
                score += 8
                bull_case.append(f"Latest operating margin is healthy at {latest.opm_percent:.1f}%.")
            if latest.eps > 0:
                score += 5
                bull_case.append(f"Latest quarterly EPS is positive at {latest.eps:.2f}.")

            if len(quarters) >= 5:
                rev_growth = self._growth(quarters[-1].revenue, quarters[-5].revenue)
                eps_growth = self._growth(quarters[-1].eps, quarters[-5].eps)
                if rev_growth is not None and rev_growth > 12:
                    score += 10
                    bull_case.append(f"Revenue growth is strong at {rev_growth:.1f}% YoY.")
                elif rev_growth is not None and rev_growth < 0:
                    score -= 8
                    bear_case.append(f"Revenue declined {abs(rev_growth):.1f}% YoY.")

                if eps_growth is not None and eps_growth > 15:
                    score += 10
                    bull_case.append(f"EPS growth is strong at {eps_growth:.1f}% YoY.")
                elif eps_growth is not None and eps_growth < 0:
                    score -= 8
                    bear_case.append(f"EPS declined {abs(eps_growth):.1f}% YoY.")

                watch_items.append("Confirm whether YoY growth and margin direction continue next quarter.")

        high_risks = [r for r in risks if r.severity == "High"]
        medium_risks = [r for r in risks if r.severity == "Medium"]
        score -= len(high_risks) * 12
        score -= len(medium_risks) * 5
        bear_case.extend([f"{r.category}: {r.message}" for r in high_risks[:3]])

        sector = info.get("sector") or "sector"
        industry = info.get("industry") or "industry"
        watch_items.append(f"Compare valuation and margins with peers in {sector} / {industry}.")
        watch_items.append("Read the latest annual report notes and auditor observations before acting.")

        score = max(0, min(100, score))
        if score >= 70:
            stance = "Accumulate Candidate"
        elif score >= 55:
            stance = "Watchlist / Fair"
        elif score >= 40:
            stance = "Cautious"
        else:
            stance = "Avoid / Needs Work"

        return ThesisSnapshot(
            stance=stance,
            score=score,
            bull_case=bull_case[:5] or ["No strong bull-case signal detected from available deterministic data."],
            bear_case=bear_case[:5] or ["No major bear-case signal detected from available deterministic data."],
            watch_items=watch_items[:5],
        )

    @staticmethod
    def _first_number(*values: Any, default: float = 0.0) -> float:
        for value in values:
            try:
                if value is not None and value != "":
                    return float(value)
            except (TypeError, ValueError):
                continue
        return default

    @staticmethod
    def _growth(current: float, previous: float) -> float | None:
        if previous is None or previous == 0:
            return None
        return (current - previous) / abs(previous) * 100

    def _yoy_growth(self, values: list[float]) -> float | None:
        if len(values) >= 5:
            return self._growth(values[-1], values[-5])
        return None

    def _estimate_eps_ttm(self, info: dict[str, Any], quarters: list[QuarterlyResult]) -> float:
        if len(quarters) >= 4:
            eps_values = [q.eps for q in quarters[-4:]]
            if any(v != 0 for v in eps_values):
                return sum(eps_values)
        return self._first_number(info.get("trailingEps"), info.get("epsTrailingTwelveMonths"), default=0.0)

    @staticmethod
    def _latest_interest_to_revenue(quarters: list[QuarterlyResult]) -> float:
        if not quarters:
            return 0.0
        latest = quarters[-1]
        if not latest.revenue:
            return 0.0
        return latest.interest / latest.revenue * 100

    @staticmethod
    def _drawdown_from_high(hist_df: pd.DataFrame | None) -> float | None:
        if hist_df is None or hist_df.empty or "Close" not in hist_df:
            return None
        close = pd.to_numeric(hist_df["Close"], errors="coerce").dropna()
        if close.empty:
            return None
        high = close.max()
        latest = close.iloc[-1]
        if not high:
            return None
        return (latest - high) / high * 100
