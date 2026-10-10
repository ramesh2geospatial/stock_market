import requests

symbols = ["TATAMOTORS", "ZOMATO", "ETHEREUM"]
test_urls = [
    "https://www.screener.in/company/{symbol}/",
    "https://www.screener.in/company/{symbol}/consolidated/",
    "https://www.screener.in/company/{symbol}",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
}

for s in symbols:
    print(f"\n--- Checking {s} ---")
    for u in test_urls:
        url = u.format(symbol=s)
        resp = requests.get(url, headers=headers, allow_redirects=True)
        print(f"URL: {url} -> Status: {resp.status_code}, Final URL: {resp.url}")
