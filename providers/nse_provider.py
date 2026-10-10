"""
NSE India Data Provider for corporate announcements fallback (Tier 3).
"""
import requests
import datetime
import re
from typing import Optional
from models.stock import UnifiedDocument

NSE_ANNOUNCEMENT_API = "https://www.nseindia.com/api/corporate-announcements"
NSE_ATTACH_BASE = "https://nselive.nseindia.com/content/corporate/anndecl/"

DEFAULT_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
}


class NSEProvider:
    """Provider for querying NSE India Corporate Announcements (Tier 3 fallback)."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = DEFAULT_NSE_HEADERS.copy()
        self.session = None

    def _init_session(self):
        """Establish session with NSE to obtain cookies (nsit, nseappid)."""
        if self.session is None:
            self.session = requests.Session()
            self.session.headers.update(self.headers)
            try:
                # Visit main page to set cookies
                self.session.get("https://www.nseindia.com", timeout=self.timeout)
            except Exception as e:
                print(f"[NSEProvider] Warning: Session init failed: {e}")

    def fetch_announcements(self, symbol: str) -> list[dict]:
        """Fetch announcements for ticker symbol from NSE API."""
        if not symbol:
            return []

        clean_symbol = symbol.strip().upper()
        if clean_symbol.endswith(".NS") or clean_symbol.endswith(".BO"):
            clean_symbol = clean_symbol[:-3]

        self._init_session()
        params = {
            "index": "equities",
            "symbol": clean_symbol,
        }

        try:
            resp = self.session.get(
                NSE_ANNOUNCEMENT_API,
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            print(f"[NSEProvider] Error fetching announcements for {clean_symbol}: {e}")
            return []

    def classify_announcement(self, desc: str, subject: str = "") -> str:
        """Classify announcement text into category."""
        text = f"{desc} {subject}".lower()
        if any(k in text for k in ["concall", "transcript", "earnings call"]):
            return "transcript"
        elif any(k in text for k in ["presentation", "investor presentation", "analyst presentation"]):
            return "presentation"
        elif any(k in text for k in ["financial result", "quarterly result", "outcome of board meeting"]):
            return "financial_results"
        elif "annual report" in text:
            return "annual_report"
        elif "credit rating" in text:
            return "credit_rating"
        return "other"

    def fetch_documents(self, symbol: str) -> list[UnifiedDocument]:
        """Fetch documents from NSE for symbol."""
        announcements = self.fetch_announcements(symbol)
        documents = []

        clean_symbol = symbol.strip().upper()
        if clean_symbol.endswith(".NS") or clean_symbol.endswith(".BO"):
            clean_symbol = clean_symbol[:-3]

        for item in announcements:
            desc = item.get("desc", "") or item.get("sm_name", "") or ""
            subject = item.get("subject", "") or ""
            att_file = item.get("attchmntFile", "") or item.get("attachment", "") or ""
            an_dt = item.get("an_dt", "") or item.get("bcastDate", "") or ""

            if not att_file:
                continue

            if att_file.startswith("http://") or att_file.startswith("https://"):
                url = att_file
            else:
                url = f"{NSE_ATTACH_BASE}{att_file}"

            category = self.classify_announcement(desc, subject)
            if category == "other":
                continue

            doc = UnifiedDocument(
                symbol=clean_symbol,
                quarter="Unknown",
                title=subject or desc or f"{category.capitalize()}",
                url=url,
                source_used="NSE",
                category=category,
                filing_date=an_dt,
            )
            documents.append(doc)

        return documents
