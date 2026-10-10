"""
Pydantic data models for stock market data.
These models are the shared language between providers, analyzers, and visualizers.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class StockQuote(BaseModel):
    """Current stock quote and key metrics."""
    symbol: str
    name: str = ""
    current_price: float = 0.0
    previous_close: float = 0.0
    market_cap: float = 0.0
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    fifty_two_week_high: float = 0.0
    fifty_two_week_low: float = 0.0
    beta: Optional[float] = None
    enterprise_value: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    book_value: Optional[float] = None
    business_summary: str = ""
    sector: str = ""
    industry: str = ""

    @property
    def change(self) -> float:
        """Net price change from previous close."""
        return round(self.current_price - self.previous_close, 2)

    @property
    def change_percent(self) -> float:
        """Percentage price change from previous close."""
        if self.previous_close > 0:
            return round((self.change / self.previous_close) * 100.0, 2)
        return 0.0



class QuarterlyResult(BaseModel):
    """A single quarter's financial performance."""
    quarter: str  # e.g., "Mar 2024", "Jun 2024"
    revenue: float = 0.0
    expenses: float = 0.0
    operating_profit: float = 0.0
    opm_percent: float = 0.0
    other_income: float = 0.0
    interest: float = 0.0
    depreciation: float = 0.0
    profit_before_tax: float = 0.0
    tax_percent: float = 0.0
    net_profit: float = 0.0
    eps: float = 0.0


class DocumentLink(BaseModel):
    """A link to a company document (transcript, presentation, etc.)."""
    title: str
    url: str
    category: Literal[
        "transcript", "presentation", "financial_results", "credit_rating", "annual_report", "other"
    ] = "other"
    date_hint: Optional[str] = None  # Extracted date from title if available
    symbol: Optional[str] = None
    quarter: Optional[str] = None
    source_used: Optional[Literal["BSE", "SCREENER", "NSE"]] = None
    local_path: Optional[str] = None
    checksum: Optional[str] = None
    filing_date: Optional[str] = None


class UnifiedDocument(BaseModel):
    """Unified document representation for multi-source ingestion (BSE, Screener, NSE)."""
    symbol: str
    quarter: str = ""  # e.g., "Q1 FY26", "Jun 2024"
    title: str
    url: str
    source_used: Literal["BSE", "SCREENER", "NSE"] = "BSE"
    category: Literal[
        "transcript", "presentation", "financial_results",
        "credit_rating", "annual_report", "other"
    ] = "other"
    local_path: Optional[str] = None
    checksum: Optional[str] = None
    filing_date: Optional[str] = None
    bse_scrip_code: Optional[str] = None
    file_size_bytes: int = 0
    extraction_status: Literal["pending", "success", "failed"] = "pending"
    date_hint: Optional[str] = None


class CorporateAction(BaseModel):
    """A corporate action event (dividend, split, bonus)."""
    date: datetime
    action_type: str  # "Dividend", "Stock Split", "Bonus"
    value: float = 0.0
    details: str = ""

