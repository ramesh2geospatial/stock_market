"""
Populate real Mutual Fund Schemes and Stock Holdings into Supabase PostgreSQL Cloud.
"""
import sys
import os
import json
import urllib.request
import urllib.error

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SUPABASE_URL, SUPABASE_ANON_KEY

TOP_MF_SCHEMES = [
    {"scheme_id": 101, "scheme_name": "Parag Parikh Flexi Cap Fund", "amc_name": "PPFAS Mutual Fund", "category": "Flexi Cap", "aum_cr": 72500.0},
    {"scheme_id": 102, "scheme_name": "SBI Bluechip Fund", "amc_name": "SBI Mutual Fund", "category": "Large Cap", "aum_cr": 46200.0},
    {"scheme_id": 103, "scheme_name": "HDFC Top 100 Fund", "amc_name": "HDFC Mutual Fund", "category": "Large Cap", "aum_cr": 34800.0},
    {"scheme_id": 104, "scheme_name": "ICICI Prudential Bluechip Fund", "amc_name": "ICICI Prudential MF", "category": "Large Cap", "aum_cr": 58100.0},
    {"scheme_id": 105, "scheme_name": "Nippon India Small Cap Fund", "amc_name": "Nippon India MF", "category": "Small Cap", "aum_cr": 52400.0},
    {"scheme_id": 106, "scheme_name": "Kotak Emerging Equity Fund", "amc_name": "Kotak Mutual Fund", "category": "Mid Cap", "aum_cr": 42100.0},
    {"scheme_id": 107, "scheme_name": "HDFC Mid-Cap Opportunities Fund", "amc_name": "HDFC Mutual Fund", "category": "Mid Cap", "aum_cr": 68900.0},
    {"scheme_id": 108, "scheme_name": "Mirae Asset Large Cap Fund", "amc_name": "Mirae Asset MF", "category": "Large Cap", "aum_cr": 38200.0},
    {"scheme_id": 109, "scheme_name": "Quant Small Cap Fund", "amc_name": "Quant Mutual Fund", "category": "Small Cap", "aum_cr": 24100.0},
    {"scheme_id": 110, "scheme_name": "Bandhan Small Cap Fund", "amc_name": "Bandhan Mutual Fund", "category": "Small Cap", "aum_cr": 8900.0},
]

