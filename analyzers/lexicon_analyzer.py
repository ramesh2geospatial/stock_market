"""
Enhanced lexicon-based sentiment analyzer for financial text.
Offline, fast, no API key needed. Acts as fallback when Gemini is unavailable.
"""
import re
from analyzers.base import BaseSentimentAnalyzer
from models.analysis import SentimentResult


# --- Separate single-word and multi-word terms to prevent double-counting (Issue #30) ---
POSITIVE_SINGLE_WORDS = {
    # Growth & performance
    "increase", "increased", "rise", "risen", "grow", "growth", "grew",
    "profit", "profitable", "profitability", "bullish", "gain", "gains",
    "approve", "approval", "acquisition", "win", "wins", "won",
    "high", "higher", "highest", "success", "successful",
    "expand", "expansion", "expanding", "lead", "leading",
    "strengthen", "strengthened", "positive", "outlook",
    "deal", "beat", "beats", "beating", "surge", "surged",
    "jump", "jumped", "strong", "stronger", "strongest",
    "climb", "climbing", "recover", "recovery", "rebound",
    "improve", "improved", "improving", "improvement",
    "momentum", "accelerate", "accelerated", "acceleration",
    "outperform", "outperformed", "exceed", "exceeded", "exceeding",
    "milestone", "achieved", "achievement", "record", "breakthrough",
    "robust", "resilient", "resilience", "healthy", "stable", "stability",
    "upgrade", "upgraded", "optimistic", "confident", "confidence",
    "dividend", "buyback", "deleveraging", "deleverage",
    "turnaround",
    # Operational
    "launch", "launched", "scale", "scaling", "scaled",
    "innovation", "innovative", "efficiency", "efficient",
    "penetration", "traction", "ramp", "ramping",
    "commissioning", "commissioned", "operational", "commenced",
}

POSITIVE_BIGRAMS = [
    "margin expansion", "ebitda growth", "order inflow",
    "market share", "cash flow", "book to bill",
]

NEGATIVE_SINGLE_WORDS = {
    # Decline & risk
    "decrease", "decreased", "fall", "fallen", "decline", "declined", "declining",
    "loss", "losses", "bearish", "drop", "dropped", "dropping",
    "disapprove", "lose", "losing", "widen", "widened", "widening",
    "low", "lower", "lowest", "failure", "failed",
    "contract", "contracted", "contraction", "weaken", "weakened",
    "negative", "warn", "warning", "warned",
    "probe", "investigation", "lawsuit", "fine", "fined",
    "penalty", "deficit", "scam", "fraud", "crash", "crashed",
    "plunge", "plunged", "concern", "concerned", "concerns",
    "dispute", "disputed", "slow", "slowing", "slowdown",
    "sluggish", "debt", "risk", "risks", "risky",
    "pressure", "pressured", "softness", "soft",
    "headwind", "headwinds", "uncertainty", "uncertain",
    "volatile", "volatility", "impair", "impairment",
    "challenge", "challenged", "challenging", "challenges",
    "restructure", "restructuring", "closure", "closures", "closed",
    "inflation", "inflationary", "recession", "recessionary",
    "downgrade", "downgraded", "default", "defaulted",
    "write-off", "writeoff", "writedown", "erosion",
    "muted", "subdued", "cautious", "caution",
    "attrition",
}

NEGATIVE_BIGRAMS = [
    "margin compression", "margin pressure", "cost overrun",
    "supply chain", "working capital",
]

# Keywords that signal key management highlights (Issue #33: expanded)
HIGHLIGHT_KEYWORDS = [
    "ebitda", "margin", "growth", "revenue", "demand", "profit",
    "outlook", "store", "volume", "guidance", "target", "capex",
    "expansion", "market share", "order book", "pipeline",
    "commissioning", "capacity", "utilization", "milestone",
    "working capital", "cash flow", "receivables", "payables",
    "order inflow", "backlog", "headcount",
]

