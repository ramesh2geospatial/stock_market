"""
Pydantic data models for the Cross-Quarter Intelligence Engine.
These models represent the connected 10-quarter narrative produced
by the synthesis engine — connecting management promises, analyst
concerns, and business evolution across quarters.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


# --- Casing normalization helpers ---
def _normalize_to_options(value: str, options: tuple[str, ...], default: str) -> str:
    """Normalize a string value to match one of the allowed Literal options (case-insensitive)."""
    if not isinstance(value, str):
        return default
    lower_map = {opt.lower(): opt for opt in options}
    normalized = lower_map.get(value.strip().lower())
    return normalized if normalized is not None else default


_PROMISE_STATUSES = ("Delivered", "Missed", "In Progress", "Delayed", "Abandoned", "Partially Met", "Not Yet Due")
_CONCERN_STATUSES = ("Addressed", "Recurring", "Escalating", "Dismissed", "Partially Addressed")
_SEVERITY_LEVELS = ("high", "medium", "low")
_SEGMENT_TRENDS = ("Growing", "Declining", "Volatile", "Stable", "New")
_RISK_DIRECTIONS = ("Escalating", "Resolving", "New", "Stable", "Recurring")


class PromiseTracker(BaseModel):
    """Tracks a specific management promise from commitment to delivery."""
    promise: str                                    # What was promised
    committed_quarter: str                          # When promised
    target_quarter: Optional[str] = ""              # When to be delivered
    current_status: Literal[
        "Delivered", "Missed", "In Progress", "Delayed", "Abandoned", "Partially Met", "Not Yet Due"
    ] = "In Progress"
    delivery_quarter: Optional[str] = ""            # When actually delivered (if applicable)
    evidence: str = ""                              # Evidence for status
    credibility_impact: Optional[float] = 0.0       # -1.0 to +1.0 impact on credibility

    @field_validator("target_quarter", "delivery_quarter", mode="before")
    @classmethod
    def _normalize_quarter(cls, v):
        return v if v is not None else ""

    @field_validator("credibility_impact", mode="before")
    @classmethod
    def _normalize_impact(cls, v):
        if v is None:
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("current_status", mode="before")
    @classmethod
    def _normalize_status(cls, v):
        return _normalize_to_options(v, _PROMISE_STATUSES, "In Progress")


class AnalystConcernEvolution(BaseModel):
    """Tracks how a recurring analyst concern evolves across quarters."""
    concern: str                                    # The core concern topic
    first_raised_quarter: str                       # First appearance
    quarters_raised: list[str] = Field(default_factory=list)  # All quarters raised
    management_responses: list[dict] = Field(default_factory=list)
    # Each: {"quarter": "Q1 FY24", "response": "Management said..."}
    current_status: Literal[
        "Addressed", "Recurring", "Escalating", "Dismissed", "Partially Addressed"
    ] = "Recurring"
    severity: Literal["high", "medium", "low"] = "medium"

    @field_validator("current_status", mode="before")
    @classmethod
    def _normalize_status(cls, v):
        return _normalize_to_options(v, _CONCERN_STATUSES, "Recurring")

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, v):
        return _normalize_to_options(v, _SEVERITY_LEVELS, "medium")


class SegmentTrend(BaseModel):
    """Tracks a business segment's performance across quarters."""
    name: str                                       # Segment name
    quarterly_data: list[dict] = Field(default_factory=list)
    # Each: {"quarter": "Q1 FY24", "revenue_cr": 1200, "growth_pct": 18, "margin_pct": 14.2}
    trend: Literal["Growing", "Declining", "Volatile", "Stable", "New"] = "Stable"
    significance: str = ""                          # Why this segment matters

    @field_validator("trend", mode="before")
    @classmethod
    def _normalize_trend(cls, v):
        return _normalize_to_options(v, _SEGMENT_TRENDS, "Stable")


class RiskTrajectory(BaseModel):
    """Tracks how a specific risk evolves over time."""
    risk: str                                       # Risk description
    direction: Literal["Escalating", "Resolving", "New", "Stable", "Recurring"] = "New"
    first_quarter: str = ""
    last_quarter: str = ""
    quarters_mentioned: int = 0
    detail: str = ""

    @field_validator("direction", mode="before")
    @classmethod
    def _normalize_direction(cls, v):
        return _normalize_to_options(v, _RISK_DIRECTIONS, "New")


class InflectionPoint(BaseModel):
    """A significant turning point in the company's narrative."""
    quarter: str
    event: str
    impact: str                                     # What changed because of this
    sentiment_shift: Optional[float] = None         # Change in sentiment score


class CrossQuarterIntelligence(BaseModel):
    """
    The connected 10-quarter narrative produced by the synthesis engine.
    This is the ultimate output — connecting dots across all quarters
    to give investors a complete picture of management credibility,
    business evolution, and risk trajectory.
    """
    symbol: str = ""
    quarters_analyzed: int = 0
    analysis_period: str = ""                       # e.g., "Q1 FY23 to Q2 FY26"

    # Management credibility
    management_credibility_score: float = 50.0      # 0-100: % of promises met
    credibility_trend: str = ""                     # "Improving" / "Declining" / "Stable"

    # The story
    overall_narrative: str = ""                      # 3-5 sentence story arc

    # Detailed trackers
    promise_tracker: list[PromiseTracker] = Field(default_factory=list)
    analyst_concern_evolution: list[AnalystConcernEvolution] = Field(default_factory=list)
    segment_trends: list[SegmentTrend] = Field(default_factory=list)
    risk_trajectory: list[RiskTrajectory] = Field(default_factory=list)
    key_inflection_points: list[InflectionPoint] = Field(default_factory=list)

    # Summary flags
    red_flags: list[str] = Field(default_factory=list)     # Should worry investors
    green_flags: list[str] = Field(default_factory=list)   # Should excite investors

    # Financial progression (for charting)
    financial_progression: list[dict] = Field(default_factory=list)
    # Each: {"quarter": "Q1 FY24", "revenue_cr": 2400, "ebitda_margin_pct": 15.2, "pat_cr": 180}

    @property
    def credibility_index(self) -> float:
        """Alias for management_credibility_score."""
        return self.management_credibility_score

    @property
    def promise_delivery_rate(self) -> float:
        """Alias for management_credibility_score."""
        return self.management_credibility_score

    @property
    def promises_tracked(self) -> list[PromiseTracker]:
        """Alias for promise_tracker."""
        return self.promise_tracker
