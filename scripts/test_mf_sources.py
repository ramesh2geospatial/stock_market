import requests
import json
import re
from bs4 import BeautifulSoup

def test_screener():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    # Screener company page
    url = 'https://www.screener.in/company/RELIANCE/consolidated/'
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # Check for company id
    btn = soup.find('button', attrs={'data-url': True})
    print('Trades button:', btn['data-url'] if btn else None)
    
    # Try company-id url
    # /api/company/2726/shareholders/?q=domestic_institutions&period=quarterly
    test_urls = [
        'https://www.screener.in/api/company/2726/shareholders/?q=domestic_institutions&period=quarterly',
        'https://www.screener.in/api/company/2726/shareholders/?q=foreign_institutions&period=quarterly',
        'https://www.screener.in/api/company/2726/shareholders/?q=promoters&period=quarterly',
        'https://www.screener.in/api/company/2726/shareholding-details/',
    ]
    
    for u in test_urls:
        r = requests.get(u, headers=headers)
        print(f'{u} -> {r.status_code}')
        if r.status_code == 200:
            print('SUCCESS Content preview:\n', r.text[:600])

if __name__ == '__main__':
    test_screener()
