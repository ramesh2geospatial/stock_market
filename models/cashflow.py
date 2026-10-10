"""
Pydantic data models for cashflow analysis.
Covers annual cash flow statements, quarterly balance sheet items,
and derived working capital / cash quality metrics.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal


class CashFlowPeriod(BaseModel):
    """Single period (annual or quarterly) of cashflow and working capital data."""
    period: str                          # "Mar 2024" or "FY24"
    period_type: Literal["annual", "quarterly"] = "annual"

    # --- P&L items ---
    revenue: float = 0.0
    net_profit: float = 0.0
    expenses: float = 0.0

    # --- Cash Flow Statement (annual) ---
    cfo: float = 0.0                     # Cash from Operating Activity
    cfi: float = 0.0                     # Cash from Investing Activity
    cff: float = 0.0                     # Cash from Financing Activity
    net_cash_flow: float = 0.0

    # --- Balance Sheet items ---
    trade_receivables: float = 0.0
    trade_payables: float = 0.0
    inventory: float = 0.0
    total_borrowings: float = 0.0
    cash_and_equivalents: float = 0.0

    # --- Derived metrics (computed by analyzer) ---
    cash_conversion_ratio: Optional[float] = None   # CFO / PAT
    free_cash_flow: Optional[float] = None           # CFO - CAPEX (|CFI| proxy)
    receivable_days: Optional[float] = None          # (Receivables / Revenue) * 365
    payable_days: Optional[float] = None             # (Payables / Expenses) * 365
    inventory_days: Optional[float] = None           # (Inventory / Revenue) * 365
    working_capital_days: Optional[float] = None     # Recv days + Inv days - Pay days
    receivable_growth_pct: Optional[float] = None    # YoY growth in receivables
    revenue_growth_pct: Optional[float] = None       # YoY growth in revenue
    cfo_growth_pct: Optional[float] = None           # YoY growth in CFO

    # --- Balance Sheet (Additional for Forensics) ---
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    retained_earnings: float = 0.0
    ebit: float = 0.0

    # --- Advanced / Forensic metrics ---
    altman_z_score: Optional[float] = None
    dupont_roe: Optional[float] = None
    dupont_npm: Optional[float] = None               # Net Profit Margin
    dupont_at: Optional[float] = None                # Asset Turnover
    dupont_fl: Optional[float] = None                # Financial Leverage
    fcf_margin: Optional[float] = None               # FCF / Revenue


class CashFlowDiagnostic(BaseModel):
    """A single diagnostic signal from cashflow analysis."""
    severity: Literal["red", "yellow", "green"] = "green"
    category: str = ""          # e.g., "Cash Conversion", "Credit Sales", "Working Capital"
    message: str = ""           # Human-readable insight
    metric_value: Optional[float] = None   # The numeric value triggering this signal


class CashFlowAnalysisResult(BaseModel):
    """Complete cashflow analysis output for a company."""
    symbol: str = ""
    annual_data: list[CashFlowPeriod] = Field(default_factory=list)
    quarterly_bs_data: list[CashFlowPeriod] = Field(default_factory=list)
    diagnostics: list[CashFlowDiagnostic] = Field(default_factory=list)
    cash_quality_score: float = 0.0   # 0-100 composite score
    summary: str = ""                  # One-liner summary of cash position
