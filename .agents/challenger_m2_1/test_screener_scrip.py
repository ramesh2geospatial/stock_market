import requests

symbols = ["500570", "543320"]
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}

for s in symbols:
    url = f"https://www.screener.in/company/{s}/"
    r = requests.get(url, headers=headers)
    print(f"URL {url} -> Status: {r.status_code}, Final URL: {r.url}")
