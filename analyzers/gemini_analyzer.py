"""
Gemini AI-powered concall sentiment analyzer.
Uses Google's Gemini 2.5 Flash for deep structured extraction.
Falls back to LexiconAnalyzer if API key is missing or quota is exhausted.

Enhanced to extract:
- Absolute financial numbers (Revenue, EBITDA, PAT in Rs Cr)
- Segment-level breakdown
- Debt & leverage position
- Capex actual vs guided
- Promise tracking: prior quarter guidance → current quarter delivery
"""
import json
import time
import re
from typing import Optional

from analyzers.base import BaseSentimentAnalyzer
from analyzers.lexicon_analyzer import LexiconAnalyzer
from analyzers.text_preprocessor import preprocess_transcript
from models.analysis import SentimentResult
from config import GEMINI_MODEL


class GeminiAnalyzer(BaseSentimentAnalyzer):
    """
    AI-powered analyzer using Google Gemini.
    Extracts structured insights from concall transcripts.
    Auto-falls back to lexicon if API is unavailable.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = None
        self._fallback = LexiconAnalyzer()
        self._last_call_time = 0
        self._min_interval = 4.0  # ~15 RPM rate limit

        if api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=api_key)
            except ImportError:
                print("[GeminiAnalyzer] google-generativeai not installed. Using lexicon fallback.")
            except Exception as e:
                print(f"[GeminiAnalyzer] Init error: {e}. Using lexicon fallback.")

    def _rate_limit(self):
        """Enforce rate limiting to stay within free tier."""
        elapsed = time.time() - self._last_call_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call_time = time.time()

    def analyze_text(self, text: str) -> SentimentResult:
        """Quick sentiment analysis — uses lexicon for speed."""
        return self._fallback.analyze_text(text)

    def analyze_concall(
        self, text: str, quarter: str,
        prior_guidance: dict = None,
        prior_targets: list = None,
    ) -> SentimentResult:
        """
        Deep AI analysis of a concall transcript.
        Preprocesses text to strip boilerplate, then sends to Gemini
        with a structured extraction prompt.

        Args:
            text: Raw transcript text
            quarter: Quarter label (e.g., "Q1 FY25")
            prior_guidance: Previous quarter's guidance_numbers dict
            prior_targets: Previous quarter's future_targets list
        """
        if not self.client or not text.strip():
            return self._fallback.analyze_concall(text, quarter,
                                                  prior_guidance=prior_guidance,
                                                  prior_targets=prior_targets)

        # Preprocess: strip disclaimers, participant lists, operator lines
        cleaned_text = preprocess_transcript(text, max_chars=200000)
        if len(cleaned_text.strip()) < 200:
            return self._fallback.analyze_concall(text, quarter,
                                                  prior_guidance=prior_guidance,
                                                  prior_targets=prior_targets)

        prompt = self._build_prompt(cleaned_text, quarter, prior_guidance, prior_targets)

        try:
            self._rate_limit()
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )

            result = self._parse_response(response.text, quarter)
            if result:
                return result

        except Exception as e:
            error_str = str(e).lower()
            if any(kw in error_str for kw in ("quota", "429", "rate", "resource_exhausted")):
                print(f"[GeminiAnalyzer] Quota exceeded, falling back to lexicon for {quarter}")
            else:
                print(f"[GeminiAnalyzer] API error for {quarter}: {e}")

        # Fallback to lexicon (Issue #17: forward prior_guidance/prior_targets)
        return self._fallback.analyze_concall(text, quarter,
                                              prior_guidance=prior_guidance,
                                              prior_targets=prior_targets)

    def _build_prompt(
        self, text: str, quarter: str,
        prior_guidance: dict = None,
        prior_targets: list = None,
    ) -> str:
        # Build prior guidance context for promise tracking
        prior_context = ""
        if prior_guidance or prior_targets:
            prior_context = "\n\nPRIOR QUARTER GUIDANCE TO ASSESS:\n"
            prior_context += "The management gave the following guidance/targets in the PREVIOUS quarter's earnings call.\n"
            prior_context += "For each item, determine if it was ACHIEVED, MISSED, PARTIALLY MET, or NOT YET DUE based on this quarter's results.\n"
            if prior_guidance:
                prior_context += "\nGuidance Numbers:\n"
                for k, v in prior_guidance.items():
                    if v:
                        label = k.replace("_", " ").title()
                        prior_context += f"  - {label}: {v}\n"
            if prior_targets:
                prior_context += "\nFuture Targets Stated:\n"
                for t in prior_targets:
                    prior_context += f"  - {t}\n"
            prior_context += "\n"

        return f"""You are a senior equity research analyst at a top-tier Indian brokerage house. You are analyzing a conference call transcript for quarter {quarter} of an Indian listed company.

