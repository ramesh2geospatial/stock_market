import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional

from etl.amfi_nav_fetcher import AMFINAVFetcher
from etl.amc_holdings_scraper import AMCHoldingsEngine
from etl.mf_buying_selling_engine import MFBuyingSellingEngine
from etl.market_cap_engine import MarketCapEngine

app = FastAPI(
    title="Indian Mutual Fund Activity & Market Cap Holdings API",
    description="Legal open-data API tracking what Indian Mutual Funds are buying, selling, and holding across Large, Mid, Small, and Micro Cap stocks.",
    version="2.5.0"
)

fetcher = AMFINAVFetcher()

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Mutual Fund Activity & Market Cap Holdings API",
        "legal_notice": "Data aggregated from statutory AMC monthly disclosures & AMFI official open feeds."
    }

# ----------------------------
# Market Cap Tiered Stock Explorer
# ----------------------------

@app.get("/api/v1/stocks/market-cap-tier")
def get_stocks_by_market_cap_tier(tier: str = Query("large", description="Market cap tier: 'large', 'mid', 'small', 'micro'")):
    """Get stocks categorized by market capitalization tier with MF ownership stats."""
    stocks = MarketCapEngine.get_stocks_by_tier(tier)
    return {
        "tier": tier.lower(),
        "count": len(stocks),
        "stocks": stocks
    }

@app.get("/api/v1/stocks/{stock_isin}/mf-holdings")
def get_stock_mf_holdings_detail(stock_isin: str):
    """Get detailed mutual fund schemes holding matrix for a specific stock ISIN."""
    detail = MarketCapEngine.get_stock_mf_holdings(stock_isin)
    if not detail:
        raise HTTPException(status_code=404, detail="Stock ISIN not found in market cap database")
    return detail

# ----------------------------
# MF Buying & Selling Discovery
# ----------------------------

@app.get("/api/v1/mf/buying-trends")
def get_industry_buying_trends():
    """Get top stocks most bought by Indian Mutual Funds this month."""
    return {
        "period": MFBuyingSellingEngine.get_latest_reporting_period(),
        "top_bought_stocks": MFBuyingSellingEngine.get_industry_buying_trends()
    }

@app.get("/api/v1/mf/selling-trends")
def get_industry_selling_trends():
    """Get top stocks most sold by Indian Mutual Funds this month."""
    return {
        "period": MFBuyingSellingEngine.get_latest_reporting_period(),
        "top_sold_stocks": MFBuyingSellingEngine.get_industry_selling_trends()
    }

@app.get("/api/v1/mf/fresh-entries")
def get_fresh_entries():
    """Get new stocks added to mutual fund schemes this month (0 -> >0)."""
    return {
        "period": MFBuyingSellingEngine.get_latest_reporting_period(),
        "fresh_additions": MFBuyingSellingEngine.get_fresh_entries()
    }

@app.get("/api/v1/mf/exits")
def get_complete_exits():
    """Get stocks completely dumped by mutual fund schemes this month."""
    return {
        "period": MFBuyingSellingEngine.get_latest_reporting_period(),
        "complete_exits": MFBuyingSellingEngine.get_complete_exits()
    }

@app.get("/api/v1/mf/stock-ownership")
def get_stock_mf_ownership(stock: str = Query(..., min_length=2, description="Stock name e.g. Zomato, HDFC Bank")):
    """Reverse lookup: Find all mutual funds holding and trading a specific stock."""
    return MFBuyingSellingEngine.search_stock_mf_ownership(stock)

@app.get("/api/v1/mf/scheme-mom-diff/{scheme_code}")
def get_scheme_mom_diff(scheme_code: str):
    """Get Month-over-Month (MoM) buy/sell changes for a specific scheme."""
    return MFBuyingSellingEngine.get_scheme_mom_diff(scheme_code)

# ----------------------------
# Scheme Master & Holdings
# ----------------------------

@app.get("/api/v1/schemes")
def list_schemes(amc: Optional[str] = Query(None, description="Optional AMC name filter")):
    """List all tracked mutual fund schemes with their categories and AUM."""
    try:
        from storage.sqlite_store import SQLiteStore
        store = SQLiteStore()
        schemes = store.get_mf_schemes_cache(amc_name=amc)
        return {
            "count": len(schemes),
            "schemes": schemes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/schemes/search")
def search_schemes(q: str = Query(..., min_length=2, description="Search term for fund name or AMC")):
    """Search scheme names from institutional database and live AMFI open-data feed."""
    q_lower = q.lower().strip()
    results = []
    seen_names = set()

    # 1. First priority: Search local institutional schemes (which have holdings data)
    try:
        from storage.sqlite_store import SQLiteStore
        store = SQLiteStore()
        local_schemes = store.get_mf_schemes_cache()
        for s in local_schemes:
            s_name = s.get("scheme_name", "")
            amc_name = s.get("amc_name", "")
            if q_lower in s_name.lower() or q_lower in amc_name.lower():
                results.append({
                    "scheme_code": str(s.get("scheme_id")),
                    "scheme_name": s_name,
                    "amc": amc_name,
                    "category": s.get("category", "Equity"),
                    "aum_cr": s.get("aum_cr", 0.0),
                    "source": "INSTITUTIONAL_CACHE",
                    "has_holdings": True
                })
                seen_names.add(s_name.lower())
    except Exception as e:
        logger.debug(f"Local schemes search error: {e}")

    # 2. Second priority: Search AMFI daily feed for universe discovery
    try:
        nav_data = fetcher.fetch_amfi_daily_nav()
        if nav_data:
            for item in nav_data:
                s_name = item.get("scheme_name", "")
                amc_name = item.get("amc", "")
                if (q_lower in s_name.lower() or q_lower in amc_name.lower()) and s_name.lower() not in seen_names:
                    results.append({
                        "scheme_code": item.get("scheme_code"),
                        "scheme_name": s_name,
                        "amc": amc_name,
                        "nav": item.get("nav", 0.0),
                        "date": item.get("date", ""),
                        "source": "AMFI_LIVE_FEED",
                        "has_holdings": False
                    })
                    seen_names.add(s_name.lower())
                if len(results) >= 50:
                    break
    except Exception as e:
        logger.debug(f"AMFI search error: {e}")

    return {
        "query": q,
        "count": len(results),
        "results": results[:30]
    }

@app.get("/api/v1/schemes/{scheme_code}/holdings")
def get_scheme_holdings(scheme_code: str):
    """Get underlying stock & sector holdings for a scheme."""
    holdings = AMCHoldingsEngine.get_holdings(scheme_code)
    if not holdings.get("holdings"):
        raise HTTPException(status_code=404, detail="Holdings data not available for this scheme")
    return holdings

@app.get("/api/v1/analytics/overlap")
def get_fund_overlap(fund_a: str, fund_b: str):
    """Calculate common stock exposure & overlap % between two schemes."""
    return AMCHoldingsEngine.calculate_portfolio_overlap(fund_a, fund_b)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
