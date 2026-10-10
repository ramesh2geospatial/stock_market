"""
ETL Pipeline for Mutual Fund Holdings Data.

Processes monthly AMC portfolio disclosure CSVs and uploads to Supabase.
Computes MoM diff (month-over-month share changes) and classifies actions:
  - FRESH_ENTRY: New stock added to scheme portfolio
  - COMPLETE_EXIT: Stock fully removed from scheme portfolio  
  - STAKE_INCREASE: Shares increased from previous month
  - STAKE_REDUCTION: Shares decreased from previous month

Usage:
  python scripts/etl_mf_holdings.py --file disclosures.csv --date 2026-07-31
  python scripts/etl_mf_holdings.py --file disclosures.csv --date 2026-07-31 --dry-run
"""
import sys
import os
import csv
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SUPABASE_URL, SUPABASE_ANON_KEY


def parse_csv_holdings(filepath: str) -> List[Dict[str, Any]]:
    """Parse a CSV file with MF holdings data.
    
    Expected CSV columns (flexible column name matching):
      scheme_id, scheme_name, amc_name, symbol, isin, shares_held, 
      market_value_cr, portfolio_weight_pct
    """
    if not os.path.exists(filepath):
        print(f"[ETL] Error: File not found: {filepath}")
        return []
    
    holdings = []
    column_map = {
        'scheme_id': ['scheme_id', 'schemeid', 'fund_id'],
        'symbol': ['symbol', 'stock_symbol', 'ticker', 'nse_symbol'],
        'shares_held': ['shares_held', 'quantity', 'shares', 'qty', 'units'],
        'market_value_cr': ['market_value_cr', 'value_cr', 'market_value', 'value'],
        'portfolio_weight_pct': ['portfolio_weight_pct', 'weight_pct', 'weight', 'pct_of_aum'],
        'scheme_name': ['scheme_name', 'fund_name', 'scheme'],
        'amc_name': ['amc_name', 'amc', 'fund_house'],
        'isin': ['isin', 'isin_code'],
    }
    
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = [h.strip().lower() for h in (reader.fieldnames or [])]
            
            # Build header mapping
            field_map = {}
            for target, aliases in column_map.items():
                for alias in aliases:
                    if alias in headers:
                        field_map[target] = alias
                        break
            
            required = ['scheme_id', 'symbol', 'shares_held']
            missing = [r for r in required if r not in field_map]
            if missing:
                print(f"[ETL] Error: Missing required columns: {missing}")
                print(f"[ETL] Available columns: {headers}")
                return []
            
            for row in reader:
                # Normalize keys
                clean = {k.strip().lower(): v.strip() for k, v in row.items()}
                holding = {
                    'scheme_id': int(clean.get(field_map['scheme_id'], 0)),
                    'symbol': clean.get(field_map['symbol'], ''),
                    'shares_held': int(float(clean.get(field_map['shares_held'], 0))),
                }
                if 'market_value_cr' in field_map:
                    try:
                        holding['market_value_cr'] = float(clean.get(field_map['market_value_cr'], 0))
                    except (ValueError, TypeError):
                        holding['market_value_cr'] = 0.0
                if 'portfolio_weight_pct' in field_map:
                    try:
                        holding['portfolio_weight_pct'] = float(clean.get(field_map['portfolio_weight_pct'], 0))
                    except (ValueError, TypeError):
                        holding['portfolio_weight_pct'] = 0.0
                
                if holding['symbol'] and holding['shares_held'] >= 0:
                    holdings.append(holding)
        
        print(f"[ETL] Parsed {len(holdings)} holdings from {filepath}")
    except Exception as e:
        print(f"[ETL] Error parsing CSV: {e}")
    
    return holdings


def fetch_previous_month_holdings(
    scheme_ids: List[int],
    previous_date: str
) -> Dict[Tuple[int, str], int]:
    """Fetch previous month's holdings from Supabase for MoM diff calculation.
    
    Returns dict of (scheme_id, symbol) -> shares_held.
    """
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("[ETL] Warning: Supabase not configured, skipping previous month fetch")
        return {}
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }
    
    prev_holdings = {}
    for sid in scheme_ids:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/mf_stock_holdings?scheme_id=eq.{sid}&as_of_date=eq.{previous_date}&select=scheme_id,symbol,shares_held&limit=500"
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for row in data:
                    key = (row['scheme_id'], row['symbol'])
                    prev_holdings[key] = row.get('shares_held', 0)
        except Exception as e:
            print(f"[ETL] Warning: Failed to fetch previous holdings for scheme {sid}: {e}")
    
    print(f"[ETL] Fetched {len(prev_holdings)} previous month holdings for diff calculation")
    return prev_holdings


def compute_mom_diff(
    current_holdings: List[Dict[str, Any]],
    prev_holdings: Dict[Tuple[int, str], int],
    as_of_date: str
) -> List[Dict[str, Any]]:
    """Compute MoM share change and classify action type for each holding.
    
    Action classification:
      FRESH_ENTRY: prev_shares == 0 and current_shares > 0
      COMPLETE_EXIT: prev_shares > 0 and current_shares == 0
      STAKE_INCREASE: current_shares > prev_shares (and not fresh entry)
      STAKE_REDUCTION: current_shares < prev_shares (and not complete exit)
    """
    processed = []
    for h in current_holdings:
        key = (h['scheme_id'], h['symbol'])
        prev_shares = prev_holdings.get(key, 0)
        current_shares = h['shares_held']
        mom_change = current_shares - prev_shares
        
        # Classify action
        if prev_shares == 0 and current_shares > 0:
            action = 'FRESH_ENTRY'
        elif prev_shares > 0 and current_shares == 0:
            action = 'COMPLETE_EXIT'
        elif mom_change > 0:
            action = 'STAKE_INCREASE'
        elif mom_change < 0:
            action = 'STAKE_REDUCTION'
        else:
            action = 'STAKE_INCREASE'  # No change, treat as hold
        
        record = {
            'scheme_id': h['scheme_id'],
            'symbol': h['symbol'],
            'as_of_date': as_of_date,
            'shares_held': current_shares,
            'market_value_cr': h.get('market_value_cr'),
            'portfolio_weight_pct': h.get('portfolio_weight_pct'),
            'mom_share_change': mom_change,
            'action_type': action,
        }
        processed.append(record)
    
    # Summary
    actions = {}
    for r in processed:
        actions[r['action_type']] = actions.get(r['action_type'], 0) + 1
    print(f"[ETL] Diff computed: {actions}")
    
    return processed


