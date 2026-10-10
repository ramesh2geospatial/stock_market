import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
from bs4 import BeautifulSoup
from providers.screener_provider import ScreenerProvider

sp = ScreenerProvider()
for sym in ["HDFCBANK", "ZOMATO", "RELIANCE", "TATAMOTORS", "INFY"]:
    docs = sp.fetch_documents(sym)
    print(f"Symbol: {sym} -> Screener fetched {len(docs)} docs")
