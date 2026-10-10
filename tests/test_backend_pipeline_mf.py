"""
Unit tests for backend_pipeline MF analytics and API endpoints.
Verifies live and fallback operations for AMCHoldingsEngine, MFBuyingSellingEngine, and FastAPI routes.
"""
from fastapi.testclient import TestClient
import pytest

from backend_pipeline.api.main import app
from backend_pipeline.etl.amc_holdings_scraper import AMCHoldingsEngine
from backend_pipeline.etl.mf_buying_selling_engine import MFBuyingSellingEngine

client = TestClient(app)


def test_amc_holdings_engine_lookup():
    # Lookup live scheme from SQLite
    res_live = AMCHoldingsEngine.get_holdings("111")
    assert res_live["scheme_name"] != ""
    assert len(res_live["holdings"]) > 0

    # Lookup fallback sample scheme
    res_sample = AMCHoldingsEngine.get_holdings("122639")
    assert "Parag Parikh" in res_sample["scheme_name"]
    assert len(res_sample["holdings"]) >= 8


def test_amc_portfolio_overlap():
    res = AMCHoldingsEngine.calculate_portfolio_overlap("122639", "119063")
    assert res["overlap_pct"] > 0.0
    assert res["common_stock_count"] > 0
    assert "common_stocks" in res


def test_mf_buying_selling_engine():
    period = MFBuyingSellingEngine.get_latest_reporting_period()
    assert period != ""

    buying = MFBuyingSellingEngine.get_industry_buying_trends()
    assert len(buying) > 0
    assert "stock_name" in buying[0]

    selling = MFBuyingSellingEngine.get_industry_selling_trends()
    assert len(selling) > 0

    fresh = MFBuyingSellingEngine.get_fresh_entries()
    assert len(fresh) > 0

    ownership = MFBuyingSellingEngine.search_stock_mf_ownership("RELIANCE")
    assert ownership["funds_holding_count"] > 0


def test_api_mf_routes():
    res_buy = client.get("/api/v1/mf/buying-trends")
    assert res_buy.status_code == 200
    assert "period" in res_buy.json()
    assert len(res_buy.json()["top_bought_stocks"]) > 0

    res_sell = client.get("/api/v1/mf/selling-trends")
    assert res_sell.status_code == 200
    assert len(res_sell.json()["top_sold_stocks"]) > 0

    res_fresh = client.get("/api/v1/mf/fresh-entries")
    assert res_fresh.status_code == 200
    assert len(res_fresh.json()["fresh_additions"]) > 0

    res_exits = client.get("/api/v1/mf/exits")
    assert res_exits.status_code == 200

    res_overlap = client.get("/api/v1/analytics/overlap?fund_a=122639&fund_b=119063")
    assert res_overlap.status_code == 200
    assert res_overlap.json()["overlap_pct"] > 0

    res_schemes = client.get("/api/v1/schemes")
    assert res_schemes.status_code == 200
    assert res_schemes.json()["count"] > 0

    res_search = client.get("/api/v1/schemes/search?q=SBI")
    assert res_search.status_code == 200
    assert res_search.json()["count"] > 0
    assert len(res_search.json()["results"]) > 0

    res_holdings_102 = client.get("/api/v1/schemes/102/holdings")
    assert res_holdings_102.status_code == 200
    assert "SBI Bluechip" in res_holdings_102.json()["scheme_name"]
    assert res_holdings_102.json()["holdings_count"] >= 14
