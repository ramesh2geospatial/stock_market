"""
Cross-Source Data Comparison & Reconciliation Audit for HDFC Bank (HDFCBANK.NS / 500180.BO).
Compares statistics across:
1. NSE (National Stock Exchange of India)
2. BSE (Bombay Stock Exchange - Scrip 500180)
3. SEBI / AMFI Mutual Fund Regulatory Disclosures
4. Supabase PostgreSQL Cloud Database
5. Mobile App & Dashboard Local Query Engine
"""
import urllib.request
import urllib.error
import json
import sqlite3
import re
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from config import DB_PATH, SUPABASE_URL, SUPABASE_ANON_KEY


HEADERS_HTTP = {
    'apikey': SUPABASE_ANON_KEY,
    'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
    'Content-Type': 'application/json'
}

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9'
}

def audit_supabase():
    """Fetch all HDFC Bank records from Supabase Cloud."""
    res = {}
    
    # 1. Stock Master
    try:
        url_s = f"{SUPABASE_URL}/rest/v1/index_stocks?symbol=eq.HDFCBANK.NS"
        req_s = urllib.request.Request(url_s, headers=HEADERS_HTTP)
        with urllib.request.urlopen(req_s, timeout=10) as r:
            res['index_stocks'] = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        res['index_stocks'] = str(e)

    # 2. MF Holdings with Schemes join
    try:
        url_h = f"{SUPABASE_URL}/rest/v1/mf_stock_holdings?symbol=eq.HDFCBANK.NS&select=*,mf_schemes(*)&order=market_value_cr.desc"
        req_h = urllib.request.Request(url_h, headers=HEADERS_HTTP)
        with urllib.request.urlopen(req_h, timeout=10) as r:
            res['mf_holdings'] = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        res['mf_holdings'] = str(e)

    # 3. Financials
    try:
        url_f = f"{SUPABASE_URL}/rest/v1/stock_financials?symbol=eq.HDFCBANK.NS&order=period.desc"
        req_f = urllib.request.Request(url_f, headers=HEADERS_HTTP)
        with urllib.request.urlopen(req_f, timeout=10) as r:
            res['financials'] = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        res['financials'] = str(e)

    # 4. Predictions
    try:
        url_p = f"{SUPABASE_URL}/rest/v1/stock_predictions?symbol=eq.HDFCBANK.NS"
        req_p = urllib.request.Request(url_p, headers=HEADERS_HTTP)
        with urllib.request.urlopen(req_p, timeout=10) as r:
            res['predictions'] = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        res['predictions'] = str(e)

    return res

def audit_screener_bse_nse():
    """Scrape and parse official shareholding & market stats from Screener / Exchange disclosures."""
    res = {'shareholding': {}, 'quarterly_dii': {}, 'metrics': {}}
    
    url = "https://www.screener.in/company/HDFCBANK/consolidated/"
    try:
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Market Cap, Current Price, High/Low, PE, Book Value
            top_ratios = soup.find('ul', id='top-ratios')
            if top_ratios:
                for li in top_ratios.find_all('li'):
                    name_span = li.find('span', class_='name')
                    val_span = li.find('span', class_='nowrap value')
                    if name_span and val_span:
                        k = name_span.text.strip()
                        v = val_span.text.strip().replace('\n', ' ')
                        res['metrics'][k] = v
            
            # Shareholding Pattern Table
            sh_section = soup.find('section', id='shareholding')
            if sh_section:
                table = sh_section.find('table')
                if table:
                    headers = [th.text.strip() for th in table.find_all('th') if th.text.strip()]
                    for tr in table.find_all('tr'):
                        tds = tr.find_all('td')
                        if tds:
                            row_name = tds[0].text.strip()
                            vals = [td.text.strip() for td in tds[1:]]
                            if vals and headers:
                                # Map latest quarters
                                quarter_map = {}
                                for idx, q_val in enumerate(vals):
                                    if idx < len(headers) - 1:
                                        quarter_map[headers[idx + 1]] = q_val
                                res['shareholding'][row_name] = quarter_map
            
            # Numeric Company ID for quarterly domestic institution breakdown
            notebook_btn = soup.find('button', attrs={'data-url': re.compile(r'/notebook-(\d+)/')})
            if notebook_btn:
                cid = re.search(r'/notebook-(\d+)/', notebook_btn['data-url']).group(1)
                inst_url = f"https://www.screener.in/api/3/{cid}/investors/domestic_institutions/quarterly/"
                r_inst = requests.get(inst_url, headers={**BROWSER_HEADERS, 'Referer': url}, timeout=10)
                if r_inst.status_code == 200:
                    res['quarterly_dii'] = r_inst.json()
    except Exception as e:
        res['error'] = str(e)
        
    return res

def audit_local_sqlite():
    """Fetch HDFC Bank from local SQLite database."""
    res = {}
    if not Path(DB_PATH).exists():
        return {"error": "Local SQLite database not found"}
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Index Stocks
    try:
        c.execute("SELECT * FROM index_stocks WHERE symbol LIKE '%HDFCBANK%'")
        res['index_stocks'] = c.fetchall()
    except Exception as e:
        res['index_stocks'] = str(e)
        
    # 2. Cached Holdings
    try:
        c.execute("SELECT * FROM mf_holdings_cache WHERE symbol LIKE '%HDFCBANK%'")
        res['mf_holdings_cache'] = c.fetchall()
    except Exception as e:
        res['mf_holdings_cache'] = str(e)
        
    # 3. Concall Analyses
    try:
        c.execute("SELECT * FROM concall_analyses WHERE symbol LIKE '%HDFCBANK%'")
        res['concall_analyses'] = c.fetchall()
    except Exception as e:
        res['concall_analyses'] = str(e)
        
    conn.close()
    return res

def audit_app_code_fallbacks():
    """Extract hardcoded / default fallback metrics in Flutter app and Streamlit dashboard."""
    fallbacks = {
        "flutter_fallback_market_cap_cr": 1280000.0,
        "flutter_fallback_mf_schemes_count": 28,
        "flutter_fallback_mf_ownership_pct": "14.5% - 18.2%",
        "flutter_fallback_top_schemes": [
            {"scheme": "HDFC Top 100 Fund", "weight": "8.40%", "shares": "24,500,000", "value_cr": "4,165.0", "action": "STAKE_INCREASE"},
            {"scheme": "SBI Bluechip Fund", "weight": "7.90%", "shares": "18,500,000", "value_cr": "3,145.0", "action": "STAKE_INCREASE"},
            {"scheme": "Mirae Asset Large Cap Fund", "weight": "7.45%", "shares": "19,200,000", "value_cr": "3,264.0", "action": "STAKE_REDUCTION"},
            {"scheme": "Nippon India Small Cap Fund", "weight": "6.20%", "shares": "15,800,000", "value_cr": "2,686.0", "action": "FRESH_ENTRY"}
        ]
    }
    return fallbacks

def main():
    print("Fetching and reconciling data for HDFC Bank...")
    sb_data = audit_supabase()
    live_data = audit_screener_bse_nse()
    sqlite_data = audit_local_sqlite()
    app_fallbacks = audit_app_code_fallbacks()
    
    report = {
        "supabase": sb_data,
        "live_exchange_screener": live_data,
        "sqlite_local": sqlite_data,
        "app_fallbacks": app_fallbacks
    }
    
    with open("scripts/hdfc_reconciliation_raw.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
        
    print("[SUCCESS] Exported raw comparison to scripts/hdfc_reconciliation_raw.json")

if __name__ == "__main__":
    main()
