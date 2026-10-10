import logging
import requests
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amfi_nav_fetcher")

AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
MFAPI_BASE_URL = "https://api.mfapi.in/mf"

class AMFINAVFetcher:
    """Legal open-data client fetching official daily NAVs from AMFI & mfapi.in."""

    def __init__(self):
        self._cache: Dict[str, Dict] = {}

    def fetch_amfi_daily_nav(self) -> List[Dict]:
        """Fetch and parse the raw AMFI NAV text feed (NAVAll.txt)."""
        logger.info(f"Fetching daily NAV feed from {AMFI_NAV_URL}...")
        try:
            response = requests.get(AMFI_NAV_URL, timeout=15)
            response.raise_for_status()
            lines = response.text.splitlines()

            results = []
            current_house = "Unknown AMC"

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check for AMC header lines (e.g. "HDFC Mutual Fund")
                if ";" not in line:
                    current_house = line
                    continue

                parts = line.split(";")
                if len(parts) >= 6 and parts[0].isdigit():
                    scheme_code = parts[0].strip()
                    isin_growth = parts[1].strip()
                    isin_reinvest = parts[2].strip()
                    scheme_name = parts[3].strip()
                    nav_str = parts[4].strip()
                    nav_date = parts[5].strip()

                    try:
                        nav = float(nav_str)
                    except ValueError:
                        nav = 0.0

                    record = {
                        "scheme_code": scheme_code,
                        "isin_growth": isin_growth,
                        "isin_reinvest": isin_reinvest,
                        "scheme_name": scheme_name,
                        "nav": nav,
                        "date": nav_date,
                        "amc": current_house
                    }
                    results.append(record)
                    self._cache[scheme_code] = record

            logger.info(f"Successfully parsed {len(results)} schemes from AMFI feed.")
            return results

        except Exception as e:
            logger.error(f"Error fetching AMFI feed: {e}")
            return []

    def get_nav_from_mfapi(self, scheme_code: str) -> Optional[Dict]:
        """Fallback REST lookup via public mfapi.in API."""
        url = f"{MFAPI_BASE_URL}/{scheme_code}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                meta = data.get("meta", {})
                nav_list = data.get("data", [])
                latest_nav = float(nav_list[0]["nav"]) if nav_list else 0.0
                latest_date = nav_list[0]["date"] if nav_list else ""
                return {
                    "scheme_code": str(meta.get("scheme_code", scheme_code)),
                    "scheme_name": meta.get("scheme_name", ""),
                    "amc": meta.get("fund_house", ""),
                    "scheme_category": meta.get("scheme_category", ""),
                    "nav": latest_nav,
                    "date": latest_date
                }
        except Exception as e:
            logger.error(f"Error fetching from mfapi.in for scheme {scheme_code}: {e}")
        return None

if __name__ == "__main__":
    fetcher = AMFINAVFetcher()
    data = fetcher.fetch_amfi_daily_nav()
    if data:
        print(f"Sample scheme: {data[0]}")
