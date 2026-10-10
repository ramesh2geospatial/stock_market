"""Audit script for the new Vahan cumulative snapshot + interpolation system."""
import sqlite3
import datetime
import sys
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

conn = sqlite3.connect('data/portfolio.db')
c = conn.cursor()

# Clear old daily data so the new system can start fresh
print("=== CLEARING OLD DAILY DATA ===")
c.execute("DELETE FROM vahan_daily_sales")
conn.commit()
print("Cleared vahan_daily_sales table")

# Create the new snapshots table if it doesn't exist yet
c.execute("""
    CREATE TABLE IF NOT EXISTS vahan_cumulative_snapshots (
        maker TEXT,
        date TEXT,
        cumulative_mtd INTEGER,
        month INTEGER,
        year INTEGER,
        source TEXT DEFAULT 'estimated',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(maker, date)
    )
""")
conn.commit()
print("Ensured vahan_cumulative_snapshots table exists")
conn.close()

print("\n=== TESTING VAHAN PROVIDER ===")
sys.path.insert(0, '.')
from providers.vahan_provider import VahanProvider

vahan = VahanProvider()
today = datetime.date.today()
month = today.month
year = today.year
prev_y, prev_m = vahan._get_prev_month(year, month)

print(f"\nToday: {today}")
print(f"Current month: {vahan.MONTH_NAMES[month-1]} {year}")
print(f"Previous month: {vahan.MONTH_NAMES[prev_m-1]} {prev_y}")

# Test growth factor calculation
print("\n=== GROWTH FACTORS ===")
for maker in vahan.get_makers():
    gf = vahan._calc_growth_factor(maker, prev_y, prev_m)
    prev_total = vahan._get_monthly_total(maker, prev_y, prev_m)
    est = vahan._estimate_current_month_cumulative(maker, today)
    print(f"  {maker}: growth_factor={gf:.3f}, prev_month_total={prev_total:,}, estimated_today_cumulative={est:,}")

# Trigger get_daily_sales_df which will create snapshots + interpolate
print("\n=== GENERATING DAILY DATA ===")
df = vahan.get_daily_sales_df()
print(f"Total daily rows generated: {len(df)}")

# Check snapshots
conn = sqlite3.connect('data/portfolio.db')
print("\n=== CUMULATIVE SNAPSHOTS ===")
rows = conn.execute("SELECT maker, date, cumulative_mtd, source FROM vahan_cumulative_snapshots ORDER BY maker, date").fetchall()
for r in rows:
    print(f"  {r[0]}: {r[1]} -> cumulative={r[2]:,} (source={r[3]})")

# Check daily sums match cumulative
print("\n=== DAILY SUMS vs CUMULATIVE (VERIFICATION) ===")
for maker in vahan.get_makers():
    # Current month daily sum
    row = conn.execute(
        "SELECT SUM(registrations) FROM vahan_daily_sales WHERE maker=? AND date LIKE ?",
        (maker, f"{year}-{month:02d}-%")
    ).fetchone()
    daily_sum = row[0] or 0
    
    # Cumulative snapshot
    snap_row = conn.execute(
        "SELECT cumulative_mtd FROM vahan_cumulative_snapshots WHERE maker=? AND month=? AND year=? ORDER BY date DESC LIMIT 1",
        (maker, month, year)
    ).fetchone()
    snap_cum = snap_row[0] if snap_row else 0
    
    match = "MATCH" if daily_sum == snap_cum else f"MISMATCH (diff={daily_sum - snap_cum})"
    print(f"  {maker}: daily_sum={daily_sum:,} vs cumulative={snap_cum:,} -> {match}")

# Previous month check
print(f"\n=== PREVIOUS MONTH ({vahan.MONTH_NAMES[prev_m-1]} {prev_y}) DAILY SUMS ===")
for maker in vahan.get_makers():
    row = conn.execute(
        "SELECT SUM(registrations) FROM vahan_daily_sales WHERE maker=? AND date LIKE ?",
        (maker, f"{prev_y}-{prev_m:02d}-%")
    ).fetchone()
    daily_sum = row[0] or 0
    expected = vahan._get_monthly_total(maker, prev_y, prev_m) or 0
    match = "MATCH" if daily_sum == expected else f"MISMATCH (diff={daily_sum - expected})"
    print(f"  {maker}: daily_sum={daily_sum:,} vs monthly_static={expected:,} -> {match}")

# All-time totals
print("\n=== ALL-TIME TOTALS ===")
alltime = vahan.get_all_time_totals()
for maker, total in alltime.items():
    print(f"  {maker}: {total:,}")

conn.close()
print("\n=== AUDIT COMPLETE ===")
