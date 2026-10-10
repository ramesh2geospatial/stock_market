import urllib.request
import urllib.error
import json
from collections import Counter

SUPABASE_URL = 'https://nbyzclczjoxaemcckxne.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5ieXpjbGN6am94YWVtY2NreG5lIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkyNTM5NDEsImV4cCI6MjA4NDgyOTk0MX0.p3KZFSndnHvphx3iu7BmIMFCz-Y6SGes0_do_W8Ym5g'

headers = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'count=exact'
}

def get_data(endpoint):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            cr = resp.headers.get('Content-Range', '')
            data = json.loads(resp.read().decode('utf-8'))
            return data, cr
    except Exception as e:
        return [], str(e)

def main():
    print("=" * 70)
    print("           [AUDIT REPORT] LIVE SUPABASE DATABASE & EDGE AUDIT")
    print("=" * 70)

    # 1. Audit Holdings
    holdings, h_cr = get_data("mf_stock_holdings?select=symbol,shares_held,market_value_cr,portfolio_weight_pct,mom_share_change,action_type,as_of_date,created_at&order=as_of_date.desc,market_value_cr.desc&limit=100")
    total_h = h_cr.split("/")[-1] if "/" in h_cr else len(holdings)
    print(f"\n1. [HOLDINGS] MF Stock Holdings (Total Records in Cloud: {total_h})")
    print("-" * 55)
    dates = Counter(h.get('as_of_date') for h in holdings)
    actions = Counter(h.get('action_type') for h in holdings)
    stocks = Counter(h.get('symbol') for h in holdings)

    print(f"  * Reporting Dates in Cloud: {dict(dates)}")
    print(f"  * Action Distribution: {dict(actions)}")
    print(f"  * Most Active Stocks Tracked: {dict(stocks.most_common(8))}")
    print("\n  Top 5 High-Value Institutional Holdings:")
    for h in holdings[:5]:
        val = h.get('market_value_cr', 0)
        shs = h.get('shares_held', 0)
        print(f"    - {h.get('symbol')}: Rs {val:,.1f} Cr | {shs:,} shares | Action: {h.get('action_type')} | Date: {h.get('as_of_date')}")

    # 2. Audit Index Stocks
    stocks_list, s_cr = get_data("index_stocks?select=symbol,company_name,index_name,market_cap_tier,market_cap_cr&order=market_cap_cr.desc&limit=10")
    total_s = s_cr.split("/")[-1] if "/" in s_cr else len(stocks_list)
    all_stocks, _ = get_data("index_stocks?select=market_cap_tier&limit=1000")
    tiers = Counter(s.get('market_cap_tier', 'UNKNOWN') for s in all_stocks)

    print(f"\n2. [INDEX STOCKS] Index Stocks Catalog (Total Equities Indexed: {total_s})")
    print("-" * 55)
    print(f"  * Market Cap Tier Breakdown: {dict(tiers)}")
    print("  * Top 5 Equities by Market Cap:")
    for s in stocks_list[:5]:
        mcap = s.get('market_cap_cr', 0) or 0
        print(f"    - {s.get('symbol')} ({s.get('company_name')}): Rs {mcap:,.1f} Cr | {s.get('market_cap_tier')}")

    # 3. Audit Schemes
    schemes, sc_cr = get_data("mf_schemes?select=scheme_id,scheme_name,amc_name,category,aum_cr&order=aum_cr.desc&limit=5")
    total_sc = sc_cr.split("/")[-1] if "/" in sc_cr else len(schemes)
    print(f"\n3. [SCHEMES] Mutual Fund Schemes (Total Registered Schemes: {total_sc})")
    print("-" * 55)
    print("  * Top 5 Largest Schemes by AUM:")
    for sc in schemes[:5]:
        aum = sc.get('aum_cr', 0) or 0
        print(f"    - {sc.get('scheme_name')} ({sc.get('amc_name')}): Rs {aum:,.1f} Cr | {sc.get('category')}")

    # 4. Audit Predictions
    preds, _ = get_data("stock_predictions?select=*")
    print(f"\n4. [PREDICTIONS] 10-Signal Predictions (Total Records: {len(preds)})")
    print("-" * 55)
    for p in preds:
        print(f"    - {p.get('symbol')}: Score: {p.get('trajectory_score')} | Stance: {p.get('stance')} | Bear/Base/Bull: Rs {p.get('target_bear')}/Rs {p.get('target_base')}/Rs {p.get('target_bull')}")

    # 5. Audit Financials
    fins, _ = get_data("stock_financials?select=*")
    print(f"\n5. [FINANCIALS] Financial Statements (Total Records: {len(fins)})")
    print("-" * 55)
    for f in fins:
        print(f"    - {f.get('symbol')} ({f.get('period')}): Rev: Rs {f.get('revenue_cr')} Cr | PAT: Rs {f.get('pat_cr')} Cr | YoY Growth: {f.get('revenue_growth_yoy')}%")

    # 6. Audit Edge Function
    print("\n6. [EDGE FUNCTION] Supabase Serverless Edge Function Status")
    print("-" * 55)
    ef_url = f"{SUPABASE_URL}/functions/v1/fetch-mf-holdings"
    ef_req = urllib.request.Request(
        ef_url,
        data=json.dumps({"symbol": "RELIANCE.NS"}).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(ef_req, timeout=10) as resp:
            print(f"  * Edge Endpoint: {ef_url}")
            print(f"  * Status: HTTP {resp.status} (Deployed & Active)")
            res_body = json.loads(resp.read().decode('utf-8'))
            print(f"  * Live Execution Response: {json.dumps(res_body, indent=4)[:300]}...")
    except urllib.error.HTTPError as e:
        print(f"  * Edge Endpoint: {ef_url}")
        print(f"  * Status: HTTP {e.code} ({e.reason})")
        print("  * Note: Edge Function code is authored in `supabase/functions/fetch-mf-holdings/index.ts` ready for deployment via Supabase CLI.")
    except Exception as e:
        print(f"  * Edge Endpoint Error: {e}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
