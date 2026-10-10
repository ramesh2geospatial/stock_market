"""
Sync all 752 official index constituent stocks to Supabase Cloud PostgreSQL.
Uses PostgREST REST API with proper headers and error handling.
"""
import sys
import os
import json
import sqlite3
import urllib.request
import urllib.error

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_PUBLISHABLE_KEY

def sync_to_supabase():
    print("[Supabase Sync] Fetching 752 index stocks from local SQLite...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT symbol, company_name, index_name, tier, mcap_cr, sector FROM index_stocks")
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("[Supabase Sync] Error: No index stocks found in local database.")
        return

    payload = [
        {
            "symbol": r[0],
            "company_name": r[1],
            "index_name": r[2],
            "market_cap_tier": r[3],
            "market_cap_cr": r[4] or 0.0,
            "sector": r[5] or "Equities"
        }
        for r in rows
    ]

    print(f"[Supabase Sync] Uploading {len(payload)} stocks to Supabase table `index_stocks`...")

    endpoint = f"{SUPABASE_URL.rstrip('/')}/rest/v1/index_stocks"
    
    # Try with Anon key and Publishable key
    keys_to_try = [SUPABASE_ANON_KEY, SUPABASE_PUBLISHABLE_KEY]
    
    for idx, key in enumerate(keys_to_try):
        if not key:
            continue
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }

        try:
            # Batch upload in chunks of 100 stocks
            chunk_size = 100
            for i in range(0, len(payload), chunk_size):
                chunk = payload[i:i + chunk_size]
                body = json.dumps(chunk).encode("utf-8")
                req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    pass
            print(f"[Supabase Sync] SUCCESS! All {len(payload)} stocks synced to Supabase PostgreSQL!")
            return
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="ignore")
            print(f"[Supabase Sync] Key #{idx+1} failed with HTTP {e.code}: {err}")
        except Exception as e:
            print(f"[Supabase Sync] Key #{idx+1} error: {e}")

if __name__ == "__main__":
    sync_to_supabase()