# Keywords that signal concerns (Issue #33: expanded)
CONCERN_KEYWORDS = [
    "concern", "challenge", "risk", "pressure", "inflation",
    "headwind", "uncertainty", "debt", "loss", "slowdown",
    "closure", "restructuring", "impairment", "default",
    "supply chain", "logistics", "regulatory", "compliance",
    "forex", "currency", "attrition",
]

# Keywords for milestones
MILESTONE_KEYWORDS = [
    "achieved", "milestone", "record", "commissioned", "launched",
    "crossed", "reached", "completed", "inaugurated", "operational",
    "turnaround", "breakeven", "break-even", "first time",
]

# Keywords for future targets (Issue #34: removed greedy "fy2", "fy3")
TARGET_KEYWORDS = [
    "target", "guidance", "expect", "plan", "pipeline", "roadmap",
    "aim", "aspire", "goal", "will", "intend", "strategy",
    "next quarter", "next year",
]

# Keywords for institutional concall analysis sections
VOLUME_YIELD_KEYWORDS = [
    "volume", "realization", "yield", "demand", "tonnage", "units",
    "pricing power", "price increase", "blended realization", "offtake",
    "sales volume", "shipments", "ticket size", "arpu",
]

PRODUCTIVITY_KEYWORDS = [
    "productivity", "efficiency", "utilization", "capacity", "cost per",
    "throughput", "footprint", "asset turn", "automation", "bottleneck",
    "de-bottlenecking", "oee", "turnaround time", "yield improvement",
]

MARGIN_ARCHITECTURE_KEYWORDS = [
    "margin", "ebitda", "gross margin", "opm", "cost structure",
    "operating leverage", "raw material", "input cost", "cost optimization",
    "favorable mix", "freight cost", "power and fuel", "spread",
]

CUSTOMER_SEGMENTATION_KEYWORDS = [
    "customer", "client", "segment", "retail", "enterprise", "b2b", "b2c",
    "tier", "geography", "demographic", "cohort", "key accounts", "distribution",
    "channel", "deal size", "oem", "dealer",
]

CAPITAL_ALLOCATION_KEYWORDS = [
    "capex", "capital allocation", "debt", "deleverage", "dividend",
    "buyback", "roic", "roe", "capital expenditure", "working capital",
    "cash flow", "reinvestment", "free cash", "repayment",
]

GUIDANCE_COMMITMENTS_KEYWORDS = [
    "guidance", "target", "commit", "committed", "outlook", "expect",
    "aim", "aspire", "pipeline", "fy25", "fy26", "fy27", "horizon",
    "double-digit", "on track",
]

KEY_TAKEAWAYS_KEYWORDS = [
    "takeaway", "summary", "highlight", "performance", "key driver",
    "milestone", "record", "growth", "strategy", "transform",
]

# Issue #31: Sentence splitting regex with negative lookbehinds for common abbreviations
_SENTENCE_SPLIT_RE = re.compile(
    r'(?<=[.!?])'
    r'(?<!\bMr\.)'
    r'(?<!\bMs\.)'
    r'(?<!\bDr\.)'
    r'(?<!\bRs\.)'
    r'(?<!\bvs\.)'
    r'(?<!\bSt\.)'
    r'(?<!\bNo\.)'
    r'(?<!\bCr\.)'
    r'(?<!\bLt\.)'
    r'\s+'
)


