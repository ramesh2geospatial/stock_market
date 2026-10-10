"""
Empirical verification harness for Milestone 2 - MultiSourceDocFetcher & documents_index.
Run by Challenger 2.
"""
import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.stock import UnifiedDocument, DocumentLink
from providers.multi_source_doc_fetcher import MultiSourceDocFetcher, normalize_quarter_label
from storage.sqlite_store import SQLiteStore


class EmpiricalM2Test(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_m2.db"
        self.docs_dir = Path(self.temp_dir) / "documents"
        self.db_store = SQLiteStore(db_path=self.db_path)
        self.fetcher = MultiSourceDocFetcher(
            db_store=self.db_store,
            docs_base_dir=self.docs_dir
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # 1. Deduplication Verification
    # -------------------------------------------------------------
    def test_dedup_cross_source_priority(self):
        """Verify BSE > SCREENER > NSE priority when duplicate documents exist."""
        doc_bse = UnifiedDocument(
            symbol="RELIANCE",
            quarter="Q1 FY26",
            title="Reliance Concall Transcript Q1 FY26",
            url="https://www.bseindia.com/rel_bse.pdf",
            source_used="BSE",
            category="transcript",
        )
        doc_screener = UnifiedDocument(
            symbol="RELIANCE",
            quarter="Q1 FY26",
            title="Reliance Concall Transcript Q1 FY26",
            url="https://www.screener.in/rel_scr.pdf",
            source_used="SCREENER",
            category="transcript",
        )
        doc_nse = UnifiedDocument(
            symbol="RELIANCE",
            quarter="Q1 FY26",
            title="Reliance Concall Transcript Q1 FY26",
            url="https://nseindia.com/rel_nse.pdf",
            source_used="NSE",
            category="transcript",
        )

        deduped = self.fetcher.deduplicate_documents([doc_nse, doc_screener, doc_bse])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].source_used, "BSE")

    def test_dedup_multiple_distinct_docs_same_category(self):
        """
        EMPIRICAL CHECK: Verify if multiple distinct documents in the same quarter & category
        (e.g., Earnings Call Transcript AND Investor Call Transcript, or Unaudited vs Audited Results)
        are preserved or accidentally dropped by key_coarse = (symbol, norm_q, category).
        """
        doc1 = UnifiedDocument(
            symbol="TCS",
            quarter="Q1 FY26",
            title="TCS Q1 FY26 Concall Transcript - Main Call",
            url="https://www.bseindia.com/tcs_main.pdf",
            source_used="BSE",
            category="transcript",
        )
        doc2 = UnifiedDocument(
            symbol="TCS",
            quarter="Q1 FY26",
            title="TCS Q1 FY26 Analyst Meet Transcript - Strategic Briefing",
            url="https://www.bseindia.com/tcs_analyst.pdf",
            source_used="BSE",
            category="transcript",
        )

        deduped = self.fetcher.deduplicate_documents([doc1, doc2])
        # If coarse dedup drops distinct docs of same category, len(deduped) will be 1 instead of 2
        print(f"\n[Empirical Check] Deduplication count for 2 distinct transcripts in same quarter: {len(deduped)}")
        self.assertEqual(len(deduped), 2, "Multiple distinct documents in same quarter/category should NOT be dropped")

    def test_quarter_normalization(self):
        """Test quarter label normalizations."""
        self.assertEqual(normalize_quarter_label("Jul 2025"), "Q1 FY26")
        self.assertEqual(normalize_quarter_label("May 2026"), "Q4 FY26")
        self.assertEqual(normalize_quarter_label("Q1 FY26"), "Q1 FY26")
        self.assertEqual(normalize_quarter_label("Q4 FY2026"), "Q4 FY26")
        self.assertEqual(normalize_quarter_label("Oct 2025"), "Q2 FY26")
        self.assertEqual(normalize_quarter_label("Jan 2026"), "Q3 FY26")
        self.assertEqual(normalize_quarter_label("Dec 2025"), "Q3 FY26")
        self.assertEqual(normalize_quarter_label(""), "Unknown")

    # -------------------------------------------------------------
    # 2. Local File Caching & SQLite Storage Verification
    # -------------------------------------------------------------
    @patch("requests.get")
    def test_local_file_caching_and_sqlite(self, mock_get):
        """Verify downloading saves to data/documents/{symbol}/{quarter}/ and indexes in SQLite."""
        pdf_bytes = b"%PDF-1.4 Mock PDF Document Content"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = pdf_bytes
        mock_get.return_value = mock_resp

        doc = UnifiedDocument(
            symbol="INFY.NS",
            quarter="Q2 FY26",
            title="Infosys Q2 FY26 Results",
            url="https://www.bseindia.com/infy_q2.pdf",
            source_used="BSE",
            category="financial_results",
        )

        saved_doc = self.fetcher.download_and_store(doc)

        self.assertEqual(saved_doc.extraction_status, "success")
        self.assertIsNotNone(saved_doc.local_path)
        
        # Verify file path structure: data/documents/INFY.NS/Q2 FY26/financial_results_BSE_...pdf
        expected_dir = self.docs_dir / "INFY.NS" / "Q2 FY26"
        self.assertTrue(expected_dir.exists(), f"Directory {expected_dir} should exist")
        self.assertTrue(Path(saved_doc.local_path).exists())
        
        # Verify file size and checksum
        self.assertEqual(saved_doc.file_size_bytes, len(pdf_bytes))
        import hashlib
        self.assertEqual(saved_doc.checksum, hashlib.md5(pdf_bytes).hexdigest())

        # Verify SQLite documents_index persistence
        indexed = self.db_store.get_documents_by_symbol_and_quarter("INFY.NS", "Q2 FY26")
        self.assertEqual(len(indexed), 1)
        self.assertEqual(indexed[0]["checksum"], saved_doc.checksum)
        self.assertEqual(indexed[0]["extraction_status"], "success")

    def test_sqlite_db_cache_lookup(self):
        """Verify fetch_documents uses SQLite documents_index when force_refresh=False."""
        doc = UnifiedDocument(
            symbol="TCS",
            quarter="Q1 FY26",
            title="TCS Q1 FY26 Transcript",
            url="https://www.bseindia.com/tcs.pdf",
            source_used="BSE",
            category="transcript",
        )
        self.db_store.save_document_index(doc)

        # Mocks for providers
        self.fetcher.bse.fetch_documents = MagicMock()

        # Call with force_refresh=False
        docs = self.fetcher.fetch_documents("TCS", force_refresh=False)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].title, "TCS Q1 FY26 Transcript")
        self.fetcher.bse.fetch_documents.assert_not_called()

    # -------------------------------------------------------------
    # 3. Edge Case Handling Verification
    # -------------------------------------------------------------
    @patch("requests.get")
    def test_edge_case_http_error_404(self, mock_get):
        """Verify download_and_store handles HTTP errors cleanly."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = Exception("404 Client Error: Not Found")
        mock_get.return_value = mock_resp

        doc = UnifiedDocument(
            symbol="WIPRO",
            quarter="Q1 FY26",
            title="Missing Doc",
            url="https://www.bseindia.com/missing.pdf",
            source_used="BSE",
            category="transcript",
        )

        saved_doc = self.fetcher.download_and_store(doc)
        self.assertEqual(saved_doc.extraction_status, "failed")

    @patch("requests.get")
    def test_edge_case_corrupted_pdf_header(self, mock_get):
        """
        EMPIRICAL CHECK: What happens when server returns 200 OK with HTML error page
        instead of valid PDF binary? Check if header validation exists.
        """
        html_error = b"<html><body>Access Denied / Soft 404</body></html>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = html_error
        mock_get.return_value = mock_resp

        doc = UnifiedDocument(
            symbol="SBIN",
            quarter="Q1 FY26",
            title="SBI Presentation",
            url="https://www.bseindia.com/sbi_presentation.pdf",
            source_used="BSE",
            category="presentation",
        )

        saved_doc = self.fetcher.download_and_store(doc)
        print(f"\n[Empirical Check] Corrupted/HTML PDF response status: {saved_doc.extraction_status}, local_path ext: {saved_doc.local_path}")
        
        # Check if saved file starts with %PDF- magic header
        if saved_doc.local_path and Path(saved_doc.local_path).exists():
            with open(saved_doc.local_path, "rb") as f:
                header = f.read(4)
            print(f"[Empirical Check] Saved file header magic bytes: {header}")
            is_valid_pdf = header.startswith(b"%PDF")
            print(f"[Empirical Check] Is valid PDF magic header? {is_valid_pdf}")

    def test_edge_case_empty_url(self):
        """Verify handling of document with no URL."""
        doc = UnifiedDocument(
            symbol="TATAMOTORS",
            quarter="Q1 FY26",
            title="No URL Doc",
            url="",
            source_used="BSE",
            category="transcript",
        )
        saved_doc = self.fetcher.download_and_store(doc)
        self.assertEqual(saved_doc.url, "")


if __name__ == "__main__":
    unittest.main()
