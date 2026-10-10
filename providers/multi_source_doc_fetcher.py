"""
Multi-Source Document Fetcher with 3-tier fallback architecture:
Tier 1 (BSE India Announcements API) -> Tier 2 (Screener.in) -> Tier 3 (NSE India API / fallback).
Includes cross-source deduplication and local file persistence under data/documents/{symbol}/{quarter}/.
"""
import os
import re
import hashlib
import requests
import datetime
from pathlib import Path
from typing import Optional

from models.stock import UnifiedDocument, DocumentLink
from providers.bse_provider import BSEProvider
from providers.screener_provider import ScreenerProvider
from providers.nse_provider import NSEProvider
from storage.sqlite_store import SQLiteStore
from storage.cache import FileCache

DOCUMENTS_DIR = Path("data/documents")


def normalize_quarter_label(quarter_str: str, filing_date: str = "") -> str:
    """
    Normalize various date/quarter hints into canonical Indian FY quarter label (e.g. Q1 FY26).
    Examples:
        "Jul 2025" -> "Q1 FY26"
        "May 2026" -> "Q4 FY26"
        "Q1 FY26" -> "Q1 FY26"
        "Q4 FY2026" -> "Q4 FY26"
    """
    raw = (quarter_str or "").strip()
    if not raw and filing_date:
        raw = filing_date.strip()

    if not raw:
        return "Unknown"

    # Direct match for Q[1-4] FY[0-9]{2,4}
    m_fy = re.search(r"Q([1-4])\s*FY\s*(\d{2,4})", raw, re.I)
    if m_fy:
        q = int(m_fy.group(1))
        y = int(m_fy.group(2))
        if y > 2000:
            y %= 100
        return f"Q{q} FY{y:02d}"

    # Try parsing month-year or date strings
    for fmt in ("%b %Y", "%B %Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(raw.split(".")[0], fmt).date()
            month = dt.month
            year = dt.year
            # Indian FY Quarter assignment based on month:
            # Jan, Feb -> Q3 FYyy
            # Mar, Apr, May -> Q4 FYyy
            # Jun, Jul, Aug -> Q1 FY(yy+1)
            # Sep, Oct, Nov -> Q2 FY(yy+1)
            # Dec -> Q3 FY(yy+1)
            if month in (1, 2):
                q, fy = 3, year
            elif month in (3, 4, 5):
                q, fy = 4, year
            elif month in (6, 7, 8):
                q, fy = 1, year + 1
            elif month in (9, 10, 11):
                q, fy = 2, year + 1
            else:  # month == 12
                q, fy = 3, year + 1
            return f"Q{q} FY{fy % 100:02d}"
        except (ValueError, TypeError):
            continue

    return raw


class MultiSourceDocFetcher:
    """
    3-Tier Fallback Multi-Source Document Ingestion Engine.
    Tier 1: BSE India Announcements API
    Tier 2: Screener.in Aggregator
    Tier 3: NSE India Filings API
    """

    def __init__(self, db_store: SQLiteStore = None, cache: FileCache = None, docs_base_dir: Path = DOCUMENTS_DIR):
        self.bse = BSEProvider()
        self.screener = ScreenerProvider()
        self.nse = NSEProvider()
        self.db = db_store or SQLiteStore()
        self.cache = cache or FileCache()
        self.docs_base_dir = Path(docs_base_dir)

    def fetch_documents(self, symbol: str, force_refresh: bool = False) -> list[UnifiedDocument]:
        """
        Fetch documents using 3-tier fallback strategy, deduplicate across sources,
        and index them in SQLite.
        """
        clean_symbol = symbol.strip().upper()
        if clean_symbol.endswith(".NS") or clean_symbol.endswith(".BO"):
            clean_symbol = clean_symbol[:-3]

        if not force_refresh:
            cached_docs = self.db.get_documents_index(symbol=clean_symbol)
            if cached_docs:
                return [UnifiedDocument(**d) for d in cached_docs]

        all_docs: list[UnifiedDocument] = []
        tier_used = None
        required_categories = {"transcript", "presentation", "financial_results"}

        # --- Tier 1: BSE India API ---
        try:
            bse_docs = self.bse.fetch_documents(clean_symbol)
            if bse_docs:
                all_docs.extend(bse_docs)
                tier_used = "BSE"
        except Exception as e:
            print(f"[MultiSourceDocFetcher] Tier 1 (BSE) failed for {clean_symbol}: {e}")

        # --- Tier 2: Screener.in (if Tier 1 is missing any required categories) ---
        found_categories = {d.category for d in all_docs}
        if not required_categories.issubset(found_categories):
            try:
                screener_links = self.screener.fetch_documents(clean_symbol)
                if screener_links:
                    for link in screener_links:
                        quarter_lbl = normalize_quarter_label(link.date_hint or link.title)
                        cat = link.category
                        if cat not in ("transcript", "presentation", "financial_results", "credit_rating", "annual_report"):
                            cat = "other"

                        udoc = UnifiedDocument(
                            symbol=clean_symbol,
                            quarter=quarter_lbl,
                            title=link.title,
                            url=link.url,
                            source_used="SCREENER",
                            category=cat,
                            date_hint=link.date_hint,
                        )
                        all_docs.append(udoc)
                    tier_used = "SCREENER" if not tier_used else tier_used
            except Exception as e:
                print(f"[MultiSourceDocFetcher] Tier 2 (Screener) failed for {clean_symbol}: {e}")

        # --- Tier 3: NSE India API (if required categories are still missing) ---
        found_categories = {d.category for d in all_docs}
        if not required_categories.issubset(found_categories):
            try:
                nse_docs = self.nse.fetch_documents(clean_symbol)
                if nse_docs:
                    all_docs.extend(nse_docs)
                    tier_used = "NSE" if not tier_used else tier_used
            except Exception as e:
                print(f"[MultiSourceDocFetcher] Tier 3 (NSE) failed for {clean_symbol}: {e}")

        # Cross-source deduplication
        deduped_docs = self.deduplicate_documents(all_docs)

        # Index in SQLite
        for doc in deduped_docs:
            self.db.save_document_index(doc)

        return deduped_docs

    def deduplicate_documents(self, docs: list[UnifiedDocument]) -> list[UnifiedDocument]:
        """
        Deduplicate documents for the same quarter and category using fine-grained keys.
        Multiple distinct filings in the same quarter for a category (e.g. Analyst Meet vs Concall Transcript)
        are NOT dropped. Priority order: BSE -> SCREENER -> NSE.
        """
        seen_urls = set()
        seen_title_keys = set()
        deduped = []

        # Sort with preference to BSE > SCREENER > NSE
        source_priority = {"BSE": 1, "SCREENER": 2, "NSE": 3}
        sorted_docs = sorted(docs, key=lambda d: (source_priority.get(d.source_used, 99), d.quarter, d.category))

        for doc in sorted_docs:
            norm_q = normalize_quarter_label(doc.quarter, doc.filing_date or doc.date_hint or "")
            doc.quarter = norm_q

            norm_title = re.sub(r"\s+", " ", (doc.title or "").strip().lower())
            norm_url = (doc.url or "").strip().lower()

            title_key = (doc.symbol, norm_q, doc.category, norm_title)
            url_key = norm_url if norm_url else None

            is_duplicate = False
            if url_key and url_key in seen_urls:
                is_duplicate = True
            elif norm_title and title_key in seen_title_keys:
                is_duplicate = True

            if not is_duplicate:
                if url_key:
                    seen_urls.add(url_key)
                if norm_title:
                    seen_title_keys.add(title_key)
                deduped.append(doc)

        return deduped

    def download_and_store(self, doc: UnifiedDocument, timeout: int = 15) -> UnifiedDocument:
        """
        Download document binary/text content from remote URL, compute MD5 checksum,
        save to local file system under data/documents/{symbol}/{quarter}/,
        and update SQLite document index.
        Validates PDF magic bytes (%PDF-) for PDF documents before saving.
        """
        if not doc.url:
            return doc

        clean_symbol = doc.symbol.upper()
        target_dir = self.docs_base_dir / clean_symbol / (doc.quarter or "Unknown")

        url_hash = hashlib.md5(doc.url.encode("utf-8")).hexdigest()[:8]
        ext = ".pdf" if ".pdf" in doc.url.lower() or doc.category in ("transcript", "presentation", "financial_results") else ".html"
        filename = f"{doc.category}_{doc.source_used}_{url_hash}{ext}"
        file_path = target_dir / filename

        try:
            resp = requests.get(
                doc.url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
                },
                timeout=timeout,
            )
            resp.raise_for_status()

            content = resp.content

            if ext == ".pdf" and not content.startswith(b"%PDF-"):
                print(f"[MultiSourceDocFetcher] Content for {doc.url} is not a valid PDF (missing %PDF- magic bytes). Flagging extraction failure.")
                doc.extraction_status = "failed"
                doc.local_path = None
                self.db.save_document_index(doc)
                return doc

            target_dir.mkdir(parents=True, exist_ok=True)
            md5_checksum = hashlib.md5(content).hexdigest()

            with open(file_path, "wb") as f:
                f.write(content)

            doc.local_path = str(file_path.absolute())
            doc.checksum = md5_checksum
            doc.file_size_bytes = len(content)
            doc.extraction_status = "success"

            # Update DB index
            self.db.save_document_index(doc)

        except Exception as e:
            print(f"[MultiSourceDocFetcher] Error downloading {doc.url}: {e}")
            doc.extraction_status = "failed"

        return doc

    def fetch_quarterly_documents(self, symbol: str, quarters: int = 40, force_refresh: bool = False) -> dict[str, list[dict]]:
        """
        Fetch, deduplicate, and group documents into standard categorized dictionary.
        Returns: {"transcripts": [...], "presentations": [...], "financial_results": [...], "credit_ratings": [...], "annual_reports": [...]}
        """
        docs = self.fetch_documents(symbol, force_refresh=force_refresh)
        result = {
            "transcripts": [],
            "presentations": [],
            "financial_results": [],
            "credit_ratings": [],
            "annual_reports": [],
            "other": [],
        }

        for doc in docs:
            d_dict = doc.model_dump()
            cat = doc.category
            if cat == "transcript":
                result["transcripts"].append(d_dict)
            elif cat == "presentation":
                result["presentations"].append(d_dict)
            elif cat == "financial_results":
                result["financial_results"].append(d_dict)
            elif cat == "credit_rating":
                result["credit_ratings"].append(d_dict)
            elif cat == "annual_report":
                result["annual_reports"].append(d_dict)
            else:
                result["other"].append(d_dict)

        # Retain all documents (up to quarters limit if specified, preserving latest)
        for cat in result:
            if len(result[cat]) > quarters:
                result[cat] = result[cat][-quarters:]

        return result
