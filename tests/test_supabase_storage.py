"""
Unit tests for SupabaseStorageProvider in Stock Market Platform:
- Endpoint configuration for target Supabase project https://nbyzclczjoxaemcckxne.supabase.co
- Public URL generation for stock concall PDFs & backups
- Stock document upload mock tests
"""
import unittest
from unittest.mock import patch, MagicMock

from providers.supabase_storage_provider import SupabaseStorageProvider


class TestSupabaseStorageProvider(unittest.TestCase):

    def setUp(self):
        self.target_url = "https://nbyzclczjoxaemcckxne.supabase.co"
        self.provider = SupabaseStorageProvider(
            supabase_url=self.target_url,
            supabase_key="test_anon_key",
            default_bucket="stock_documents"
        )

    def test_provider_configuration(self):
        """Verify provider targets the Supabase project URL."""
        self.assertTrue(self.provider.is_configured())
        self.assertEqual(self.provider.supabase_url, self.target_url)

    def test_public_url_generation(self):
        """Verify public URL formatting for uploaded stock concall PDFs."""
        url = self.provider.get_public_url("RELIANCE/Q1_FY26_Transcript.pdf")
        expected = "https://nbyzclczjoxaemcckxne.supabase.co/storage/v1/object/public/stock_documents/RELIANCE/Q1_FY26_Transcript.pdf"
        self.assertEqual(url, expected)

    @patch("urllib.request.urlopen")
    def test_upload_stock_document_success(self, mock_urlopen):
        """Verify stock PDF upload formatting and success response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = self.provider.upload_stock_document(b"fake_pdf_bytes", "RELIANCE/Q1_FY26_Transcript.pdf")
        self.assertTrue(res["success"])
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(
            res["public_url"],
            "https://nbyzclczjoxaemcckxne.supabase.co/storage/v1/object/public/stock_documents/RELIANCE/Q1_FY26_Transcript.pdf"
        )


if __name__ == "__main__":
    unittest.main()
