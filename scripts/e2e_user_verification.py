import sys
import os
sys.path.insert(0, os.path.abspath("."))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi.testclient import TestClient
import json

from backend_pipeline.api.main import app

client = TestClient(app)

def run_e2e_user_test():
    print("================================================================================")
    print("🚀 USER JOURNEY 1: SEARCH SCHEMES ACROSS MULTIPLE SOURCES")
    print("================================================================================")
    r1 = client.get("/api/v1/schemes/search?q=SBI")
    d1 = r1.json()
    print(f"Status Code: {r1.status_code} | Total Matching Schemes: {d1.get('count')}")
    print("Sample Search Results (Institutional Cache + AMFI Open Feed):")
    for item in d1.get("results", [])[:4]:
        print(f" - [{item.get('source')}] {item.get('scheme_name')} ({item.get('amc')}) | Has Holdings: {item.get('has_holdings')}")

    print("\n================================================================================")
    print("🚀 USER JOURNEY 2: VIEW ALL HOLDINGS FOR A SCHEME (SBI BLUECHIP FUND - ID 102)")
    print("================================================================================")
    r2 = client.get("/api/v1/schemes/102/holdings")
    d2 = r2.json()
    print(f"Status Code: {r2.status_code}")
    print(f"Scheme Name : {d2.get('scheme_name')} | AMC: {d2.get('amc')}")
    print(f"Category    : {d2.get('category')} | Total Holdings: {d2.get('holdings_count')}")
    print("\nAll Portfolio Holdings:")
    for i, h in enumerate(d2.get("holdings", []), 1):
        print(f"  {i:2d}. {h['stock_name']:<30} | {h['sector']:<22} | Weight: {h['weight_pct']:5.2f}% | Value: ₹{h['market_value_cr']:8.1f} Cr | Action: {h['action']}")

    print("\n================================================================================")
    print("🚀 USER JOURNEY 3: PORTFOLIO OVERLAP CALCULATOR (SBI BLUECHIP VS PARAG PARIKH)")
    print("================================================================================")
    r3 = client.get("/api/v1/analytics/overlap?fund_a=102&fund_b=101")
    d3 = r3.json()
    print(f"Status Code: {r3.status_code}")
    print(f"Fund A: {d3.get('fund_a')}")
    print(f"Fund B: {d3.get('fund_b')}")
    print(f"Portfolio Overlap: {d3.get('overlap_pct')}%")
    print(f"Common Stocks Count: {d3.get('common_stock_count')} stocks\n")
    print("Common Stock Breakdown:")
    for s in d3.get("common_stocks", []):
        print(f"  * {s['stock_name']:<28} | Weight in Fund A: {s['weight_in_fund_a']:5.2f}% | Weight in Fund B: {s['weight_in_fund_b']:5.2f}% | Overlap Contribution: {s['overlap_contribution']:5.2f}%")

    print("\n================================================================================")
    print("🚀 USER JOURNEY 4: REVERSE STOCK OWNERSHIP LOOKUP (RELIANCE)")
    print("================================================================================")
    r4 = client.get("/api/v1/mf/stock-ownership?stock=RELIANCE")
    d4 = r4.json()
    print(f"Status Code: {r4.status_code}")
    print(f"Target Stock: {d4.get('query_stock')} | Funds Holding Stock: {d4.get('funds_holding_count')}\n")
    print("Institutional Holder Breakdown:")
    for f in d4.get("funds", [])[:6]:
        print(f"  * {f['scheme_name']:<35} ({f['amc']:<20}) | Action: {f['action']:<10} | Shares Δ: {f['shares_change']:<14} | Weight: {f['weight_pct']}%")

    print("\n================================================================================")
    print("🚀 USER JOURNEY 5: SMART MONEY ACCUMULATION TRENDS (TOP BOUGHT STOCKS)")
    print("================================================================================")
    r5 = client.get("/api/v1/mf/buying-trends")
    d5 = r5.json()
    print(f"Status Code: {r5.status_code} | Period: {d5.get('period')}")
    print("Top Stocks Accumulated by Indian Mutual Funds:")
    for tb in d5.get("top_bought_stocks", [])[:5]:
        print(f"  * {tb['stock_name']:<18} | Net Shares Bought: {tb['net_shares_bought']:<18} | Funds Accumulating: {tb['buying_funds_count']:2d} | Value: ₹{tb.get('total_value_cr', 0.0):,.1f} Cr")

if __name__ == "__main__":
    run_e2e_user_test()
