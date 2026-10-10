"""
News aggregator provider — merges yfinance news + Google News RSS.
"""
import re
import urllib.parse
import xml.etree.ElementTree as ET
import requests
import yfinance as yf

from providers.base import NewsProvider
from config import GOOGLE_NEWS_RSS_URL, DEFAULT_HEADERS


class GoogleYFinanceNewsProvider(NewsProvider):
    """Merges yfinance internal news with Google News RSS for Indian market context."""

    def fetch_news(self, symbol: str, company_name: str) -> list[dict]:
        items = []
        seen = set()

        # 1. yfinance news
        try:
            yf_news = yf.Ticker(symbol).news or []
            for item in yf_news:
                title = item.get("title") or (item.get("content", {}) or {}).get("title")
                link = item.get("link") or (item.get("content", {}) or {}).get("clickThroughUrl", {}).get("url")
                publisher = item.get("publisher") or (item.get("content", {}) or {}).get("provider", {}).get("displayName")
                pub_time = item.get("providerPublishTime") or (item.get("content", {}) or {}).get("pubDate")

                if title and link and title not in seen:
                    seen.add(title)
                    items.append({
                        "title": title,
                        "url": link,
                        "source": publisher or "Yahoo Finance",
                        "pub_date": pub_time,
                    })
        except Exception as e:
            print(f"[NewsProvider] yfinance news error: {e}")

        # 2. Google News RSS
        try:
            clean_name = re.sub(r"Limited|Ltd\.?|Corp\.?", "", company_name, flags=re.I).strip()
            query = f"{clean_name} stock OR {symbol}"
            params = {
                "q": query,
                "hl": "en-IN",
                "gl": "IN",
                "ceid": "IN:en",
            }
            url = f"{GOOGLE_NEWS_RSS_URL}?{urllib.parse.urlencode(params)}"

            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                for item in root.findall(".//item")[:10]:
                    title_el = item.find("title")
                    link_el = item.find("link")
                    pub_el = item.find("pubDate")
                    src_el = item.find("source")

                    if title_el is None or link_el is None:
                        continue

                    title = title_el.text or ""
                    short_title = title.split(" - ")[0]

                    if short_title not in seen:
                        seen.add(short_title)
                        items.append({
                            "title": short_title,
                            "url": link_el.text or "",
                            "source": src_el.text if src_el is not None else "Google News",
                            "pub_date": pub_el.text if pub_el is not None else "",
                        })
        except Exception as e:
            print(f"[NewsProvider] Google News RSS error: {e}")

        return items
