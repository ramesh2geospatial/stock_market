import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
from bs4 import BeautifulSoup
from config import SCREENER_COMPANY_URL, DEFAULT_HEADERS

for sym in ["TATAMOTORS", "ZOMATO"]:
    url = SCREENER_COMPANY_URL.format(symbol=sym)
    r = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
    print(f"URL: {url} -> Status: {r.status_code}")
    soup = BeautifulSoup(r.text, "lxml")
    doc_sec = soup.find("section", id="documents")
    print(f"Document section found for {sym}? {doc_sec is not None}")
    if doc_sec:
        subs = doc_sec.find_all("div", class_=lambda c: c and ("documents" in c or "sub" in c))
        print(f"Sub-sections found: {len(subs)}")
        headings = [h.get_text(strip=True) for h in doc_sec.find_all("h3")]
        print(f"Headings found: {headings}")
        links = doc_sec.find_all("a")
        print(f"Total links in #documents: {len(links)}")
        if links:
            print(f"Sample link: {links[0].get_text(strip=True)} -> {links[0].get('href')}")
