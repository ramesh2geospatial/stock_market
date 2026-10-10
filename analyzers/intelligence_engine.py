"""
Cross-Quarter Intelligence Engine.
Takes all per-quarter SentimentResults from 10 quarters and produces
a connected narrative via a second Gemini synthesis call.

This is the centerpiece — connecting management promises, analyst concerns,
segment performance, and risk evolution across quarters.
"""
import json
import re
import time
from typing import Optional

from models.analysis import SentimentResult
from models.intelligence import (
    CrossQuarterIntelligence,
    PromiseTracker,
    AnalystConcernEvolution,
    SegmentTrend,
    RiskTrajectory,
    InflectionPoint,
)
from config import GEMINI_MODEL


class IntelligenceEngine:
    """
    Synthesizes per-quarter analysis results into a connected
    10-quarter intelligence briefing.
    """

    def __init__(self, gemini_client=None, rate_limiter=None):
        self.client = gemini_client
        self._rate_limiter = rate_limiter  # Issue #20: callable for rate limiting

    def synthesize(
        self,
        analyses: list[SentimentResult],
        symbol: str = "",
    ) -> CrossQuarterIntelligence:
        """
        Main entry point. Takes sorted list of SentimentResults and produces
        CrossQuarterIntelligence via Gemini synthesis.
        """
        if not analyses:
            return CrossQuarterIntelligence(symbol=symbol)

        # Build the synthesis prompt
        prompt = self._build_synthesis_prompt(analyses, symbol)

        # Call Gemini
        if self.client:
            try:
                # Issue #20: Call rate limiter right before API call
                if self._rate_limiter:
                    self._rate_limiter()
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                )
                result = self._parse_synthesis_response(response.text, analyses, symbol)
                if result:
                    return result
            except Exception as e:
                print(f"[IntelligenceEngine] Gemini synthesis error: {e}")

        # Fallback: rule-based synthesis
        return self._rule_based_synthesis(analyses, symbol)

    def _build_synthesis_prompt(
        self,
        analyses: list[SentimentResult],
        symbol: str,
    ) -> str:
        """Build the comprehensive synthesis prompt from all quarter data."""

        # 1. Financial Progression
        financial_lines = []
        for a in analyses:
            parts = [f"**{a.quarter}**"]
            if a.transcript_date:
                parts.append(f"(Date: {a.transcript_date})")
            parts.append(f"| Tone: {a.management_tone or 'N/A'}")
            parts.append(f"| Sentiment: {a.sentiment_score:+.2f}")
            if a.revenue_absolute is not None or a.revenue_growth_pct is not None:
                rev_str = "| Revenue: "
                if a.revenue_absolute is not None:
                    rev_str += f"Rs {a.revenue_absolute:,.0f} Cr "
                if a.revenue_growth_pct is not None:
                    rev_str += f"({a.revenue_growth_pct:+.1f}% YoY)"
                parts.append(rev_str.strip())
            if a.ebitda_margin_pct is not None:
                parts.append(f"| EBITDA Margin: {a.ebitda_margin_pct:.1f}%")
            if a.ebitda_absolute is not None:  # Issue #24
                parts.append(f"(Rs {a.ebitda_absolute:,.0f} Cr)")
            if a.pat_absolute is not None:  # Issue #24
                parts.append(f"| PAT: Rs {a.pat_absolute:,.0f} Cr")
            if a.pat_growth_pct is not None:
                parts.append(f"({a.pat_growth_pct:+.1f}% YoY)")
            if a.net_debt_cr is not None:
                parts.append(f"| Net Debt: Rs {a.net_debt_cr:,.0f} Cr")
            if a.capex_actual_cr is not None:
                parts.append(f"| Capex: Rs {a.capex_actual_cr:,.0f} Cr")
            financial_lines.append(" ".join(parts))

        # 2. Guidance History
        guidance_lines = []
        for a in analyses:
            if a.guidance_numbers:
                g_items = [f"{k.replace('_', ' ').title()}: {v}" for k, v in a.guidance_numbers.items() if v]
                if g_items:
                    guidance_lines.append(f"- {a.quarter} guidance: {'; '.join(g_items)}")
            if a.future_targets:
                for t in a.future_targets[:3]:
                    guidance_lines.append(f"- {a.quarter} target: {t}")

        # 3. Promise Tracking (from per-quarter assessment)
        promise_lines = []
        for a in analyses:
            if a.prior_guidance_met:
                for p in a.prior_guidance_met:
                    promise_lines.append(f"- {a.quarter}: ACHIEVED — {p.get('target', '')} → {p.get('actual', '')}")
            if a.prior_guidance_missed:
                for p in a.prior_guidance_missed:
                    promise_lines.append(f"- {a.quarter}: MISSED — {p.get('target', '')} → {p.get('actual', '')}")

        # 4. Analyst Concerns
        concern_lines = []
        for a in analyses:
            if a.analyst_concerns:
                for c in a.analyst_concerns[:3]:
                    concern_lines.append(f"- {a.quarter}: {c}")

        # 5. Key Highlights & Milestones
        milestone_lines = []
        for a in analyses:
            if a.milestones_achieved:
                for m in a.milestones_achieved[:3]:
                    milestone_lines.append(f"- {a.quarter} [ACHIEVED]: {m}")
            if a.concerns:
                for c in a.concerns[:3]:
                    milestone_lines.append(f"- {a.quarter} [CONCERN]: {c}")

        # 6. Segment Data
        segment_lines = []
        for a in analyses:
            if a.segment_data:
                for s in a.segment_data:
                    name = s.get("name", "?")
                    rev = s.get("revenue_cr")
                    growth = s.get("growth_pct")
                    margin = s.get("margin_pct")
                    parts = [f"{a.quarter} | {name}"]
                    if rev is not None:  # Issue #24: use 'is not None' for zero-value safety
                        try:
                            parts.append(f"Rev: Rs {float(rev):,.0f} Cr")
                        except (ValueError, TypeError):
                            parts.append(f"Rev: Rs {rev} Cr")
                    if growth is not None:
                        try:
                            parts.append(f"Growth: {float(growth):+.1f}%")
                        except (ValueError, TypeError):
                            parts.append(f"Growth: {growth}%")
                    if margin is not None:
                        try:
                            parts.append(f"Margin: {float(margin):.1f}%")
                        except (ValueError, TypeError):
                            parts.append(f"Margin: {margin}%")
                    segment_lines.append("- " + " | ".join(parts))

        # 7. Management Quotes
        quote_lines = []
        for a in analyses:
            if a.management_quotes:
                for q in a.management_quotes[:2]:
                    quote_lines.append(f'- {a.quarter}: "{q}"')

        # Assemble the prompt
        period = f"{analyses[0].quarter} to {analyses[-1].quarter}" if len(analyses) > 1 else analyses[0].quarter

        prompt = f"""You are a senior equity research analyst writing a COMPREHENSIVE 10-QUARTER INTELLIGENCE BRIEFING for company {symbol}.

You have access to {len(analyses)} quarters of conference call analysis data spanning {period}.
Your job is to CONNECT THE DOTS across quarters — find patterns, track promises, identify inflection points, and assess management credibility.

=== FINANCIAL PROGRESSION ===
{chr(10).join(financial_lines) if financial_lines else "No financial data available."}

=== MANAGEMENT GUIDANCE & TARGETS HISTORY ===
{chr(10).join(guidance_lines) if guidance_lines else "No guidance data available."}

=== PROMISE TRACKING (Prior Guidance vs Delivery) ===
{chr(10).join(promise_lines) if promise_lines else "No promise tracking data available."}

=== ANALYST CONCERNS ACROSS QUARTERS ===
{chr(10).join(concern_lines) if concern_lines else "No analyst concern data available."}

=== MILESTONES & CONCERNS ===
{chr(10).join(milestone_lines) if milestone_lines else "No milestone data available."}

=== SEGMENT PERFORMANCE ===
{chr(10).join(segment_lines) if segment_lines else "No segment data available."}

=== MANAGEMENT QUOTES ===
{chr(10).join(quote_lines) if quote_lines else "No quotes available."}

Now produce a connected intelligence report as valid JSON (no markdown, no code fences):
{{
  "management_credibility_score": <0-100: what % of promises/guidance were met>,
  "credibility_trend": "<Improving|Declining|Stable>",
  "overall_narrative": "<3-5 sentence story arc of how this company evolved over {len(analyses)} quarters. What's the big picture? What changed? Where is it heading?>",

  "promise_tracker": [
    {{
      "promise": "<what was promised>",
      "committed_quarter": "<when promised>",
      "target_quarter": "<deadline if given>",
      "current_status": "<Delivered|Missed|In Progress|Delayed|Abandoned|Partially Met|Not Yet Due>",
      "delivery_quarter": "<when delivered, or empty>",
      "evidence": "<brief evidence>",
      "credibility_impact": <-1.0 to 1.0>
    }}
  ],

  "analyst_concern_evolution": [
    {{
      "concern": "<the core concern topic>",
      "first_raised_quarter": "<first quarter>",
      "quarters_raised": ["<all quarters where this concern appeared>"],
      "management_responses": [
        {{"quarter": "<quarter>", "response": "<management's response>"}}
      ],
      "current_status": "<Addressed|Recurring|Escalating|Dismissed|Partially Addressed>",
      "severity": "<high|medium|low>"
    }}
  ],

  "segment_trends": [
    {{
      "name": "<segment name>",
      "quarterly_data": [{{"quarter": "<Q>", "revenue_cr": <num>, "growth_pct": <num>, "margin_pct": <num>}}],
      "trend": "<Growing|Declining|Volatile|Stable|New>",
      "significance": "<why this matters>"
    }}
  ],

  "risk_trajectory": [
    {{
      "risk": "<risk description>",
      "direction": "<Escalating|Resolving|New|Stable|Recurring>",
      "first_quarter": "<first quarter>",
      "last_quarter": "<last quarter>",
      "quarters_mentioned": <number>,
      "detail": "<how the risk evolved>"
    }}
  ],

  "key_inflection_points": [
    {{
      "quarter": "<quarter>",
      "event": "<what happened>",
      "impact": "<what changed because of this>",
      "sentiment_shift": <float change in sentiment score, or null>
    }}
  ],

  "red_flags": [
    "<things that should worry an investor — be specific with numbers>"
  ],

  "green_flags": [
    "<things that should excite an investor — be specific with numbers>"
  ],

  "financial_progression": [
    {{
      "quarter": "<quarter>",
      "revenue_cr": <number or null>,
      "ebitda_margin_pct": <number or null>,
      "pat_cr": <number or null>,
      "sentiment_score": <number>
    }}
  ]
}}"""

        return prompt

    def _parse_synthesis_response(
        self,
        response_text: str,
        analyses: list[SentimentResult],
        symbol: str,
    ) -> Optional[CrossQuarterIntelligence]:
        """Parse Gemini's synthesis JSON into CrossQuarterIntelligence."""
        try:
            clean = response_text.strip()
            # Issue #10 (same as gemini_analyzer): Robust JSON extraction
            clean = re.sub(r'^```(?:json)?\s*', '', clean, flags=re.MULTILINE)
            clean = re.sub(r'\s*```\s*$', '', clean, flags=re.MULTILINE)
            json_start = clean.find('{')
            json_end = clean.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                clean = clean[json_start:json_end + 1]
            data = json.loads(clean)

            period = f"{analyses[0].quarter} to {analyses[-1].quarter}" if len(analyses) > 1 else analyses[0].quarter

            # Parse promise tracker (Issue #23: log malformed promises)
            promises = []
            for p in data.get("promise_tracker", []):
                if isinstance(p, dict):
                    try:
                        # Issue #21: Safe float conversion for credibility_impact
                        try:
                            cred_impact = float(p.get("credibility_impact", 0.0))
                        except (ValueError, TypeError):
                            cred_impact = 0.0
                        promises.append(PromiseTracker(
                            promise=p.get("promise", ""),
                            committed_quarter=p.get("committed_quarter", ""),
                            target_quarter=p.get("target_quarter", ""),
                            current_status=p.get("current_status", "In Progress"),
                            delivery_quarter=p.get("delivery_quarter", ""),
                            evidence=p.get("evidence", ""),
                            credibility_impact=cred_impact,
                        ))
                    except Exception as e:
                        print(f"[IntelligenceEngine] Skipping malformed promise: {e} — data: {p}")

            # Parse analyst concern evolution (Issue #23: log malformed entries)
            concerns = []
            for c in data.get("analyst_concern_evolution", []):
                if isinstance(c, dict):
                    try:
                        concerns.append(AnalystConcernEvolution(
                            concern=c.get("concern", ""),
                            first_raised_quarter=c.get("first_raised_quarter", ""),
                            quarters_raised=c.get("quarters_raised", []),
                            management_responses=c.get("management_responses", []),
                            current_status=c.get("current_status", "Recurring"),
                            severity=c.get("severity", "medium"),
                        ))
                    except Exception as e:
                        print(f"[IntelligenceEngine] Skipping malformed concern: {e} — data: {c}")

            # Parse segment trends (Issue #23: log malformed entries)
            segments = []
            for s in data.get("segment_trends", []):
                if isinstance(s, dict):
                    try:
                        segments.append(SegmentTrend(
                            name=s.get("name", ""),
                            quarterly_data=s.get("quarterly_data", []),
                            trend=s.get("trend", "Stable"),
                            significance=s.get("significance", ""),
                        ))
                    except Exception as e:
                        print(f"[IntelligenceEngine] Skipping malformed segment: {e} — data: {s}")

            # Parse risk trajectory (Issue #21/#23: safe int conversion, log errors)
            risks = []
            for r in data.get("risk_trajectory", []):
                if isinstance(r, dict):
                    try:
                        try:
                            q_mentioned = int(r.get("quarters_mentioned", 0))
                        except (ValueError, TypeError):
                            q_mentioned = 0
                        risks.append(RiskTrajectory(
                            risk=r.get("risk", ""),
                            direction=r.get("direction", "New"),
                            first_quarter=r.get("first_quarter", ""),
                            last_quarter=r.get("last_quarter", ""),
                            quarters_mentioned=q_mentioned,
                            detail=r.get("detail", ""),
                        ))
                    except Exception as e:
                        print(f"[IntelligenceEngine] Skipping malformed risk: {e} — data: {r}")

            # Parse inflection points (Issue #25: also extract sentiment_shift)
            inflections = []
            for i in data.get("key_inflection_points", []):
                if isinstance(i, dict):
                    try:
                        ss_raw = i.get("sentiment_shift")
                        try:
                            ss = float(ss_raw) if ss_raw is not None else None
                        except (ValueError, TypeError):
                            ss = None
                        inflections.append(InflectionPoint(
                            quarter=i.get("quarter", ""),
                            event=i.get("event", ""),
                            impact=i.get("impact", ""),
                            sentiment_shift=ss,
                        ))
                    except Exception as e:
                        print(f"[IntelligenceEngine] Skipping malformed inflection: {e} — data: {i}")

            # Issue #22: Validate financial_progression entries
            raw_fin_prog = data.get("financial_progression", [])
            validated_fin_prog = []
            if isinstance(raw_fin_prog, list):
                for fp in raw_fin_prog:
                    if isinstance(fp, dict) and "quarter" in fp:
                        validated_fin_prog.append(fp)
                    else:
                        print(f"[IntelligenceEngine] Skipping malformed financial_progression entry: {fp}")

            # Issue #21: Safe float for credibility score
            try:
                mgmt_cred = float(data.get("management_credibility_score", 50.0))
            except (ValueError, TypeError):
                mgmt_cred = 50.0

            return CrossQuarterIntelligence(
                symbol=symbol,
                quarters_analyzed=len(analyses),
                analysis_period=period,
                management_credibility_score=mgmt_cred,
                credibility_trend=data.get("credibility_trend", "Stable"),
                overall_narrative=data.get("overall_narrative", ""),
                promise_tracker=promises,
                analyst_concern_evolution=concerns,
                segment_trends=segments,
                risk_trajectory=risks,
                key_inflection_points=inflections,
                red_flags=data.get("red_flags", []),
                green_flags=data.get("green_flags", []),
                financial_progression=validated_fin_prog,
            )

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            print(f"[IntelligenceEngine] JSON parse error: {e}")
            return None

    def _rule_based_synthesis(
        self,
        analyses: list[SentimentResult],
        symbol: str,
    ) -> CrossQuarterIntelligence:
        """Fallback: produce a basic synthesis without Gemini."""
        period = f"{analyses[0].quarter} to {analyses[-1].quarter}" if len(analyses) > 1 else analyses[0].quarter

        # Build financial progression
        fin_prog = []
        for a in analyses:
            fin_prog.append({
                "quarter": a.quarter,
                "revenue_cr": a.revenue_absolute,
                "ebitda_margin_pct": a.ebitda_margin_pct,
                "pat_cr": a.pat_absolute,
                "sentiment_score": a.sentiment_score,
            })

        # Simple promise tracking from per-quarter data
        promises = []
        for a in analyses:
            for p in a.prior_guidance_met:
                promises.append(PromiseTracker(
                    promise=p.get("target", ""),
                    committed_quarter="Prior quarter",
                    current_status="Delivered",
                    delivery_quarter=a.quarter,
                    evidence=p.get("actual", ""),
                    credibility_impact=0.5,
                ))
            for p in a.prior_guidance_missed:
                promises.append(PromiseTracker(
                    promise=p.get("target", ""),
                    committed_quarter="Prior quarter",
                    current_status="Missed",
                    delivery_quarter=a.quarter,
                    evidence=p.get("actual", ""),
                    credibility_impact=-0.5,
                ))

        # Credibility score
        # Issue #26: Weighted credibility score — PARTIALLY MET = 0.5 credit
        total_promises = len(promises)
        weighted_met = sum(
            1.0 if p.current_status == "Delivered" else 0.5 if p.current_status == "Partially Met" else 0.0
            for p in promises
        )
        credibility = (weighted_met / total_promises * 100) if total_promises > 0 else 50.0

        # Sentiment trend for narrative
        scores = [a.sentiment_score for a in analyses]
        avg_score = sum(scores) / len(scores) if scores else 0
        trend_dir = "positive" if scores[-1] > scores[0] else "negative" if scores[-1] < scores[0] else "stable"
        narrative = (
            f"Over {len(analyses)} quarters ({period}), the company's sentiment trend has been {trend_dir}. "
            f"Average sentiment score: {avg_score:+.2f}. "
            f"Management credibility based on {total_promises} tracked promises: {credibility:.0f}%. "
            f"Run with Gemini AI for a deeper connected narrative."
        )

        # Collect all red/green flags
        red_flags = []
        green_flags = []
        for a in analyses[-3:]:
            for c in a.concerns[:2]:
                red_flags.append(f"{a.quarter}: {c}")
            for h in a.key_highlights[:2]:
                green_flags.append(f"{a.quarter}: {h}")

        return CrossQuarterIntelligence(
            symbol=symbol,
            quarters_analyzed=len(analyses),
            analysis_period=period,
            management_credibility_score=credibility,
            credibility_trend="Stable",
            overall_narrative=narrative,
            promise_tracker=promises,
            analyst_concern_evolution=[],
            segment_trends=[],
            risk_trajectory=[],
            key_inflection_points=[],
            red_flags=red_flags[:5],
            green_flags=green_flags[:5],
            financial_progression=fin_prog,
        )
