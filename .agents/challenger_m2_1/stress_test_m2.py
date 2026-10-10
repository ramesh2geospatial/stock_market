"""
Empirical Stress Verification Harness for Milestone 2 Multi-Source Document Ingestion Engine.
Tests BSEProvider, MultiSourceDocFetcher, and fallback logic under adverse conditions.
"""
import unittest
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import requests

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.stock import UnifiedDocument, DocumentLink
from providers.bse_provider import BSEProvider, NSE_TO_BSE_MAPPING
from providers.multi_source_doc_fetcher import MultiSourceDocFetcher, normalize_quarter_label
from storage.sqlite_store import SQLiteStore


class TestBSEProviderAdverseConditions(unittest.TestCase):

    def setUp(self):
        self.provider = BSEProvider(timeout=1)

    # --------------------------------------------------
    # Category A: Invalid Ticker Lookup & BSE Scrip Code
    # --------------------------------------------------

    def test_get_bse_scrip_code_missing_mapping(self):
        """Test tickers not present in hardcoded 50-stock mapping."""
        unmapped_symbols = ["ZOMATO", "PAYTM", "JIOFIN", "IRCTC", "TATAPOWER", "SUZLON", "NYKAA"]
        for sym in unmapped_symbols:
            scrip = self.provider.get_bse_scrip_code(sym)
            self.assertIsNone(scrip, f"Expected None for unmapped symbol {sym}, got {scrip}")

    def test_get_bse_scrip_code_edge_case_inputs(self):
        """Test invalid or whitespace-heavy inputs."""
        self.assertIsNone(self.provider.get_bse_scrip_code(""))
        self.assertIsNone(self.provider.get_bse_scrip_code("   "))
        self.assertIsNone(self.provider.get_bse_scrip_code("INVALID_TICKER_9999"))
        self.assertEqual(self.provider.get_bse_scrip_code("  hdfcbank.ns  "), "500180")
        self.assertEqual(self.provider.get_bse_scrip_code("500180"), "500180")

    def test_get_bse_scrip_code_non_string_crash(self):
        """Test non-string inputs (e.g. integer, None)."""
        with self.assertRaises(AttributeError):
            self.provider.get_bse_scrip_code(123456) # type: ignore

    # --------------------------------------------------
    # Category B: BSE API Network Failures & Adverse HTTP
    # --------------------------------------------------

    @patch("requests.get")
    def test_fetch_announcements_network_timeout(self, mock_get):
        """Network timeout during BSE API request."""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        res = self.provider.fetch_announcements("500180")
        self.assertEqual(res, [])

    @patch("requests.get")
    def test_fetch_announcements_http_500_error(self, mock_get):
        """Server returns 500 Internal Server Error."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_get.return_value = mock_resp
        res = self.provider.fetch_announcements("500180")
        self.assertEqual(res, [])

    @patch("requests.get")
    def test_fetch_announcements_connection_refused(self, mock_get):
        """Connection refused by remote host."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        res = self.provider.fetch_announcements("500180")
        self.assertEqual(res, [])

    # --------------------------------------------------
    # Category C: Malformed JSON / HTML Responses from BSE
    # --------------------------------------------------

    @patch("requests.get")
    def test_fetch_announcements_html_returned_instead_of_json(self, mock_get):
        """BSE API returns HTML Cloudflare page with 200 OK status."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)
        mock_get.return_value = mock_resp
        res = self.provider.fetch_announcements("500180")
        self.assertEqual(res, [])

    @patch("requests.get")
    def test_fetch_announcements_malformed_dict_structure(self, mock_get):
        """BSE API returns dict where Table is a string or integer instead of list."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"Table": "Server maintenance error text"}
        mock_get.return_value = mock_resp
        res = self.provider.fetch_announcements("500180")
        self.assertEqual(res, "Server maintenance error text")

    @patch("providers.bse_provider.BSEProvider.fetch_announcements")
    def test_fetch_documents_crash_on_malformed_table_string(self, mock_fetch_ann):
        """CRASH TEST: fetch_documents throws AttributeError if fetch_announcements returns non-list (e.g. string or dict without list)."""
        mock_fetch_ann.return_value = "Server maintenance error text"
        try:
            docs = self.provider.fetch_documents("HDFCBANK")
            self.fail("Expected Exception or graceful handle, but crash might occur")
        except AttributeError as e:
            print(f"\n[BUG CONFIRMED] fetch_documents crashed on string announcements: {e}")

    @patch("providers.bse_provider.BSEProvider.fetch_announcements")
    def test_fetch_documents_crash_on_list_of_ints(self, mock_fetch_ann):
        """CRASH TEST: fetch_documents throws AttributeError if fetch_announcements returns list of ints/strings."""
        mock_fetch_ann.return_value = [123, 456]
        try:
            docs = self.provider.fetch_documents("HDFCBANK")
            self.fail("Expected Exception or graceful handle, but crash occurred")
        except AttributeError as e:
            print(f"\n[BUG CONFIRMED] fetch_documents crashed on list of ints: {e}")

    # --------------------------------------------------
    # Category D: Missing Fields in Announcement JSON
    # --------------------------------------------------

    @patch("providers.bse_provider.BSEProvider.fetch_announcements")
    def test_fetch_documents_missing_headline_and_attachment(self, mock_fetch_ann):
        """Announcements with missing/None fields."""
        mock_fetch_ann.return_value = [
            {"SCRIP_CD": "500180", "HEADLINE": None, "ATTACHMENTNAME": None},
            {"SCRIP_CD": "500180", "HEADLINE": "Concall Transcript", "ATTACHMENTNAME": "valid.pdf", "NEWS_DT": None},
        ]
        docs = self.provider.fetch_documents("HDFCBANK")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].url, "https://www.bseindia.com/xml-data/corpfiling/AttachLive/valid.pdf")
        self.assertEqual(docs[0].quarter, "Unknown")


