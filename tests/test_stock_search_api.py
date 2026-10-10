"""
Unit tests for Stock Search API & Mutual Fund Holdings Provider.
"""
import pytest
import os
import tempfile
from providers.mf_holdings_provider import MFHoldingsProvider
from stock_analyzer import StockAnalyzer


@pytest.fixture
def test_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    yield db_path
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_mf_holdings_provider_search(test_db):
    provider = MFHoldingsProvider(db_path=test_db)
    
    # 1. Search Large Cap
    res_large = provider.search_stocks(query="Reliance", tier="LARGE_CAP")
    assert len(res_large) > 0
    assert res_large[0]["symbol"] == "RELIANCE.NS"
    assert res_large[0]["tier"] == "LARGE_CAP"

    # 2. Search Mid Cap
    res_mid = provider.search_stocks(query="Polycab", tier="MID_CAP")
    assert len(res_mid) > 0
    assert res_mid[0]["symbol"] == "POLYCAB.NS"

    # 3. Search Small Cap
    res_small = provider.search_stocks(query="BSE", tier="SMALL_CAP")
    assert len(res_small) > 0
    assert res_small[0]["symbol"] == "BSE.NS"


def test_mf_holdings_breakdown(test_db):
    provider = MFHoldingsProvider(db_path=test_db)
    
    ownership = provider.get_stock_mf_ownership("RELIANCE.NS")
    assert "stock_info" in ownership
    assert ownership["stock_info"]["symbol"] == "RELIANCE.NS"
    assert "summary" in ownership
    assert ownership["summary"]["total_mf_schemes_holding"] > 0
    assert len(ownership["holdings_matrix"]) > 0


def test_stock_analyzer_integration(test_db):
    analyzer = StockAnalyzer()
    analyzer.mf_holdings_provider = MFHoldingsProvider(db_path=test_db)
    
    search_res = analyzer.search_stocks(query="HDFC")
    assert len(search_res) > 0
    
    tier_res = analyzer.get_market_cap_tier_stocks("SMALL_CAP")
    assert len(tier_res) > 0
