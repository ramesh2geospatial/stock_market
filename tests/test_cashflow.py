import pandas as pd
import pytest
from analyzers.cashflow_analyzer import CashflowAnalyzer
from models.cashflow import CashFlowPeriod, CashFlowAnalysisResult
from models.stock import QuarterlyResult


def test_cashflow_analyzer_empty():
    analyzer = CashflowAnalyzer()
    res = analyzer.analyze(pd.DataFrame(), pd.DataFrame(), quarterly_results=[], symbol="TEST")
    assert isinstance(res, CashFlowAnalysisResult)
    assert len(res.annual_data) == 0
    assert len(res.quarterly_bs_data) == 0
    assert res.cash_quality_score == 50.0  # default starting score


def test_cashflow_analyzer_basic():
    analyzer = CashflowAnalyzer()

    # Setup mock cashflow df
    cf_data = {
        "Cash Flow Metric": [
            "Cash from Operating Activity",
            "Cash from Investing Activity",
            "Cash from Financing Activity",
            "Net Cash Flow"
        ],
        "Mar 2023": [100.0, -80.0, -10.0, 10.0],
        "Mar 2024": [150.0, -100.0, -20.0, 30.0]
    }
    cf_df = pd.DataFrame(cf_data)

    # Setup mock balance sheet df
    bs_data = {
        "Balance Sheet Metric": [
            "Trade Receivables",
            "Trade Payables",
            "Inventories",
            "Borrowings"
        ],
        "Mar 2023": [20.0, 15.0, 30.0, 50.0],
        "Mar 2024": [25.0, 18.0, 35.0, 45.0]
    }
    bs_df = pd.DataFrame(bs_data)

    # Setup mock quarterly results (P&L context)
    q_results = [
        QuarterlyResult(quarter="Jun 2023", revenue=100.0, net_profit=15.0, expenses=80.0),
        QuarterlyResult(quarter="Sep 2023", revenue=120.0, net_profit=20.0, expenses=90.0)
    ]

    res = analyzer.analyze(cf_df, bs_df, quarterly_results=q_results, symbol="TEST")

    assert len(res.annual_data) == 2
    p1 = res.annual_data[0]
    assert p1.period == "Mar 2023"
    assert p1.cfo == 100.0
    assert p1.trade_receivables == 20.0

    p2 = res.annual_data[1]
    assert p2.period == "Mar 2024"
    assert p2.cfo == 150.0
    assert p2.trade_receivables == 25.0

    # Quarterly BS base populated
    assert len(res.quarterly_bs_data) == 2
    assert res.quarterly_bs_data[0].period == "Jun 2023"


def test_cashflow_quarterly_enrichment_from_yfinance():
    analyzer = CashflowAnalyzer()

    # Raw tables are empty for simplicity, we just want to test quarterly yfinance match
    cf_df = pd.DataFrame()
    bs_df = pd.DataFrame()

    q_results = [
        QuarterlyResult(quarter="Sep 2025", revenue=1000.0, net_profit=150.0, expenses=800.0),
        QuarterlyResult(quarter="Mar 2026", revenue=1200.0, net_profit=180.0, expenses=900.0)
    ]

    # Mock yfinance quarterly balance sheet
    # Row labels, and date columns. YFinance returns absolute values (scaled by 1e7)
    qbs_data = {
        "index": ["Accounts Receivable", "Accounts Payable", "Inventory", "Total Debt", "Cash And Cash Equivalents"],
        "2025-09-30": [200.0 * 1e7, 150.0 * 1e7, 300.0 * 1e7, 500.0 * 1e7, 100.0 * 1e7],
        "2026-03-31": [250.0 * 1e7, 180.0 * 1e7, 350.0 * 1e7, 450.0 * 1e7, 120.0 * 1e7]
    }
    qbs_df = pd.DataFrame(qbs_data)

    yf_financials = {
        "quarterly_balance_sheet": qbs_df
    }

    res = analyzer.analyze(cf_df, bs_df, quarterly_results=q_results, symbol="TEST", yf_financials=yf_financials)

    # Quarterly BS should have yfinance values scaled by 1e7
    assert len(res.quarterly_bs_data) == 2
    
    q1 = res.quarterly_bs_data[0]
    assert q1.period == "Sep 2025"
    assert q1.trade_receivables == 200.0
    assert q1.trade_payables == 150.0
    assert q1.inventory == 300.0

    q2 = res.quarterly_bs_data[1]
    assert q2.period == "Mar 2026"
    assert q2.trade_receivables == 250.0
    assert q2.trade_payables == 180.0
    assert q2.inventory == 350.0
