"""
Pydantic model for Ground-Truth Financial Metrics extracted from official PDFs
(Investor Presentations and BSE/NSE Quarterly Financial Result announcements).
"""
from typing import Optional, Literal, Any
from pydantic import BaseModel, Field


class GroundTruthFinancials(BaseModel):
    """Ground-truth financial metrics extracted directly from official company PDFs."""
    symbol: str
    quarter: str  # e.g., "Q1 FY25", "Q4 FY24"
    doc_type: Literal["presentation", "financial_results"] = "presentation"

    # Core financial figures (Rs. Crores)
    revenue_cr: Optional[float] = None
    ebitda_cr: Optional[float] = None
    pat_cr: Optional[float] = None

    # Growth & margin percentages (%)
    revenue_growth_pct: Optional[float] = None
    ebitda_margin_pct: Optional[float] = None
    pat_growth_pct: Optional[float] = None

    # Detailed breakdown & Capex
    segment_results: list[dict[str, Any]] = Field(default_factory=list)
    capex_cr: Optional[float] = None
    guidance_numbers: dict[str, Any] = Field(default_factory=dict)

    # Metadata & Provenance
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extracted_at: Optional[str] = None
    source_pdf_url: Optional[str] = None
    source_local_path: Optional[str] = None