def validate_holdings(holdings: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Validate holding records before upload.
    
    Returns (valid_records, error_messages).
    """
    valid = []
    errors = []
    valid_actions = {'FRESH_ENTRY', 'COMPLETE_EXIT', 'STAKE_INCREASE', 'STAKE_REDUCTION'}
    
    for i, h in enumerate(holdings):
        if not h.get('symbol'):
            errors.append(f"Row {i}: Missing symbol")
            continue
        if h.get('shares_held', -1) < 0:
            errors.append(f"Row {i}: Negative shares_held for {h.get('symbol')}")
            continue
        if h.get('action_type') not in valid_actions:
            errors.append(f"Row {i}: Invalid action_type '{h.get('action_type')}' for {h.get('symbol')}")
            continue
        valid.append(h)
    
    if errors:
        print(f"[ETL] Validation: {len(valid)} valid, {len(errors)} errors")
        for err in errors[:10]:  # Show first 10 errors
            print(f"  ⚠️ {err}")
    else:
        print(f"[ETL] Validation: All {len(valid)} records valid ✅")
    
    return valid, errors


def upload_to_supabase(
    holdings: List[Dict[str, Any]],
    batch_size: int = 100
) -> Dict[str, Any]:
    """Batch upsert holdings to Supabase mf_stock_holdings table."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return {"success": False, "error": "Supabase not configured"}
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    endpoint = f"{SUPABASE_URL.rstrip('/')}/rest/v1/mf_stock_holdings"
    
    total_uploaded = 0
    errors = []
    
    for i in range(0, len(holdings), batch_size):
        batch = holdings[i:i + batch_size]
        body = json.dumps(batch).encode("utf-8")
        try:
            req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                total_uploaded += len(batch)
                print(f"[ETL] Uploaded batch {i // batch_size + 1}: {len(batch)} records")
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8', errors='ignore')
            errors.append(f"Batch {i // batch_size + 1}: HTTP {e.code} - {err_msg}")
            print(f"[ETL] Error in batch {i // batch_size + 1}: {err_msg}")
        except Exception as e:
            errors.append(f"Batch {i // batch_size + 1}: {str(e)}")
            print(f"[ETL] Error in batch {i // batch_size + 1}: {e}")
    
    return {
        "success": len(errors) == 0,
        "uploaded": total_uploaded,
        "errors": errors,
        "total_records": len(holdings)
    }


def get_previous_month_date(current_date: str) -> str:
    """Get the last day of the previous month."""
    dt = datetime.strptime(current_date, "%Y-%m-%d")
    # Go to first day of current month, then subtract 1 day
    first_of_month = dt.replace(day=1)
    prev_last = first_of_month - timedelta(days=1)
    return prev_last.strftime("%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(description="ETL Pipeline for Mutual Fund Holdings")
    parser.add_argument("--file", required=True, help="Path to CSV file with MF holdings data")
    parser.add_argument("--date", required=True, help="As-of date for holdings (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate only, don't upload")
    parser.add_argument("--skip-diff", action="store_true", help="Skip MoM diff calculation")
    parser.add_argument("--batch-size", type=int, default=100, help="Upload batch size")
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"MF Holdings ETL Pipeline")
    print(f"File: {args.file}")
    print(f"Date: {args.date}")
    print(f"Dry Run: {args.dry_run}")
    print(f"{'='*60}\n")
    
    # Step 1: Parse CSV
    raw_holdings = parse_csv_holdings(args.file)
    if not raw_holdings:
        print("[ETL] No holdings to process. Exiting.")
        sys.exit(1)
    
    # Step 2: Compute MoM Diff
    if args.skip_diff:
        # Set as_of_date and default action
        for h in raw_holdings:
            h['as_of_date'] = args.date
            h['mom_share_change'] = h.get('mom_share_change', 0)
            h['action_type'] = h.get('action_type', 'STAKE_INCREASE')
        processed = raw_holdings
    else:
        prev_date = get_previous_month_date(args.date)
        scheme_ids = list(set(h['scheme_id'] for h in raw_holdings))
        prev_holdings = fetch_previous_month_holdings(scheme_ids, prev_date)
        processed = compute_mom_diff(raw_holdings, prev_holdings, args.date)
    
    # Step 3: Validate
    valid, errors = validate_holdings(processed)
    if not valid:
        print("[ETL] No valid records after validation. Exiting.")
        sys.exit(1)
    
    # Step 4: Upload (unless dry-run)
    if args.dry_run:
        print(f"\n[ETL] DRY RUN: Would upload {len(valid)} records to Supabase")
        print(f"[ETL] Sample records:")
        for r in valid[:5]:
            print(f"  {r['symbol']}: {r['shares_held']} shares, {r['action_type']}, change: {r['mom_share_change']}")
    else:
        result = upload_to_supabase(valid, batch_size=args.batch_size)
        print(f"\n[ETL] Upload Result: {result}")
    
    print(f"\n{'='*60}")
    print(f"ETL Complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