class TestMultiSourceDocFetcherAdverseConditions(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_m2.db"
        self.db = SQLiteStore(db_path=self.db_path)
        self.fetcher = MultiSourceDocFetcher(db_store=self.db, docs_base_dir=Path(self.temp_dir.name) / "documents")

    def tearDown(self):
        self.temp_dir.cleanup()

    # --------------------------------------------------
    # Category E: Quarter Normalization Edge Cases & Month Mismatches
    # --------------------------------------------------

    def test_quarter_normalization_mismatch(self):
        """Check quarter calculation boundary months (March, June, Sept, Dec)."""
        # March 2026: BSE Provider vs MultiSourceDocFetcher
        bse_provider = BSEProvider()
        bse_q = bse_provider.resolve_quarter_from_filing_date("2026-03-15T00:00:00")
        fetcher_q = normalize_quarter_label("15 Mar 2026")

        print(f"\n[MONTH MATCH CHECK] March 2026 -> BSE Provider: '{bse_q}', MultiSourceFetcher: '{fetcher_q}'")
        self.assertEqual(bse_q, fetcher_q, f"Mismatch for March: BSE Provider got {bse_q}, MultiSource got {fetcher_q}")

    def test_normalize_quarter_label_garbage_input(self):
        """Test normalization on invalid or unexpected strings."""
        self.assertEqual(normalize_quarter_label(""), "Unknown")
        self.assertEqual(normalize_quarter_label("Random String 123"), "Random String 123")
        self.assertEqual(normalize_quarter_label("Q5 FY99"), "Q5 FY99")

    # --------------------------------------------------
    # Category F: Fallback Logic Under Chain Failures
    # --------------------------------------------------

    def test_fallback_when_tier1_raises_exception(self):
        """When BSE Provider raises an unhandled exception, system falls back to Tier 2 (Screener)."""
        self.fetcher.bse.fetch_documents = MagicMock(side_effect=RuntimeError("BSE Provider crash"))
        screener_doc = DocumentLink(title="Concall Transcript Q1 FY26", url="https://screener.in/t.pdf", category="transcript", date_hint="Jul 2025")
        self.fetcher.screener.fetch_documents = MagicMock(return_value=[screener_doc])
        self.fetcher.nse.fetch_documents = MagicMock(return_value=[])

        docs = self.fetcher.fetch_documents("HDFCBANK", force_refresh=True)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].source_used, "SCREENER")

    def test_fallback_when_tier1_and_tier2_raise_exceptions(self):
        """When BSE and Screener both crash, system falls back to Tier 3 (NSE)."""
        self.fetcher.bse.fetch_documents = MagicMock(side_effect=RuntimeError("BSE crash"))
        self.fetcher.screener.fetch_documents = MagicMock(side_effect=RuntimeError("Screener crash"))
        nse_doc = UnifiedDocument(symbol="HDFCBANK", quarter="Q1 FY26", title="NSE Transcript", url="https://nse.com/t.pdf", source_used="NSE", category="transcript")
        self.fetcher.nse.fetch_documents = MagicMock(return_value=[nse_doc])

        docs = self.fetcher.fetch_documents("HDFCBANK", force_refresh=True)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].source_used, "NSE")

    def test_fallback_when_all_tiers_fail(self):
        """When all 3 tiers raise exceptions or return empty, returns empty list without raising."""
        self.fetcher.bse.fetch_documents = MagicMock(side_effect=RuntimeError("BSE crash"))
        self.fetcher.screener.fetch_documents = MagicMock(side_effect=RuntimeError("Screener crash"))
        self.fetcher.nse.fetch_documents = MagicMock(side_effect=RuntimeError("NSE crash"))

        docs = self.fetcher.fetch_documents("HDFCBANK", force_refresh=True)
        self.assertEqual(docs, [])

    def test_fallback_for_unmapped_stock(self):
        """Unmapped BSE stock (e.g. ZOMATO) falls back to Screener/NSE automatically."""
        # ZOMATO returns None for scrip code, so BSEProvider returns []
        screener_doc = DocumentLink(title="Zomato Transcript Q1 FY26", url="https://screener.in/z.pdf", category="transcript", date_hint="Jul 2025")
        self.fetcher.screener.fetch_documents = MagicMock(return_value=[screener_doc])

        docs = self.fetcher.fetch_documents("ZOMATO", force_refresh=True)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].symbol, "ZOMATO")
        self.assertEqual(docs[0].source_used, "SCREENER")

    # --------------------------------------------------
    # Category G: Partial Tier 1 Coverage vs Complete Fallback
    # --------------------------------------------------

    def test_tier1_returns_only_financial_results_skips_screener_transcripts(self):
        """
        LOGICAL LIMITATION TEST:
        If BSE returns only 1 Financial Results document, all_docs is non-empty.
        Therefore Screener (Tier 2) is NEVER called, losing all Concall Transcripts!
        """
        bse_fin_doc = UnifiedDocument(
            symbol="HDFCBANK",
            quarter="Q1 FY26",
            title="Financial Results Q1 FY26",
            url="https://bse.com/fin.pdf",
            source_used="BSE",
            category="financial_results"
        )
        self.fetcher.bse.fetch_documents = MagicMock(return_value=[bse_fin_doc])

        screener_transcript_doc = DocumentLink(
            title="Concall Transcript Q1 FY26",
            url="https://screener.in/trans.pdf",
            category="transcript",
            date_hint="Jul 2025"
        )
        self.fetcher.screener.fetch_documents = MagicMock(return_value=[screener_transcript_doc])

        docs = self.fetcher.fetch_documents("HDFCBANK", force_refresh=True)
        categories = [d.category for d in docs]

        print(f"\n[PARTIAL COVERAGE OBSERVATION] Categories fetched when BSE has only financial results: {categories}")
        self.assertIn("financial_results", categories)
        # Verify that transcripts were missed because Screener was skipped
        self.assertNotIn("transcript", categories)

    # --------------------------------------------------
    # Category H: Document Downloader & File System Errors
    # --------------------------------------------------

    @patch("requests.get")
    def test_download_and_store_http_404(self, mock_get):
        """Downloader handles 404 Not Found error gracefully."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_resp

        doc = UnifiedDocument(
            symbol="INFY",
            quarter="Q1 FY26",
            title="Missing Transcript",
            url="https://bse.com/404.pdf",
            source_used="BSE",
            category="transcript"
        )

        res = self.fetcher.download_and_store(doc)
        self.assertEqual(res.extraction_status, "failed")

    @patch("requests.get")
    def test_download_and_store_empty_content(self, mock_get):
        """Downloader handles 200 OK with empty content."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b""
        mock_get.return_value = mock_resp

        doc = UnifiedDocument(
            symbol="INFY",
            quarter="Q1 FY26",
            title="Empty Transcript",
            url="https://bse.com/empty.pdf",
            source_used="BSE",
            category="transcript"
        )

        res = self.fetcher.download_and_store(doc)
        print(f"\n[DOWNLOAD EMPTY CHECK] status: {res.extraction_status}, checksum: {res.checksum}, size: {res.file_size_bytes}")
        self.assertEqual(res.extraction_status, "success")
        self.assertEqual(res.file_size_bytes, 0)
        self.assertEqual(res.checksum, "d41d8cd98f00b204e9800998ecf8427e")  # MD5 of b""


if __name__ == "__main__":
    unittest.main()
