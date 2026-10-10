"""
BSE India Data Provider for fetching corporate announcements, filings, transcripts,
investor presentations, and financial result PDFs directly from BSE India APIs.
"""
import re
import datetime
import requests
from typing import Optional, Literal
from models.stock import UnifiedDocument, DocumentLink

# 6-digit BSE Scrip Code mapping for common Indian equities (NSE Symbol -> BSE Scrip Code)
NSE_TO_BSE_MAPPING = {
    "HDFCBANK": "500180",
    "RELIANCE": "500325",
    "INFY": "500209",
    "TCS": "532540",
    "TVSMOTOR": "532343",
    "ICICIBANK": "532174",
    "SBIN": "500112",
    "BHARTIARTL": "532454",
    "ITC": "500875",
    "LT": "500510",
    "AXISBANK": "532215",
    "KOTAKBANK": "500247",
    "HINDUNILVR": "500696",
    "BAJFINANCE": "532978",
    "MARUTI": "532500",
    "ASIANPAINT": "500820",
    "HCLTECH": "532281",
    "SUNPHARMA": "524715",
    "TATAMOTORS": "500570",
    "TATASTEEL": "500470",
    "NTPC": "532555",
    "POWERGRID": "532898",
    "ONGC": "500312",
    "TITAN": "500114",
    "ULTRACEMCO": "532538",
    "WIPRO": "507685",
    "ADANIENT": "512599",
    "ADANIPORTS": "532921",
    "JSWSTEEL": "500228",
    "M&M": "500520",
    "COALINDIA": "533278",
    "BAJAJFINSV": "532977",
    "NESTLEIND": "500790",
    "TECHM": "532755",
    "GRASIM": "500300",
    "CIPLA": "500087",
    "HDFCLIFE": "540777",
    "SBILIFE": "540719",
    "DRREDDY": "500124",
    "EICHERMOT": "505200",
    "BPCL": "500547",
    "TATACONSUM": "500800",
    "HEROMOTOCO": "500182",
    "APOLLOHOSP": "508869",
    "INDUSINDBK": "532187",
    "DIVISLAB": "532488",
    "HINDALCO": "500440",
    "BRITANNIA": "500825",
    "RBA": "543248",
    "JUBLFOOD": "533155",
    "DEVYANI": "543330",
    "WESTLIFE": "505533",
}

BSE_API_URL = "https://api.bseindia.com/BseIndiaAPI/api/CorporateSubmission/w"
BSE_ATTACH_BASE_LIVE = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
BSE_ATTACH_BASE_HIS = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/"

DEFAULT_BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bseindia.com/",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.bseindia.com",
}


