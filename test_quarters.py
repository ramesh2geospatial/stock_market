import requests
import pandas as pd
from bs4 import BeautifulSoup
import copy
import io

url = "https://www.screener.in/company/RBA/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_html_table(table_soup):
    clean_table = copy.deepcopy(table_soup)
    for row in clean_table.find_all('tr'):
        for cell in row.find_all(['td', 'th']):
            text = cell.get_text(strip=True)
            text = text.replace(" +", "").replace("+", "").replace("", "")
            if not text and cell.find('a'):
                text = "PDF"
            cell.string = text
    return clean_table

try:
    r = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(r.text, 'lxml')
    quarters_section = soup.find('section', id='quarters')
    if quarters_section:
        table = quarters_section.find('table')
        if table:
            clean_table = clean_html_table(table)
            # Wrap in io.StringIO to force pandas to parse as string HTML
            dfs = pd.read_html(io.StringIO(str(clean_table)))
            df = dfs[0]
            print("\n=== Clean DataFrame ===")
            print(df.to_string(index=False))
except Exception as e:
    print(f"Error: {e}")
