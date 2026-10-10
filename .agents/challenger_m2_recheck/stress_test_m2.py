"""
Empirical Stress Test Harness for Milestone 2 Remediation Fixes
Tests all 6 remediated edge cases against real/mocked inputs.
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import pandas as pd

from models.stock import UnifiedDocument, DocumentLink
from providers.multi_source_doc_fetcher import MultiSourceDocFetcher, normalize_quarter_label
from providers.screener_provider import ScreenerProvider
from providers.bse_provider import BSEProvider
from storage.sqlite_store import SQLiteStore


class TestMilestone2RemediationFixes(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test.db"
        self.docs_dir = Path(self.tmp_dir) / "data" / "documents"
        self.store = SQLiteStore(str(self.db_path))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # --- Fix 1: Deduplication retaining distinct filings in the same quarter ---
    def test_fix1_deduplication_retains_distinct_filings_in_same_quarter(self):
        fetcher = MultiSourceDocFetcher(db_store=self.store, docs_base_dir=self.docs_dir)

        doc1 = UnifiedDocument(
            symbol="RELIANCE",
            quarter="Q3 FY25",
            title="Analyst Meet Transcript",
            url="https://bseindia.com/xml-data/corpfiling/AttachLive/doc1.pdf",
            source_used="BSE",
            category="transcript"
        )
        doc2 = UnifiedDocument(
            symbol="RELIANCE",
            quarter="Q3 FY25",
            title="Concall Transcript Q3",
            url="https://bseindia.com/xml-data/corpfiling/AttachLive/doc2.pdf",
            source_used="BSE",
            category="transcript"
        )
        # Duplicate of doc1 from Screener
        doc3 = UnifiedDocument(
            symbol="RELIANCE",
            quarter="Q3 FY25",
            title="Analyst Meet Transcript",
            url="https://screener.in/company/doc1.pdf",
            source_used="SCREENER",
            category="transcript"
        )

        deduped = fetcher.deduplicate_documents([doc1, doc2, doc3])
        
        self.assertEqual(len(deduped), 2, f"Expected 2 distinct filings retained, got {len(deduped)}")
        titles = [d.title for d in deduped]
        self.assertIn("Analyst Meet Transcript", titles)
        self.assertIn("Concall Transcript Q3", titles)
        # Verify BSE source was prioritized over Screener for doc1
        doc1_ret = [d for d in deduped if d.title == "Analyst Meet Transcript"][0]
        self.assertEqual(doc1_ret.source_used, "BSE")
        print("[PASS] Fix 1: Deduplication correctly retains distinct filings in the same quarter.")

    # --- Fix 2: PDF magic bytes validation and soft-404 handling ---
    @patch("requests.get")
    def test_fix2_pdf_magic_bytes_validation_and_soft404(self, mock_get):
        fetcher = MultiSourceDocFetcher(db_store=self.store, docs_base_dir=self.docs_dir)

        # Sub-test 2A: Soft 404 HTML body returning 200 OK
        doc_html_soft404 = UnifiedDocument(
            symbol="TCS",
            quarter="Q3 FY25",
            title="Q3 Transcript",
            url="https://example.com/fake_transcript.pdf",
            source_used="BSE",
            category="transcript"
        )

        mock_resp_html = MagicMock()
        mock_resp_html.status_code = 200
        mock_resp_html.content = b"<html><head><title>404 Not Found</title></head><body>File not found</body></html>"
        mock_resp_html.raise_for_status.return_value = None
        mock_get.return_value = mock_resp_html

        res_doc = fetcher.download_and_store(doc_html_soft404)
        self.assertEqual(res_doc.extraction_status, "failed")
        self.assertIsNone(res_doc.local_path)
        print("[PASS] Fix 2A: Soft-404 HTML response flagged as extraction failed and not saved.")

        # Sub-test 2B: Genuine PDF content starting with %PDF-
        doc_real_pdf = UnifiedDocument(
            symbol="TCS",
            quarter="Q3 FY25",
            title="Q3 Valid Transcript",
            url="https://example.com/valid_transcript.pdf",
            source_used="BSE",
            category="transcript"
        )
        mock_resp_pdf = MagicMock()
        mock_resp_pdf.status_code = 200
        mock_resp_pdf.content = b"%PDF-1.4\n1 0 obj\n<< /Title (Test) >>\nendobj\n%%EOF"
        mock_resp_pdf.raise_for_status.return_value = None
        mock_get.return_value = mock_resp_pdf

        res_pdf_doc = fetcher.download_and_store(doc_real_pdf)
        self.assertEqual(res_pdf_doc.extraction_status, "success")
        self.assertIsNotNone(res_pdf_doc.local_path)
        self.assertTrue(Path(res_pdf_doc.local_path).exists())
        self.assertTrue(Path(res_pdf_doc.local_path).read_bytes().startswith(b"%PDF-"))
        print("[PASS] Fix 2B: Genuine PDF bytes correctly saved and extraction_status set to downloaded.")

    # --- Fix 3: Category completeness check allowing Tier 2/3 fallbacks ---
    def test_fix3_category_completeness_fallback(self):
        mock_bse = MagicMock()
        mock_screener = MagicMock()
        mock_nse = MagicMock()

        fetcher = MultiSourceDocFetcher(
            db_store=self.store,
            docs_base_dir=self.docs_dir
        )
        fetcher.bse = mock_bse
        fetcher.screener = mock_screener
        fetcher.nse = mock_nse

        # Tier 1 returns ONLY financial_results (missing transcript & presentation)
        mock_bse.fetch_documents.return_value = [
            UnifiedDocument(symbol="INFY", quarter="Q3 FY25", title="Results Q3", url="http://bse/res.pdf", source_used="BSE", category="financial_results")
        ]

        # Tier 2 returns transcript
        mock_screener.fetch_documents.return_value = [
            DocumentLink(title="Concall Transcript Q3", url="http://screener/trans.pdf", category="transcript", date_hint="Q3 FY25")
        ]

        # Tier 3 returns presentation
        mock_nse.fetch_documents.return_value = [
            UnifiedDocument(symbol="INFY", quarter="Q3 FY25", title="Investor Presentation Q3", url="http://nse/pres.pdf", source_used="NSE", category="presentation")
        ]

        docs = fetcher.fetch_documents("INFY")

        self.assertTrue(mock_bse.fetch_documents.called)
        self.assertTrue(mock_screener.fetch_documents.called, "Tier 2 Screener should be called when transcript/presentation are missing from Tier 1")
        self.assertTrue(mock_nse.fetch_documents.called, "Tier 3 NSE should be called when presentation is still missing from Tier 1 + Tier 2")

        categories_found = {d.category for d in docs}
        self.assertIn("financial_results", categories_found)
        self.assertIn("transcript", categories_found)
        self.assertIn("presentation", categories_found)
        print("[PASS] Fix 3: Multi-tier fallback correctly invoked when Tier 1 only yields partial categories.")

    # --- Fix 4: Screener BSE scrip code fallback on HTTP 404 ---
    @patch("requests.get")
    @patch.object(BSEProvider, "get_bse_scrip_code")
    def test_fix4_screener_scrip_code_fallback_on_404(self, mock_scrip_code, mock_get):
        mock_scrip_code.return_value = "500570"
        screener = ScreenerProvider()

        # 1st call for TATAMOTORS -> 404
        resp_404 = MagicMock()
        resp_404.status_code = 404

        # 2nd call for 500570 -> 200 OK with HTML section id="documents"
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.text = """
        <section id="documents">
            <div class="documents sub">
                <h3>Transcripts</h3>
                <ul>
                    <li><a href="/doc/trans1.pdf">Concall Transcript Dec 2024</a></li>
                </ul>
            </div>
        </section>
        """

        mock_get.side_effect = [resp_404, resp_200]

        docs = screener.fetch_documents("TATAMOTORS")
        self.assertEqual(mock_get.call_count, 2)
        called_urls = [call.args[0] for call in mock_get.call_args_list]
        self.assertIn("https://www.screener.in/company/TATAMOTORS/", called_urls[0])
        self.assertIn("https://www.screener.in/company/500570/", called_urls[1])
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].category, "transcript")
        print("[PASS] Fix 4: Screener correctly falls back to BSE scrip code (500570) on HTTP 404.")

    # --- Fix 5: BSE API error response robustness ---
    def test_fix5_bse_api_error_response_robustness(self):
        bse = BSEProvider()

        # Case A: String error payload
        bse.fetch_announcements = MagicMock(return_value="500 Internal Server Error String")
        docs_a = bse.fetch_documents("RELIANCE")
        self.assertEqual(docs_a, [])

        # Case B: Non-list dictionary error payload
        bse.fetch_announcements = MagicMock(return_value={"error": "Access Denied"})
        docs_b = bse.fetch_documents("RELIANCE")
        self.assertEqual(docs_b, [])

        # Case C: List containing non-dict items mixed with valid dict
        bse.fetch_announcements = MagicMock(return_value=[
            "corrupted_line",
            None,
            123,
            {
                "HEADLINE": "Financial Results for Q3 FY25",
                "NEWSSUB": "Financial Results",
                "ATTACHMENTNAME": "res_q3.pdf",
                "NEWS_DT": "2025-01-15T10:00:00"
            }
        ])
        docs_c = bse.fetch_documents("RELIANCE")
        self.assertEqual(len(docs_c), 1)
        self.assertEqual(docs_c[0].category, "financial_results")
        print("[PASS] Fix 5: BSE Provider gracefully handles string errors, dict error payloads, and corrupted list items.")

    # --- Fix 6: Quarter label alignment for March filing dates ---
    def test_fix6_quarter_label_alignment_for_march(self):
        bse = BSEProvider()

        # March 15 filing date -> Q4 FY25
        q_bse_mar15 = bse.resolve_quarter_from_filing_date("2025-03-15T14:30:00")
        self.assertEqual(q_bse_mar15, "Q4 FY25", f"Expected Q4 FY25, got {q_bse_mar15}")

        # March 31 filing date -> Q4 FY25
        q_bse_mar31 = bse.resolve_quarter_from_filing_date("2025-03-31")
        self.assertEqual(q_bse_mar31, "Q4 FY25", f"Expected Q4 FY25, got {q_bse_mar31}")

        # Test normalize_quarter_label alignment for March dates
        q_norm_mar15 = normalize_quarter_label("15 Mar 2025")
        self.assertEqual(q_norm_mar15, "Q4 FY25")

        q_norm_mar_str = normalize_quarter_label("March 2025")
        self.assertEqual(q_norm_mar_str, "Q4 FY25")

        self.assertEqual(q_bse_mar15, q_norm_mar15, "BSE Provider and MultiSourceDocFetcher quarter mapping must match!")
        print("[PASS] Fix 6: March filing dates correctly map to Q4 FYyy in both BSEProvider and MultiSourceDocFetcher.")


if __name__ == "__main__":
    unittest.main()
