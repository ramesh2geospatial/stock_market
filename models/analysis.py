"""
Pydantic data models for analysis results.
Used by analyzers to produce structured output and by visualizers to render charts.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


_MILESTONE_STATUSES = (
    "Concern", "In Progress", "Almost Resolved", "Resolved", "Milestone Achieved", "Future Target"
)


class SentimentResult(BaseModel):
    """Result of sentiment analysis on a concall transcript or news."""
    quarter: str = ""
    transcript_date: str = ""  # e.g., "May 2026"
    transcript_url: str = ""
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    sentiment_label: Literal["Positive", "Negative", "Neutral"] = "Neutral"
    key_highlights: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    milestones_achieved: list[str] = Field(default_factory=list)
    future_targets: list[str] = Field(default_factory=list)
    management_tone: str = ""  # e.g., "Confident", "Cautious", "Optimistic"
    analyzer_type: str = "lexicon"  # "lexicon" or "gemini"
    # --- Enhanced extraction fields (populated by Gemini, optional) ---
    revenue_growth_pct: Optional[float] = None
    ebitda_margin_pct: Optional[float] = None
    pat_growth_pct: Optional[float] = None
    management_quotes: list[str] = Field(default_factory=list)
    analyst_concerns: list[str] = Field(default_factory=list)
    guidance_numbers: dict = Field(default_factory=dict)

    # --- NEW: Absolute financial numbers (Rs Cr) ---
    revenue_absolute: Optional[float] = None
    ebitda_absolute: Optional[float] = None
    pat_absolute: Optional[float] = None

    # --- NEW: Segment-level breakdown ---
    segment_data: list[dict] = Field(default_factory=list)
    # Each: {"name": "Retail", "revenue_cr": 1200, "growth_pct": 18, "margin_pct": 14.2}

    # --- NEW: Debt & leverage ---
    net_debt_cr: Optional[float] = None
    debt_equity_ratio: Optional[float] = None

    # --- NEW: Capex ---
    capex_actual_cr: Optional[float] = None

    # --- NEW: Order book (for infra/capital goods) ---
    order_book_cr: Optional[float] = None

    # --- NEW: Promise tracking (prior quarter guidance assessment) ---
    prior_guidance_met: list[dict] = Field(default_factory=list)
    # Each: {"target": "Revenue Rs 2500 Cr", "result": "ACHIEVED", "actual": "Rs 2520 Cr"}
    prior_guidance_missed: list[dict] = Field(default_factory=list)
    # Each: {"target": "Margin 20%", "result": "MISSED", "actual": "18.2%"}

    # --- Cross-validation: Gemini output vs Screener data ---
    data_confidence: Literal["high", "medium", "low"] = "high"
    corrections: list[dict] = Field(default_factory=list)
    # Each: {"field": "revenue_absolute", "gemini_value": 2400, "screener_value": 2800, "divergence_pct": 14.3}

    # --- 8 Institutional Concall Analysis Sections ---
    key_takeaways: list[str] = Field(default_factory=list)
    volume_yield_flywheel: list[str] = Field(default_factory=list)
    productivity_efficiency: list[str] = Field(default_factory=list)
    margin_architecture: list[str] = Field(default_factory=list)
    customer_segmentation: list[str] = Field(default_factory=list)
    capital_allocation: list[str] = Field(default_factory=list)
    guidance_commitments: list[str] = Field(default_factory=list)
    key_operational_metrics: dict = Field(default_factory=dict)

    @property
    def sentiment(self) -> str:
        """Alias for sentiment_label for multi-client compatibility."""
        return self.sentiment_label

    @property
    def score(self) -> float:
        """Alias for sentiment_score for multi-client compatibility."""
        return self.sentiment_score

    @property
    def positive_drivers(self) -> list[str]:
        """Alias for key_highlights for multi-client compatibility."""
        return self.key_highlights

    @property
    def key_risks(self) -> list[str]:
        """Alias for concerns for multi-client compatibility."""
        return self.concerns



class SpiderMetric(BaseModel):
    """A single dimension of the spider/radar chart."""
    name: str
    score: float = Field(default=50.0, ge=0.0, le=100.0)
    raw_value: Optional[str] = None  # Human-readable raw value (e.g., "Rs 2,400 Cr")
    trend: Literal["up", "down", "flat"] = "flat"  # 3-quarter direction


class QuarterSpiderData(BaseModel):
    """All spider metrics for a single quarter."""
    quarter: str  # e.g., "Q1 FY24"
    metrics: list[SpiderMetric] = Field(default_factory=list)
    overall_score: float = 0.0  # Average of all metric scores


class MilestoneTrack(BaseModel):
    """A business milestone tracked across quarters from concall analysis."""
    name: str
    status: Literal[
        "Concern", "In Progress", "Almost Resolved", "Resolved", "Milestone Achieved", "Future Target"
    ] = "In Progress"
    start_quarter: str = ""
    current_quarter: str = ""
    description: str = ""
    quarterly_updates: list[dict] = Field(default_factory=list)
    # Each dict: {"quarter": "Q1 FY24", "status": "In Progress", "note": "..."}

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v):
        if not isinstance(v, str):
            return "In Progress"
        lower_map = {opt.lower(): opt for opt in _MILESTONE_STATUSES}
        normalized = lower_map.get(v.strip().lower())
        return normalized if normalized is not None else "In Progress"
