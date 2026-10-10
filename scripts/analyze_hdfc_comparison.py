import json
from collections import Counter

def clean_str(s):
    if not isinstance(s, str):
        s = str(s)
    return s.replace('\u20b9', 'Rs ').replace('\u2022', '*').encode('ascii', errors='replace').decode('ascii')

def main():
    with open('scripts/hdfc_reconciliation_raw.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("=" * 80)
    print("        HDFC BANK (HDFCBANK.NS / 500180) MULTI-SOURCE RECONCILIATION AUDIT")
    print("=" * 80)

    # 1. Exchange & Regulatory Metrics
    live = data.get('live_exchange_screener', {})
    metrics = live.get('metrics', {})
    shareholding = live.get('shareholding', {})
    dii_funds = live.get('quarterly_dii', {})

    print("\n--- 1. NSE / BSE OFFICIAL EXCHANGE DISCLOSURES ---")
    print(f"  Market Cap (Live): {clean_str(metrics.get('Market Cap', 'Rs 12.5L Cr'))}")
    print(f"  Current Price: {clean_str(metrics.get('Current Price', 'N/A'))}")
    print(f"  P/E Ratio: {clean_str(metrics.get('Stock P/E', 'N/A'))}")
    print(f"  Book Value: {clean_str(metrics.get('Book Value', 'N/A'))}")
    print(f"  ROCE / ROE: {clean_str(metrics.get('ROCE', 'N/A'))} / {clean_str(metrics.get('ROE', 'N/A'))}")

    print("\n  Shareholding Pattern Breakdown (LODR Reg 31):")
    for category, quarters in shareholding.items():
        latest_q = list(quarters.keys())[-1] if quarters else 'N/A'
        latest_val = quarters.get(latest_q, 'N/A') if quarters else 'N/A'
        prev_q = list(quarters.keys())[-2] if len(quarters) >= 2 else 'N/A'
        prev_val = quarters.get(prev_q, 'N/A') if len(quarters) >= 2 else 'N/A'
        print(f"    * {clean_str(category):<15}: {clean_str(latest_val)} (as of {clean_str(latest_q)}) | Prev: {clean_str(prev_val)} ({clean_str(prev_q)})")

    print(f"\n  Institutional Domestic Schemes in Regulatory Filings: {len(dii_funds)} distinct entities")
    print("  Top 10 Reg 31 Disclosed Domestic Institutional Holders:")
    for fname, qdict in list(dii_funds.items())[:10]:
        quarters = [q for q in qdict.keys() if q != 'setAttributes']
        latest_q = quarters[-1] if quarters else 'N/A'
        pct = qdict.get(latest_q, 'N/A')
        print(f"    - {clean_str(fname):<45}: {clean_str(pct)} ({clean_str(latest_q)})")

    # 2. Supabase Cloud Database Audit
    sb = data.get('supabase', {})
    sb_stock = sb.get('index_stocks', [])
    sb_holdings = sb.get('mf_holdings', [])
    sb_fins = sb.get('financials', [])
    sb_preds = sb.get('predictions', [])

    print("\n--- 2. SUPABASE CLOUD DATABASE (PostgreSQL) ---")
    if sb_stock and isinstance(sb_stock, list):
        st = sb_stock[0]
        print(f"  Master Record: Symbol={st.get('symbol')} | Name={st.get('company_name')} | Tier={st.get('market_cap_tier')} | Mcap=Rs {st.get('market_cap_cr')} Cr")
    
    print(f"  Holdings Records Stored: {len(sb_holdings)} rows")
    total_sb_val = sum(float(h.get('market_value_cr', 0)) for h in sb_holdings)
    total_sb_shares = sum(int(h.get('shares_held', 0)) for h in sb_holdings)
    print(f"  Total Stored MF Holding Value: Rs {total_sb_val:,.1f} Cr")
    print(f"  Total Stored MF Shares: {total_sb_shares:,} shares")

    print("\n  Top 5 Schemes in Supabase:")
    for h in sb_holdings[:5]:
        sch = h.get('mf_schemes') or {}
        sname = sch.get('scheme_name') or f"Scheme ID {h.get('scheme_id')}"
        amc = sch.get('amc_name') or 'N/A'
        print(f"    - {clean_str(sname):<35} ({clean_str(amc):<18}): Rs {float(h.get('market_value_cr', 0)):,.1f} Cr | {int(h.get('shares_held', 0)):,} shs | Wt: {h.get('portfolio_weight_pct')}% | Action: {h.get('action_type')}")

    # 3. Local SQLite & App Engine
    sqlite = data.get('sqlite_local', {})
    app = data.get('app_fallbacks', {})

    print("\n--- 3. APP & LOCAL CACHE ENGINE ---")
    print(f"  Local SQLite Cached Rows: {len(sqlite.get('mf_holdings_cache', []))}")
    print(f"  App Fallback Mcap: Rs {app.get('flutter_fallback_market_cap_cr'):,.1f} Cr")
    print(f"  App Fallback MF Ownership: {app.get('flutter_fallback_mf_ownership_pct')}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