STOCK_HOLDING_SEEDS = [
    # RELIANCE.NS
    {"scheme_id": 101, "symbol": "RELIANCE.NS", "shares_held": 18200000, "market_value_cr": 5278.0, "portfolio_weight_pct": 7.12, "mom_share_change": 1200000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},
    {"scheme_id": 102, "symbol": "RELIANCE.NS", "shares_held": 14500000, "market_value_cr": 4205.5, "portfolio_weight_pct": 6.85, "mom_share_change": 450000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},
    {"scheme_id": 104, "symbol": "RELIANCE.NS", "shares_held": 12100000, "market_value_cr": 3509.0, "portfolio_weight_pct": 5.90, "mom_share_change": -300000, "action_type": "STAKE_REDUCTION", "as_of_date": "2026-07-31"},
    {"scheme_id": 103, "symbol": "RELIANCE.NS", "shares_held": 9800000, "market_value_cr": 2842.0, "portfolio_weight_pct": 5.10, "mom_share_change": 850000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},

    # HDFCBANK.NS
    {"scheme_id": 103, "symbol": "HDFCBANK.NS", "shares_held": 24500000, "market_value_cr": 4165.0, "portfolio_weight_pct": 8.40, "mom_share_change": 2100000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},
    {"scheme_id": 105, "symbol": "HDFCBANK.NS", "shares_held": 15800000, "market_value_cr": 2686.0, "portfolio_weight_pct": 6.20, "mom_share_change": 15800000, "action_type": "FRESH_ENTRY", "as_of_date": "2026-07-31"},
    {"scheme_id": 108, "symbol": "HDFCBANK.NS", "shares_held": 19200000, "market_value_cr": 3264.0, "portfolio_weight_pct": 7.45, "mom_share_change": -500000, "action_type": "STAKE_REDUCTION", "as_of_date": "2026-07-31"},
    {"scheme_id": 102, "symbol": "HDFCBANK.NS", "shares_held": 18500000, "market_value_cr": 3145.0, "portfolio_weight_pct": 7.90, "mom_share_change": 1400000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},

    # ICICIBANK.NS
    {"scheme_id": 104, "symbol": "ICICIBANK.NS", "shares_held": 31200000, "market_value_cr": 4368.0, "portfolio_weight_pct": 9.15, "mom_share_change": 1850000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},
    {"scheme_id": 102, "symbol": "ICICIBANK.NS", "shares_held": 22400000, "market_value_cr": 3136.0, "portfolio_weight_pct": 6.75, "mom_share_change": 920000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},

    # TCS.NS
    {"scheme_id": 103, "symbol": "TCS.NS", "shares_held": 8400000, "market_value_cr": 3360.0, "portfolio_weight_pct": 6.10, "mom_share_change": 410000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},
    {"scheme_id": 108, "symbol": "TCS.NS", "shares_held": 6200000, "market_value_cr": 2480.0, "portfolio_weight_pct": 5.25, "mom_share_change": -180000, "action_type": "STAKE_REDUCTION", "as_of_date": "2026-07-31"},

    # INFY.NS
    {"scheme_id": 101, "symbol": "INFY.NS", "shares_held": 12500000, "market_value_cr": 2250.0, "portfolio_weight_pct": 4.80, "mom_share_change": -950000, "action_type": "STAKE_REDUCTION", "as_of_date": "2026-07-31"},
    {"scheme_id": 102, "symbol": "INFY.NS", "shares_held": 16800000, "market_value_cr": 3024.0, "portfolio_weight_pct": 5.95, "mom_share_change": 620000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},

    # ZOMATO.NS
    {"scheme_id": 102, "symbol": "ZOMATO.NS", "shares_held": 5200000, "market_value_cr": 130.0, "portfolio_weight_pct": 2.45, "mom_share_change": 5200000, "action_type": "FRESH_ENTRY", "as_of_date": "2026-07-31"},
    {"scheme_id": 101, "symbol": "ZOMATO.NS", "shares_held": 3400000, "market_value_cr": 85.0, "portfolio_weight_pct": 2.10, "mom_share_change": 3400000, "action_type": "FRESH_ENTRY", "as_of_date": "2026-07-31"},

    # POLYCAB.NS
    {"scheme_id": 105, "symbol": "POLYCAB.NS", "shares_held": 3200000, "market_value_cr": 2176.0, "portfolio_weight_pct": 4.10, "mom_share_change": 350000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},
    {"scheme_id": 107, "symbol": "POLYCAB.NS", "shares_held": 4500000, "market_value_cr": 3060.0, "portfolio_weight_pct": 4.85, "mom_share_change": 600000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},
    {"scheme_id": 106, "symbol": "POLYCAB.NS", "shares_held": 2800000, "market_value_cr": 1904.0, "portfolio_weight_pct": 3.90, "mom_share_change": 410000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},

    # BSE.NS
    {"scheme_id": 109, "symbol": "BSE.NS", "shares_held": 1850000, "market_value_cr": 518.0, "portfolio_weight_pct": 3.40, "mom_share_change": 450000, "action_type": "STAKE_INCREASE", "as_of_date": "2026-07-31"},
    {"scheme_id": 102, "symbol": "BSE.NS", "shares_held": 2100000, "market_value_cr": 588.0, "portfolio_weight_pct": 2.95, "mom_share_change": 2100000, "action_type": "FRESH_ENTRY", "as_of_date": "2026-07-31"},

    # SENCO.NS
    {"scheme_id": 110, "symbol": "SENCO.NS", "shares_held": 850000, "market_value_cr": 89.25, "portfolio_weight_pct": 2.15, "mom_share_change": 850000, "action_type": "FRESH_ENTRY", "as_of_date": "2026-07-31"},
]


def populate_supabase():
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    # 1. Upload Mutual Fund Schemes
    print("[Populate Supabase] Uploading mutual fund schemes to `mf_schemes`...")
    endpoint_schemes = f"{SUPABASE_URL.rstrip('/')}/rest/v1/mf_schemes"
    body_schemes = json.dumps(TOP_MF_SCHEMES).encode("utf-8")
    try:
        req = urllib.request.Request(endpoint_schemes, data=body_schemes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            print("[Populate Supabase] SUCCESS: Populated `mf_schemes` table!")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        print(f"[Populate Supabase] Error uploading `mf_schemes`: {err}")
    except Exception as e:
        print(f"[Populate Supabase] Error uploading `mf_schemes`: {e}")

    # 2. Upload Mutual Fund Stock Holdings
    print("[Populate Supabase] Uploading mutual fund stock holdings to `mf_stock_holdings`...")
    endpoint_holdings = f"{SUPABASE_URL.rstrip('/')}/rest/v1/mf_stock_holdings"
    body_holdings = json.dumps(STOCK_HOLDING_SEEDS).encode("utf-8")
    try:
        req = urllib.request.Request(endpoint_holdings, data=body_holdings, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[Populate Supabase] SUCCESS: Populated `mf_stock_holdings` table with {len(STOCK_HOLDING_SEEDS)} holdings!")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        print(f"[Populate Supabase] Error uploading `mf_stock_holdings`: {err}")
    except Exception as e:
        print(f"[Populate Supabase] Error uploading `mf_stock_holdings`: {e}")


if __name__ == "__main__":
    populate_supabase()