class BSEProvider:
    """Provider for querying BSE India Corporate Announcements & Filings API."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = DEFAULT_BSE_HEADERS.copy()

    @staticmethod
    def get_bse_scrip_code(symbol: str) -> Optional[str]:
        """
        Map ticker to 6-digit BSE scrip code.
        Supports NSE ticker, 6-digit string, or suffix removal (.NS/.BO).
        """
        if not symbol:
            return None
        clean = symbol.strip().upper()
        if clean.endswith(".NS") or clean.endswith(".BO"):
            clean = clean[:-3]

        if clean.isdigit() and len(clean) == 6:
            return clean

        if clean in NSE_TO_BSE_MAPPING:
            return NSE_TO_BSE_MAPPING[clean]

        return None

    def fetch_announcements(
        self,
        scrip_code: str,
        category: str = "",
        prev_date: str = None,
        to_date: str = None,
    ) -> list[dict]:
        """
        Fetch corporate announcements from BSE API for given scrip code.
        prev_date and to_date formatted as YYYYMMDD.
        """
        if not scrip_code:
            return []

        today = datetime.date.today()
        if not to_date:
            to_date = today.strftime("%Y%m%d")
        if not prev_date:
            # Default to 3 years back
            three_years_ago = today - datetime.timedelta(days=3 * 365)
            prev_date = three_years_ago.strftime("%Y%m%d")

        params = {
            "scripcode": scrip_code,
            "strCat": category,
            "strType": "D",
            "strPrevDate": prev_date,
            "strToDate": to_date,
        }

        try:
            resp = requests.get(
                BSE_API_URL,
                params=params,
                headers=self.headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            elif isinstance(data, dict):
                table = data.get("Table", []) or data.get("CorporateSubmission", []) or []
                if isinstance(table, list):
                    return [item for item in table if isinstance(item, dict)]
            return []
        except Exception as e:
            print(f"[BSEProvider] Error fetching announcements for {scrip_code}: {e}")
            return []

    def classify_announcement(self, headline: str, newssub: str = "") -> str:
        """Classify announcement into 'transcript', 'presentation', 'financial_results', or 'other'."""
        text = f"{headline} {newssub}".lower()

        # Transcript patterns
        if any(k in text for k in ["concall", "con-call", "transcript", "earnings call", "audio recording transcript"]):
            return "transcript"
        # Presentation patterns
        elif any(k in text for k in ["presentation", "investor presentation", "analyst presentation", "factsheet", "deck", "ppt"]):
            return "presentation"
        # Financial results patterns
        elif any(k in text for k in ["financial result", "quarterly result", "outcome of board meeting", "audited results", "unaudited results", "financial statement"]):
            return "financial_results"
        elif "annual report" in text or "integrated report" in text:
            return "annual_report"
        elif "credit rating" in text or "rating update" in text:
            return "credit_rating"

        return "other"

    def resolve_quarter_from_filing_date(self, news_dt: str) -> str:
        """
        Derive financial quarter string (e.g. Q1 FY26) from filing date ISO timestamp or date string.
        Indian FY run: Apr 1 - Mar 31.
        Jan-Feb -> Q3 FYyy
        Mar-May -> Q4 FYyy
        Jun-Aug -> Q1 FY(yy+1)
        Sep-Nov -> Q2 FY(yy+1)
        Dec     -> Q3 FY(yy+1)
        """
        if not news_dt:
            return ""

        dt = None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y"):
            try:
                dt = datetime.datetime.strptime(news_dt.split(".")[0], fmt).date()
                break
            except (ValueError, TypeError, AttributeError):
                continue

        if not dt:
            return ""

        month = dt.month
        year = dt.year

        if month in (1, 2):
            quarter = 3
            fy = year
        elif month in (3, 4, 5):
            quarter = 4
            fy = year
        elif month in (6, 7, 8):
            quarter = 1
            fy = year + 1
        elif month in (9, 10, 11):
            quarter = 2
            fy = year + 1
        else:  # month == 12
            quarter = 3
            fy = year + 1

        return f"Q{quarter} FY{fy % 100:02d}"

    def fetch_documents(self, symbol: str) -> list[UnifiedDocument]:
        """
        Fetch corporate announcements for symbol, parse links, classify, and return UnifiedDocument list.
        """
        scrip_code = self.get_bse_scrip_code(symbol)
        if not scrip_code:
            print(f"[BSEProvider] Warning: Could not resolve BSE scrip code for symbol '{symbol}'")
            return []

        announcements = self.fetch_announcements(scrip_code)
        if not isinstance(announcements, list):
            print(f"[BSEProvider] Warning: Expected list of announcements for symbol '{symbol}', got {type(announcements)}")
            return []

        documents = []

        for item in announcements:
            if not isinstance(item, dict):
                continue
            headline = item.get("HEADLINE", "") or item.get("NEWSSUB", "") or ""
            newssub = item.get("NEWSSUB", "") or ""
            attachment = item.get("ATTACHMENTNAME", "") or item.get("ATTACHMENT", "") or ""
            news_dt = item.get("NEWS_DT", "") or item.get("DT_TM", "") or ""

            if not attachment:
                continue

            # Construct attachment URL
            if attachment.startswith("http://") or attachment.startswith("https://"):
                url = attachment
            else:
                url = f"{BSE_ATTACH_BASE_LIVE}{attachment}"

            category = self.classify_announcement(headline, newssub)
            if category == "other":
                # We prioritize transcript, presentation, financial_results
                continue

            quarter_label = self.resolve_quarter_from_filing_date(news_dt)
            if not quarter_label:
                # Try headline extraction fallback
                q_match = re.search(r"Q([1-4])\s*FY\s*(\d{2,4})", headline, re.I)
                if q_match:
                    q_num = q_match.group(1)
                    fy_num = int(q_match.group(2)) % 100
                    quarter_label = f"Q{q_num} FY{fy_num:02d}"
                else:
                    quarter_label = "Unknown"

            clean_symbol = symbol.strip().upper()
            if clean_symbol.endswith(".NS") or clean_symbol.endswith(".BO"):
                clean_symbol = clean_symbol[:-3]

            doc = UnifiedDocument(
                symbol=clean_symbol,
                quarter=quarter_label,
                title=headline or f"{category.capitalize()} - {quarter_label}",
                url=url,
                source_used="BSE",
                category=category,
                filing_date=news_dt,
                bse_scrip_code=scrip_code,
                date_hint=news_dt,
            )
            documents.append(doc)

        return documents
