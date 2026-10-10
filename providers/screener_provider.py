"""
Screener.in scraping provider for documents, quarterly results, and transcripts.
"""
import re
import io
import copy
import requests
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

from providers.base import DocumentProvider
from models.stock import QuarterlyResult, DocumentLink
from config import (
    SCREENER_COMPANY_URL, SCREENER_CHART_API_URL,
    DEFAULT_HEADERS, MAX_TRANSCRIPT_PAGES, MAX_TRANSCRIPT_CHARS, MAX_QUARTERS,
)


def _strip_suffix(symbol: str) -> str:
    """Remove .NS or .BO suffix to get the Screener-compatible symbol."""
    return re.sub(r"\.(NS|BO)$", "", symbol.upper())


class ScreenerProvider(DocumentProvider):
    """Scrapes Screener.in for quarterly results, concall transcripts, and documents."""

    def fetch_documents(self, symbol: str, bse_scrip_code: str = None) -> list[DocumentLink]:
        """
        Fetch ALL document links from Screener.in's #documents section.
        Uses the h3 category headers for reliable classification.
        Falls back to BSE scrip code URL on 404.
        """
        base = _strip_suffix(symbol)
        url = SCREENER_COMPANY_URL.format(symbol=base)
        docs = []

        try:
            r = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
            if r.status_code == 404:
                from providers.bse_provider import BSEProvider
                scrip_code = bse_scrip_code or BSEProvider.get_bse_scrip_code(symbol)
                if scrip_code:
                    fallback_url = SCREENER_COMPANY_URL.format(symbol=scrip_code)
                    r = requests.get(fallback_url, headers=DEFAULT_HEADERS, timeout=15)

            if r.status_code != 200:
                return docs

            soup = BeautifulSoup(r.text, "lxml")
            doc_section = soup.find("section", id="documents")
            if not doc_section:
                return docs

            # Parse by sub-sections with h3 headers
            subs = doc_section.find_all("div", class_=lambda c: c and ("documents" in c or "sub" in c))
            for sub in subs:
                heading = sub.find("h3")
                heading_text = heading.get_text(strip=True).lower() if heading else ""

                # Determine category from heading
                if "transcript" in heading_text or "concall" in heading_text:
                    category = "transcript"
                elif "presentation" in heading_text:
                    category = "presentation"
                elif "rating" in heading_text:
                    category = "credit_rating"
                elif "annual" in heading_text:
                    category = "annual_report"
                else:
                    category = "other"

                if category == "transcript":
                    lis = sub.find_all("li")
                    if lis:
                        for li in lis:
                            date_div = li.find("div")
                            date_str = date_div.get_text(strip=True) if date_div else ""
                            
                            for a in li.find_all("a"):
                                href = a.get("href", "")
                                if href.startswith("/"):
                                    href = "https://www.screener.in" + href
                                if not href:
                                    continue
                                
                                link_text = a.get_text(strip=True)
                                if "transcript" in link_text.lower():
                                    title = f"Concall Transcript - {date_str}" if date_str else "Concall Transcript"
                                    docs.append(DocumentLink(
                                        title=title, url=href,
                                        category="transcript", date_hint=date_str or None
                                    ))
                                elif "ppt" in link_text.lower() or "presentation" in link_text.lower():
                                    title = f"Concall PPT - {date_str}" if date_str else "Concall PPT"
                                    docs.append(DocumentLink(
                                        title=title, url=href,
                                        category="presentation", date_hint=date_str or None
                                    ))
                        continue

                for a in sub.find_all("a"):
                    href = a.get("href", "")
                    if href.startswith("/"):
                        href = "https://www.screener.in" + href
                    if not href:
                        continue

                    title = a.get_text(strip=True)
                    # Try to extract a date hint from the title
                    date_match = re.search(
                        r"((?:Q[1-4]\s*)?(?:FY\s*)?20\d{2}(?:\s*[-–]\s*\d{2})?)", title, re.I
                    )
                    date_hint = date_match.group(1) if date_match else None

                    docs.append(DocumentLink(
                        title=title, url=href,
                        category=category, date_hint=date_hint,
                    ))

            # Fallback: if no sub-sections found, do keyword matching on all links
            if not docs:
                for a in doc_section.find_all("a"):
                    href = a.get("href", "")
                    if href.startswith("/"):
                        href = "https://www.screener.in" + href
                    if not href:
                        continue
                    text = a.get_text(strip=True).lower()
                    title = a.get_text(strip=True)
                    if "transcript" in text or "concall" in text or "audio" in text:
                        cat = "transcript"
                    elif "presentation" in text or "ppt" in text:
                        cat = "presentation"
                    elif "rating" in text:
                        cat = "credit_rating"
                    elif "annual" in text:
                        cat = "annual_report"
                    else:
                        cat = "other"
                    docs.append(DocumentLink(title=title, url=href, category=cat))

        except Exception as e:
            print(f"[ScreenerProvider] Error fetching documents: {e}")

        return docs

    def fetch_quarterly_results(self, symbol: str) -> list[QuarterlyResult]:
        """
        Return structured QuarterlyResult objects for the last N quarters.
        Uses the Screener.in Chart API for extended history, falls back to HTML table.
        """
        base = _strip_suffix(symbol)
        results = []

        # Strategy 1: Chart API (gives more history as JSON)
        try:
            api_url = SCREENER_CHART_API_URL.format(symbol=base)
            params = {"q": "Quarterly Results", "consolidated": "true"}
            headers = {**DEFAULT_HEADERS, "X-Requested-With": "XMLHttpRequest"}
            r = requests.get(api_url, params=params, headers=headers, timeout=10)

            if r.status_code == 200:
                data = r.json()
                datasets = data.get("datasets", [])

                # Build a map: metric_name -> [(timestamp, value), ...]
                metric_map = {}
                for ds in datasets:
                    label = ds.get("label", "")
                    values = ds.get("values", [])
                    metric_map[label] = values

                # Get the number of quarters from the Revenue/Sales dataset
                revenue_data = metric_map.get("Sales") or metric_map.get("Revenue", [])
                if revenue_data:
                    # Take last MAX_QUARTERS entries
                    num_points = min(len(revenue_data), MAX_QUARTERS)
                    for i in range(-num_points, 0):
                        try:
                            timestamp_ms = revenue_data[i][0]
                            from datetime import datetime
                            dt = datetime.fromtimestamp(timestamp_ms / 1000)
                            quarter_label = dt.strftime("%b %Y")

                            rev = revenue_data[i][1] if i < len(revenue_data) else 0
                            exp_data = metric_map.get("Expenses", [])
                            exp = exp_data[i][1] if exp_data and abs(i) <= len(exp_data) else 0
                            opm_data = metric_map.get("OPM %", [])
                            opm = opm_data[i][1] if opm_data and abs(i) <= len(opm_data) else 0
                            np_data = metric_map.get("Net Profit", [])
                            np_val = np_data[i][1] if np_data and abs(i) <= len(np_data) else 0
                            eps_data = metric_map.get("EPS", [])
                            eps = eps_data[i][1] if eps_data and abs(i) <= len(eps_data) else 0

                            results.append(QuarterlyResult(
                                quarter=quarter_label,
                                revenue=rev,
                                expenses=exp,
                                operating_profit=rev - exp if rev and exp else 0,
                                opm_percent=opm,
                                net_profit=np_val,
                                eps=eps,
                            ))
                        except (IndexError, TypeError):
                            continue

                    if results:
                        return results
        except Exception as e:
            print(f"[ScreenerProvider] Chart API fallback: {e}")

        # Strategy 2: HTML table scraping
        try:
            df = self.fetch_quarterly_results_df(symbol)
            if not df.empty:
                # Parse the DataFrame rows into QuarterlyResult objects
                quarters = [c for c in df.columns if c != "Quarterly Metric"]
                for q in quarters[-MAX_QUARTERS:]:
                    try:
                        def _val(metric_name):
                            row = df[df["Quarterly Metric"].str.contains(metric_name, case=False, na=False)]
                            if not row.empty:
                                v = str(row.iloc[0][q]).replace(",", "").replace("%", "").strip()
                                return float(v) if v and v != "nan" else 0.0
                            return 0.0

                        results.append(QuarterlyResult(
                            quarter=q,
                            revenue=_val("Sales"),
                            expenses=_val("Expenses"),
                            operating_profit=_val("Operating Profit"),
                            opm_percent=_val("OPM"),
                            other_income=_val("Other Income"),
                            interest=_val("Interest"),
                            depreciation=_val("Depreciation"),
                            profit_before_tax=_val("Profit before tax"),
                            tax_percent=_val("Tax"),
                            net_profit=_val("Net Profit"),
                            eps=_val("EPS"),
                        ))
                    except Exception:
                        continue
        except Exception as e:
            print(f"[ScreenerProvider] HTML scraping error: {e}")

        return results

    def fetch_quarterly_results_df(self, symbol: str) -> pd.DataFrame:
        """Scrape the raw quarterly results HTML table as a DataFrame for display."""
        return self._scrape_section_table(symbol, "quarters", "Quarterly Metric")

    def fetch_cashflow_df(self, symbol: str) -> pd.DataFrame:
        """Scrape the annual cash flow statement table from Screener.in."""
        return self._scrape_section_table(symbol, "cash-flow", "Cash Flow Metric")

    def fetch_balance_sheet_df(self, symbol: str) -> pd.DataFrame:
        """Scrape the annual/quarterly balance sheet table from Screener.in."""
        return self._scrape_section_table(symbol, "balance-sheet", "Balance Sheet Metric")

    def fetch_profit_loss_df(self, symbol: str) -> pd.DataFrame:
        """Scrape the annual profit & loss statement table from Screener.in."""
        return self._scrape_section_table(symbol, "profit-loss", "Profit & Loss Metric")

    def _scrape_section_table(self, symbol: str, section_id: str, first_col_name: str) -> pd.DataFrame:
        """Generic method to scrape any Screener.in section table by its HTML id."""
        base = _strip_suffix(symbol)
        url = SCREENER_COMPANY_URL.format(symbol=base)

        try:
            r = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
            if r.status_code == 404:
                from providers.bse_provider import BSEProvider
                scrip_code = BSEProvider.get_bse_scrip_code(symbol)
                if scrip_code:
                    fallback_url = SCREENER_COMPANY_URL.format(symbol=scrip_code)
                    r = requests.get(fallback_url, headers=DEFAULT_HEADERS, timeout=15)

            if r.status_code != 200:
                return pd.DataFrame()

            soup = BeautifulSoup(r.text, "lxml")
            section = soup.find("section", id=section_id)
            if not section:
                return pd.DataFrame()

            table = section.find("table")
            if not table:
                return pd.DataFrame()

            clean_table = self._clean_html_table(table)
            dfs = pd.read_html(io.StringIO(str(clean_table)))
            df = dfs[0]
            df = df.rename(columns={df.columns[0]: first_col_name})
            df = df[df[first_col_name] != "Raw PDF"]
            return df

        except Exception as e:
            print(f"[ScreenerProvider] {section_id} table error: {e}")
            return pd.DataFrame()

    def download_transcript_text(self, url: str, max_pages: int = MAX_TRANSCRIPT_PAGES) -> str:
        """Download a transcript from url — supports both PDF and HTML formats."""
        try:
            r = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
            if r.status_code != 200:
                print(f"[ScreenerProvider] HTTP error {r.status_code} downloading transcript from {url}")
                return ""

            content_type = r.headers.get("content-type", "").lower()

            # Route to appropriate extractor based on content type
            if "pdf" in content_type or url.lower().endswith(".pdf"):
                return self._extract_pdf_transcript(r.content, url, max_pages)
            elif "html" in content_type or "text" in content_type:
                return self._extract_html_transcript(r.text, url)
            else:
                # Try PDF first (some servers don't set content-type correctly)
                try:
                    return self._extract_pdf_transcript(r.content, url, max_pages)
                except Exception:
                    # Fall back to HTML extraction
                    try:
                        return self._extract_html_transcript(r.text, url)
                    except Exception:
                        print(f"[ScreenerProvider] Unable to extract transcript from {url} (Content-Type: {content_type})")
                        return ""

        except Exception as e:
            print(f"[ScreenerProvider] Transcript download error for {url}: {e}")
            return ""

    def _extract_pdf_transcript(self, content: bytes, url: str, max_pages: int) -> str:
        """Extract text from a PDF transcript. Falls back to HTML if response is HTML."""
        if content.strip().startswith((b"<!DOC", b"<!doc", b"<html", b"<HTML")):
            try:
                return self._extract_html_transcript(content.decode("utf-8", errors="ignore"), url)
            except Exception:
                pass

        try:
            reader = PdfReader(io.BytesIO(content))
        except Exception as pdf_err:
            print(f"[ScreenerProvider] Failed to parse PDF bytes from {url}: {pdf_err}")
            # Final fallback to HTML extraction
            try:
                return self._extract_html_transcript(content.decode("utf-8", errors="ignore"), url)
            except Exception:
                return ""

        text_lines = []

        start_page = 0
        end_page = min(len(reader.pages), start_page + max_pages)

        boilerplate_patterns = [
            r"ladies and gentlemen",
            r"listen-only mode",
            r"listen only mode",
            r"all participants.*listen-only",
            r"all participant lines.*listen-only",
            r"operator instructions",
            r"to ask a question",
            r"press star",
            r"press \*",
            r"press 1",
            r"press zero",
            r"raise your hand",
            r"your line has been unmuted",
            r"line is in the talk mode",
            r"we will wait for a moment",
            r"take the next question",
            r"the next question is from",
            r"we have the next question",
            r"thank you for joining",
            r"please go ahead",
            r"safe harbor statement",
            r"forward-looking statement",
            r"forward looking statement",
            r"i now hand the conference",
            r"i now hand over",
            r"hand the conference over",
            r"over to you,? sir",
            r"chorus call",
            r"page \d+ of \d+",
            r"page \d+",
            r"registered office",
            r"corporate identity number",
            r"cin\s*:",
        ]
        boilerplate_regex = re.compile("|".join(boilerplate_patterns), re.IGNORECASE)

        for page_idx in range(start_page, end_page):
            page = reader.pages[page_idx]
            page_text = page.extract_text()
            if not page_text:
                continue

            for line in page_text.splitlines():
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                if len(line_stripped) < 15 and not any(c.isdigit() for c in line_stripped):
                    continue
                if boilerplate_regex.search(line_stripped):
                    continue
                line_clean = re.sub(r"\s+", " ", line_stripped)
                line_clean = re.sub(r"^[\-\u2022\*\s]+", "", line_clean).strip()
                if line_clean:
                    text_lines.append(line_clean)

        full_text = "\n".join(text_lines)
        return full_text[:MAX_TRANSCRIPT_CHARS]

    def _extract_html_transcript(self, html_content: str, url: str) -> str:
        """
        Extract transcript text from an HTML page.
        Strips navigation, footers, sidebars, and other non-content elements.
        """
        try:
            soup = BeautifulSoup(html_content, "lxml")

            # Remove non-content elements
            for tag in soup.find_all(["script", "style", "nav", "footer", "header",
                                      "aside", "iframe", "noscript", "form"]):
                tag.decompose()

            # Remove elements by common CSS class/id patterns for navigation/ads
            for selector in ["#sidebar", "#footer", "#header", "#nav", "#menu",
                            ".sidebar", ".footer", ".header", ".nav", ".menu",
                            ".advertisement", ".ad", ".social-share", ".cookie",
                            ".breadcrumb", ".pagination"]:
                for el in soup.select(selector):
                    el.decompose()

            # Try to find the main content area
            content_area = None
            # Look for common transcript container patterns
            for selector in [
                "article", "main", ".transcript", "#transcript",
                ".content", "#content", ".article-body", ".post-content",
                ".entry-content", ".document-content",
            ]:
                content_area = soup.select_one(selector)
                if content_area:
                    break

            # Fall back to body if no specific content area found
            if not content_area:
                content_area = soup.find("body")
            if not content_area:
                content_area = soup

            # Extract text, preserving paragraph structure
            text_parts = []
            for element in content_area.find_all(["p", "div", "span", "li", "td", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"]):
                text = element.get_text(strip=True)
                if text and len(text) >= 10:
                    text_parts.append(text)

            # If structured extraction yielded little, fall back to get_text
            if len(text_parts) < 5:
                raw_text = content_area.get_text(separator="\n", strip=True)
                text_parts = [line.strip() for line in raw_text.split("\n") if line.strip() and len(line.strip()) >= 10]

            full_text = "\n".join(text_parts)

            if len(full_text) < 200:
                print(f"[ScreenerProvider] HTML transcript too short ({len(full_text)} chars) from {url}")
                return ""

            return full_text[:MAX_TRANSCRIPT_CHARS]

        except Exception as e:
            print(f"[ScreenerProvider] HTML extraction error for {url}: {e}")
            return ""

    @staticmethod
    def _clean_html_table(table_soup):
        """Clean up Screener.in table HTML for pandas parsing."""
        clean = copy.deepcopy(table_soup)
        for row in clean.find_all("tr"):
            for cell in row.find_all(["td", "th"]):
                text = cell.get_text(strip=True)
                text = text.replace(" +", "").replace("+", "")
                if not text and cell.find("a"):
                    text = "PDF"
                cell.string = text
        return clean