INSTRUCTIONS:
1. Read the ENTIRE transcript carefully — both the management commentary AND the Q&A section.
2. Pay special attention to the [Q&A SECTION] if marked — this contains the most valuable analyst pushback and management commitments.
3. The transcript may contain speaker role markers like [MANAGEMENT - Name, Title], [ANALYST - Name, Firm], and [MODERATOR]. Use these to:
   - Attribute management_quotes to the correct speaker (e.g., "Rajesh Kumar, CEO: ...").
   - Identify analyst_concerns by the analyst's name and firm when available.
   - Weight management statements higher than moderator/operator commentary.
4. Extract structured data following the EXACT JSON schema below.

CRITICAL RULES:
- Every highlight, concern, milestone, and target MUST include a specific NUMBER, PERCENTAGE, or AMOUNT where the transcript mentions one.
- GOOD example: "Revenue grew 18% YoY to Rs 2,400 Cr driven by 12% volume growth and 6% price realization"
- BAD example: "Revenue showed strong growth this quarter"
- GOOD example: "EBITDA margin contracted 150 bps to 14.2% due to higher raw material costs (+22% YoY)"
- BAD example: "Margins were under pressure"
- If no specific number is available for an insight, provide the qualitative context clearly.
- management_quotes: Extract 1-2 VERBATIM impactful quotes from the MD/CEO/CFO. Include the speaker name.
- analyst_concerns: What did analysts push back on or question repeatedly? Capture the substance.
- guidance_numbers: Extract specific forward guidance. Use null for any field where no guidance was given.
- segment_data: Break down performance by business segments if multiple segments are discussed.
- This is an Indian listed company. Financial years run April-March. Use Rs Cr / Rs Lakh Cr notation.
- **CRITICAL RULE FOR Q4 / FULL YEAR CALLS:** Earnings calls for the fourth quarter (Q4) generally discuss both the individual Q4 quarter results AND the full financial year (FY) results. You MUST extract ONLY the individual Q4 quarter-specific numbers (e.g. Q4 PAT, Q4 Revenue/GDPI) for `revenue_absolute_cr`, `ebitda_absolute_cr`, and `pat_absolute_cr`. DO NOT populate these fields with full-year (FY) values. If only full-year numbers are mentioned and no Q4 number is given, set these fields to null rather than using the full-year numbers. Always prioritize individual Q4 quarterly metrics.
{prior_context}
Return ONLY valid JSON (no markdown fences, no explanation, no text outside the JSON):
{{
  "sentiment_score": <float between -1.0 and 1.0>,
  "sentiment_label": "<Positive|Negative|Neutral>",
  "management_tone": "<one of: Confident, Optimistic, Measured, Cautious, Concerned, Defensive>",

  "revenue_absolute_cr": <total revenue in Rs Cr as number, or null>,
  "ebitda_absolute_cr": <EBITDA in Rs Cr as number, or null>,
  "pat_absolute_cr": <PAT/Net Profit in Rs Cr as number, or null>,
  "revenue_growth_pct": <YoY revenue growth % as number, or null>,
  "ebitda_margin_pct": <EBITDA margin % as number, or null>,
  "pat_growth_pct": <YoY PAT growth % as number, or null>,

  "segment_data": [
    {{
      "name": "<segment name>",
      "revenue_cr": <segment revenue in Rs Cr or null>,
      "growth_pct": <segment YoY growth % or null>,
      "margin_pct": <segment operating margin % or null>
    }}
  ],

  "net_debt_cr": <net debt in Rs Cr or null>,
  "debt_equity_ratio": <D/E ratio as number or null>,
  "capex_actual_cr": <actual capex spent this quarter/year in Rs Cr or null>,
  "order_book_cr": <order book / pipeline value in Rs Cr or null if not applicable>,

  "key_highlights": [
    "<top 5 specific positive developments with numbers/metrics — [TOPIC]: detail>"
  ],
  "concerns": [
    "<top 5 specific risks/challenges with numbers/context — [TOPIC]: detail>"
  ],
  "milestones_achieved": [
    "<specific things COMPLETED/ACHIEVED this quarter with evidence>"
  ],
  "future_targets": [
    "<specific forward guidance/plans with timeline and numbers>"
  ],
  "management_quotes": [
    "<1-2 verbatim impactful quotes from MD/CEO/CFO. Use speaker markers [MANAGEMENT - Name, Title] for attribution, e.g., 'Rajesh Kumar, CEO: We expect margins to...'>"
  ],
  "analyst_concerns": [
    "<top 2-3 substantive questions/pushbacks from analysts. Use speaker markers [ANALYST - Name, Firm] for attribution, e.g., 'Sanjay Mehta (HDFC Securities): What about margin pressures...'>"
  ],
  "guidance_numbers": {{
    "revenue_guidance": "<e.g., Rs 10,000 Cr for FY26 or null>",
    "margin_guidance": "<e.g., 18-20% EBITDA margin target or null>",
    "capex_guidance": "<e.g., Rs 500 Cr capex planned for FY26 or null>",
    "other_guidance": "<any other specific numeric target or null>"
  }},
  "prior_guidance_assessment": [
    {{
      "target": "<what was the previous guidance/target>",
      "result": "<ACHIEVED|MISSED|PARTIALLY MET|NOT YET DUE>",
      "actual": "<what was actually delivered>"
    }}
  ],
  "key_takeaways": [
    "<3-5 core strategic and operational takeaways from the call with key metrics>"
  ],
  "volume_yield_flywheel": [
    "<volume growth vs realization/yield dynamics, demand trends, pricing power, flywheel momentum>"
  ],
  "productivity_efficiency": [
    "<operational efficiency improvements, capacity utilization without footprint expansion, cost per unit>"
  ],
  "margin_architecture": [
    "<margin levers, gross vs EBITDA margin drivers, raw material cost pressures/gains, operating leverage>"
  ],
  "customer_segmentation": [
    "<customer mix, B2B vs B2C, enterprise/retail split, tier expansion, geographic/cohort performance>"
  ],
  "capital_allocation": [
    "<capex spending, debt repayment/leverage targets, dividend payouts, working capital, ROIC focus>"
  ],
  "guidance_commitments": [
    "<forward guidance commitments, strategic targets, revenue/margin outlook with timelines>"
  ],
  "key_operational_metrics": {{
    "<metric_name>": "<value with unit, e.g. capacity_utilization: '85%', arpu: 'Rs 210'>"
  }}
}}