class LexiconAnalyzer(BaseSentimentAnalyzer):
    """
    Enhanced rule-based financial sentiment analyzer.
    150+ financial terms, bigram support, section weighting.
    """

    def analyze_text(self, text: str) -> SentimentResult:
        """Quick sentiment score from text."""
        score, label = self._score(text)
        return SentimentResult(
            sentiment_score=score,
            sentiment_label=label,
            analyzer_type="lexicon",
        )

    def analyze_concall(
        self, text: str, quarter: str,
        prior_guidance=None, prior_targets=None,  # Issue #1: Accept kwargs to match GeminiAnalyzer
    ) -> SentimentResult:
        """
        Deep analysis of a concall transcript.
        Extracts highlights, concerns, milestones, and future targets
        using keyword matching on sentences.
        """
        score, label = self._score(text)
        sentences = _SENTENCE_SPLIT_RE.split(text)  # Issue #31: Better sentence splitting

        highlights = []
        concerns = []
        milestones = []
        targets = []

        key_takeaways = []
        volume_yield_flywheel = []
        productivity_efficiency = []
        margin_architecture = []
        customer_segmentation = []
        capital_allocation = []
        guidance_commitments = []

        for s in sentences:
            clean = s.strip().replace("\n", " ")
            if len(clean) < 30 or len(clean) > 500:  # Issue #32: Increased max from 250 to 500
                continue
            lower = clean.lower()

            # Issue #33: Allow sentence to appear in MULTIPLE categories (changed elif → if)
            if any(kw in lower for kw in MILESTONE_KEYWORDS) and len(milestones) < 5:
                milestones.append(clean)
            if any(kw in lower for kw in CONCERN_KEYWORDS) and len(concerns) < 5:
                concerns.append(clean)
            if any(kw in lower for kw in TARGET_KEYWORDS) and len(targets) < 5:
                targets.append(clean)
            if any(kw in lower for kw in HIGHLIGHT_KEYWORDS) and len(highlights) < 5:
                highlights.append(clean)

            # Institutional Concall Sections
            if any(kw in lower for kw in KEY_TAKEAWAYS_KEYWORDS) and len(key_takeaways) < 5:
                key_takeaways.append(clean)
            if any(kw in lower for kw in VOLUME_YIELD_KEYWORDS) and len(volume_yield_flywheel) < 5:
                volume_yield_flywheel.append(clean)
            if any(kw in lower for kw in PRODUCTIVITY_KEYWORDS) and len(productivity_efficiency) < 5:
                productivity_efficiency.append(clean)
            if any(kw in lower for kw in MARGIN_ARCHITECTURE_KEYWORDS) and len(margin_architecture) < 5:
                margin_architecture.append(clean)
            if any(kw in lower for kw in CUSTOMER_SEGMENTATION_KEYWORDS) and len(customer_segmentation) < 5:
                customer_segmentation.append(clean)
            if any(kw in lower for kw in CAPITAL_ALLOCATION_KEYWORDS) and len(capital_allocation) < 5:
                capital_allocation.append(clean)
            if any(kw in lower for kw in GUIDANCE_COMMITMENTS_KEYWORDS) and len(guidance_commitments) < 5:
                guidance_commitments.append(clean)

        if not key_takeaways and highlights:
            key_takeaways = highlights[:5]
        if not guidance_commitments and targets:
            guidance_commitments = targets[:5]

        fin_nums = self._extract_financial_numbers(text)
        op_metrics = {}
        if fin_nums.get("revenue_absolute") is not None:
            op_metrics["Revenue (Rs Cr)"] = f"{fin_nums['revenue_absolute']:,.1f}"
        if fin_nums.get("ebitda_margin_pct") is not None:
            op_metrics["EBITDA Margin"] = f"{fin_nums['ebitda_margin_pct']:.1f}%"
        if fin_nums.get("pat_absolute") is not None:
            op_metrics["PAT (Rs Cr)"] = f"{fin_nums['pat_absolute']:,.1f}"
        if fin_nums.get("net_debt_cr") is not None:
            op_metrics["Net Debt (Rs Cr)"] = f"{fin_nums['net_debt_cr']:,.1f}"
        if fin_nums.get("order_book_cr") is not None:
            op_metrics["Order Book (Rs Cr)"] = f"{fin_nums['order_book_cr']:,.1f}"

        segment_data = fin_nums.get("segment_data", [])
        if segment_data:
            for seg in segment_data:
                seg_name = seg.get("name", "").strip()
                if not seg_name:
                    continue
                if seg.get("revenue_cr") is not None:
                    rev_val = seg["revenue_cr"]
                    rev_str = f"Rs {rev_val:,.1f} Cr" if isinstance(rev_val, (int, float)) else str(rev_val)
                    op_metrics[f"Segment: {seg_name} Revenue"] = rev_str
                if seg.get("margin_pct") is not None:
                    margin_val = seg["margin_pct"]
                    margin_str = f"{margin_val:.1f}%" if isinstance(margin_val, (int, float)) else str(margin_val)
                    op_metrics[f"Segment: {seg_name} Margin"] = margin_str

        # Determine management tone
        if score > 0.3:
            tone = "Confident"
        elif score > 0.1:
            tone = "Optimistic"
        elif score > -0.1:
            tone = "Measured"
        elif score > -0.3:
            tone = "Cautious"
        else:
            tone = "Concerned"

        return SentimentResult(
            quarter=quarter,
            sentiment_score=score,
            sentiment_label=label,
            key_highlights=highlights,
            concerns=concerns,
            milestones_achieved=milestones,
            future_targets=targets,
            management_tone=tone,
            key_takeaways=key_takeaways,
            volume_yield_flywheel=volume_yield_flywheel,
            productivity_efficiency=productivity_efficiency,
            margin_architecture=margin_architecture,
            customer_segmentation=customer_segmentation,
            capital_allocation=capital_allocation,
            guidance_commitments=guidance_commitments,
            key_operational_metrics=op_metrics,
            # Enrich with regex-extracted financial numbers
            **fin_nums,
        )

    def _score(self, text: str) -> tuple[float, str]:
        """Compute sentiment score and label.
        Issue #30: Separate single-word and bigram counting to prevent double-counting.
        """
        words = re.findall(r'\b\w+\b', text.lower())
        text_lower = text.lower()

        # Single-word matches (only from single-word sets)
        pos = sum(1 for w in words if w in POSITIVE_SINGLE_WORDS)
        neg = sum(1 for w in words if w in NEGATIVE_SINGLE_WORDS)

        # Bigram matches — count all occurrences, weighted at 2 each
        for term in POSITIVE_BIGRAMS:
            pos += 2 * text_lower.count(term)
        for term in NEGATIVE_BIGRAMS:
            neg += 2 * text_lower.count(term)

        total = pos + neg
        if total == 0:
            return 0.0, "Neutral"

        score = round((pos - neg) / total, 2)
        score = max(-1.0, min(1.0, score))

        if score > 0.15:
            label = "Positive"
        elif score < -0.15:
            label = "Negative"
        else:
            label = "Neutral"

        return score, label

    @staticmethod
    def _extract_financial_numbers(text: str) -> dict:
        """
        Regex-based extraction of financial numbers from transcript text.
        Returns a dict of fields suitable for unpacking into SentimentResult.
        Used to enrich the lexicon fallback when Gemini is unavailable.
        """
        result = {"analyzer_type": "lexicon"}
        text_lower = text.lower()
        found_any = False

        # --- Revenue / Sales (Rs Cr) ---
        # Patterns: "revenue of Rs 2,400 crore", "sales at INR 1200 Cr", "turnover Rs. 3,500 Cr"
        rev_patterns = [
            re.compile(
                r"(?:revenue|sales|turnover|top\s*line)\s+(?:of\s+|at\s+|was\s+|stood\s+at\s+|is\s+)?"
                r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?|lakh\s+cr)",
                re.IGNORECASE,
            ),
        ]
        for pat in rev_patterns:
            m = pat.search(text)
            if m:
                try:
                    result["revenue_absolute"] = float(m.group(1).replace(",", ""))
                    found_any = True
                except ValueError:
                    pass
                break

        # --- PAT / Net Profit (Rs Cr) ---
        pat_patterns = [
            re.compile(
                r"(?:pat|net\s+profit|profit\s+after\s+tax|bottom\s*line)\s+(?:of\s+|at\s+|was\s+|stood\s+at\s+|is\s+)?"
                r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?|lakh\s+cr)",
                re.IGNORECASE,
            ),
        ]
        for pat in pat_patterns:
            m = pat.search(text)
            if m:
                try:
                    result["pat_absolute"] = float(m.group(1).replace(",", ""))
                    found_any = True
                except ValueError:
                    pass
                break

        # --- Revenue Growth % ---
        growth_patterns = [
            re.compile(
                r"(?:revenue|sales|top\s*line)\s+(?:grew|growth|increased|rose|jumped|surged)\s+"
                r"(?:by\s+)?(\d+(?:\.\d+)?)\s*%",
                re.IGNORECASE,
            ),
            re.compile(
                r"(\d+(?:\.\d+)?)\s*%\s+(?:yoy|y-o-y|year.on.year)\s+(?:revenue|sales|top\s*line)\s+(?:growth|increase)",
                re.IGNORECASE,
            ),
        ]
        for pat in growth_patterns:
            m = pat.search(text)
            if m:
                try:
                    result["revenue_growth_pct"] = float(m.group(1))
                    found_any = True
                except ValueError:
                    pass
                break

        # --- PAT Growth % ---
        pat_growth_patterns = [
            re.compile(
                r"(?:pat|net\s+profit|profit\s+after\s+tax)\s+(?:grew|growth|increased|rose|jumped)\s+"
                r"(?:by\s+)?(\d+(?:\.\d+)?)\s*%",
                re.IGNORECASE,
            ),
        ]
        for pat in pat_growth_patterns:
            m = pat.search(text)
            if m:
                try:
                    result["pat_growth_pct"] = float(m.group(1))
                    found_any = True
                except ValueError:
                    pass
                break

        # --- EBITDA Margin % ---
        margin_patterns = [
            re.compile(
                r"(?:ebitda|operating)\s+margin\s+(?:of\s+|at\s+|was\s+|stood\s+at\s+|is\s+)?"
                r"(\d+(?:\.\d+)?)\s*%",
                re.IGNORECASE,
            ),
            re.compile(
                r"opm\s+(?:at\s+|of\s+)?(\d+(?:\.\d+)?)\s*%",
                re.IGNORECASE,
            ),
        ]
        for pat in margin_patterns:
            m = pat.search(text)
            if m:
                try:
                    result["ebitda_margin_pct"] = float(m.group(1))
                    found_any = True
                except ValueError:
                    pass
                break

        # --- Net Debt (Rs Cr) ---
        debt_patterns = [
            re.compile(
                r"(?:net\s+debt|total\s+debt|gross\s+debt)\s+(?:of\s+|at\s+|was\s+|stood\s+at\s+|is\s+)?"
                r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?)",
                re.IGNORECASE,
            ),
        ]
        for pat in debt_patterns:
            m = pat.search(text)
            if m:
                try:
                    result["net_debt_cr"] = float(m.group(1).replace(",", ""))
                    found_any = True
                except ValueError:
                    pass
                break

        # --- Order Book (Rs Cr) ---
        ob_patterns = [
            re.compile(
                r"(?:order\s+book|order\s+backlog|order\s+pipeline)\s+(?:of\s+|at\s+|was\s+|stood\s+at\s+|is\s+)?"
                r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?)",
                re.IGNORECASE,
            ),
        ]
        for pat in ob_patterns:
            m = pat.search(text)
            if m:
                try:
                    result["order_book_cr"] = float(m.group(1).replace(",", ""))
                    found_any = True
                except ValueError:
                    pass
                break

        # --- Segment Data ---
        segment_list = []
        seg_patterns = [
            re.compile(
                r"([A-Z][a-zA-Z0-9_\- ]+?)\s+(?:segment|division|business)\s+(?:revenue|sales)\s+(?:of\s+|at\s+|was\s+|stood\s+at\s+)?(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:cr(?:ore)?)",
                re.IGNORECASE,
            ),
        ]
        for pat in seg_patterns:
            for m in pat.finditer(text):
                try:
                    s_name = m.group(1).strip().title()
                    s_rev = float(m.group(2).replace(",", ""))
                    segment_list.append({"name": s_name, "revenue_cr": s_rev})
                    found_any = True
                except ValueError:
                    pass
        if segment_list:
            result["segment_data"] = segment_list

        if found_any:
            result["analyzer_type"] = "lexicon_enhanced"

        return result