Transcript text:
---
{text}
---"""

    def _parse_response(self, response_text: str, quarter: str) -> Optional[SentimentResult]:
        """Parse Gemini's JSON response into a SentimentResult."""
        try:
            # Issue #10: Robust JSON extraction — find the JSON object
            # regardless of preamble text or markdown fences
            clean = response_text.strip()
            # First try stripping code fences
            clean = re.sub(r'^```(?:json)?\s*', '', clean, flags=re.MULTILINE)
            clean = re.sub(r'\s*```\s*$', '', clean, flags=re.MULTILINE)
            # Then find the actual JSON object boundaries
            json_start = clean.find('{')
            json_end = clean.rfind('}')
            if json_start != -1 and json_end != -1 and json_end > json_start:
                clean = clean[json_start:json_end + 1]

            data = json.loads(clean)

            # Issue #11: Safe float conversion for sentiment_score
            try:
                score = float(data.get("sentiment_score", 0))
            except (ValueError, TypeError):
                score = 0.0
            score = max(-1.0, min(1.0, score))

            label = data.get("sentiment_label", "Neutral")
            if label not in ("Positive", "Negative", "Neutral"):
                label = "Positive" if score > 0.15 else "Negative" if score < -0.15 else "Neutral"

            # Parse optional numeric fields safely
            def _safe_float(val):
                if val is None:
                    return None
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None

            # Parse guidance_numbers, ensuring it's a dict
            raw_guidance = data.get("guidance_numbers")
            if not isinstance(raw_guidance, dict):
                raw_guidance = {}
            # Strip null string values
            guidance = {
                k: v for k, v in raw_guidance.items()
                if v is not None and str(v).lower() not in ("null", "n/a", "none", "")
            }

            # Parse segment_data
            raw_segments = data.get("segment_data", [])
            if not isinstance(raw_segments, list):
                raw_segments = []
            sanitized_segments = []
            for s in raw_segments:
                if isinstance(s, dict):
                    sanitized_segments.append({
                        "name": str(s.get("name", "Unknown")),
                        "revenue_cr": _safe_float(s.get("revenue_cr")),
                        "growth_pct": _safe_float(s.get("growth_pct")),
                        "margin_pct": _safe_float(s.get("margin_pct")),
                    })

            # Parse prior guidance assessment
            raw_prior_assessment = data.get("prior_guidance_assessment", [])
            if not isinstance(raw_prior_assessment, list):
                raw_prior_assessment = []

            # Issue #12/#13: Separate ACHIEVED and PARTIALLY MET; preserve NOT YET DUE
            prior_met = [
                a for a in raw_prior_assessment
                if isinstance(a, dict) and a.get("result", "").upper() in ("ACHIEVED",)
            ]
            # PARTIALLY MET items go to met list but with result preserved for weighted scoring
            prior_partially = [
                a for a in raw_prior_assessment
                if isinstance(a, dict) and a.get("result", "").upper() in ("PARTIALLY MET",)
            ]
            prior_missed = [
                a for a in raw_prior_assessment
                if isinstance(a, dict) and a.get("result", "").upper() in ("MISSED",)
            ]
            # Combine achieved + partially met for the met field (consumers can check result field)
            prior_met = prior_met + prior_partially

            # Parse 8 institutional concall sections
            key_takeaways = data.get("key_takeaways", []) if isinstance(data.get("key_takeaways"), list) else []
            volume_yield_flywheel = data.get("volume_yield_flywheel", []) if isinstance(data.get("volume_yield_flywheel"), list) else []
            productivity_efficiency = data.get("productivity_efficiency", []) if isinstance(data.get("productivity_efficiency"), list) else []
            margin_architecture = data.get("margin_architecture", []) if isinstance(data.get("margin_architecture"), list) else []
            customer_segmentation = data.get("customer_segmentation", []) if isinstance(data.get("customer_segmentation"), list) else []
            capital_allocation = data.get("capital_allocation", []) if isinstance(data.get("capital_allocation"), list) else []
            guidance_commitments = data.get("guidance_commitments", []) if isinstance(data.get("guidance_commitments"), list) else []
            key_operational_metrics = data.get("key_operational_metrics") if isinstance(data.get("key_operational_metrics"), dict) else {}

            return SentimentResult(
                quarter=quarter,
                sentiment_score=score,
                sentiment_label=label,
                management_tone=data.get("management_tone", ""),
                key_highlights=(data.get("key_highlights") or [])[:5],
                concerns=(data.get("concerns") or [])[:5],
                milestones_achieved=(data.get("milestones_achieved") or [])[:5],
                future_targets=(data.get("future_targets") or [])[:5],
                management_quotes=(data.get("management_quotes") or [])[:3],
                analyst_concerns=(data.get("analyst_concerns") or [])[:3],
                revenue_growth_pct=_safe_float(data.get("revenue_growth_pct")),
                ebitda_margin_pct=_safe_float(data.get("ebitda_margin_pct")),
                pat_growth_pct=_safe_float(data.get("pat_growth_pct")),
                guidance_numbers=guidance,
                # NEW enhanced fields
                revenue_absolute=_safe_float(data.get("revenue_absolute_cr")),
                ebitda_absolute=_safe_float(data.get("ebitda_absolute_cr")),
                pat_absolute=_safe_float(data.get("pat_absolute_cr")),
                segment_data=sanitized_segments,
                net_debt_cr=_safe_float(data.get("net_debt_cr")),
                debt_equity_ratio=_safe_float(data.get("debt_equity_ratio")),
                capex_actual_cr=_safe_float(data.get("capex_actual_cr")),
                order_book_cr=_safe_float(data.get("order_book_cr")),
                prior_guidance_met=prior_met,
                prior_guidance_missed=prior_missed,
                # 8 Institutional Concall Analysis Sections
                key_takeaways=key_takeaways,
                volume_yield_flywheel=volume_yield_flywheel,
                productivity_efficiency=productivity_efficiency,
                margin_architecture=margin_architecture,
                customer_segmentation=customer_segmentation,
                capital_allocation=capital_allocation,
                guidance_commitments=guidance_commitments,
                key_operational_metrics=key_operational_metrics,
                analyzer_type="gemini",
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            print(f"[GeminiAnalyzer] JSON parse error: {e}")
            return None
