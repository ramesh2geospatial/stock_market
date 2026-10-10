"""
Unit tests for MFHoldingsProvider — Supabase PostgREST read provider and local query methods.
"""
import unittest
from unittest.mock import patch, MagicMock
import json

from providers.mf_holdings_provider import MFHoldingsProvider


class TestMFHoldingsProvider(unittest.TestCase):

    def setUp(self):
        self.provider = MFHoldingsProvider(
            supabase_url="https://test-project.supabase.co",
            supabase_key="test_anon_key_123"
        )

    def test_is_configured_with_valid_credentials(self):
        self.assertTrue(self.provider.is_configured())

    def test_is_configured_without_credentials(self):
        provider = MFHoldingsProvider(supabase_url="", supabase_key="")
        self.assertFalse(provider.is_configured())

    def test_get_headers_contains_auth(self):
        headers = self.provider._get_headers()
        self.assertEqual(headers["apikey"], "test_anon_key_123")
        self.assertIn("Bearer", headers["Authorization"])

    def test_build_query_params_with_filters(self):
        filters = {"symbol": "eq.RELIANCE.NS", "limit": "10", "unused": None}
        params = self.provider._build_query_params(filters)
        self.assertIn("symbol=eq.RELIANCE.NS", params)
        self.assertIn("limit=10", params)
        self.assertNotIn("unused", params)

    def test_build_query_params_empty(self):
        params = self.provider._build_query_params({})
        self.assertEqual(params, "")

    @patch('providers.mf_holdings_provider.urllib.request.urlopen')
    def test_fetch_with_retry_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([
            {"scheme_id": 101, "symbol": "RELIANCE.NS", "shares_held": 18200000}
        ]).encode('utf-8')
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = self.provider._fetch_with_retry("https://test.com/rest/v1/test")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["symbol"], "RELIANCE.NS")

    def test_fetch_returns_empty_when_not_configured(self):
        provider = MFHoldingsProvider(supabase_url="", supabase_key="")
        self.assertEqual(provider.fetch_mf_holdings(), [])
        self.assertEqual(provider.fetch_mf_schemes(), [])
        self.assertEqual(provider.fetch_index_stocks(), [])
        self.assertEqual(provider.fetch_available_dates(), [])

    def test_fetch_holdings_builds_correct_filters(self):
        with patch.object(self.provider, '_fetch_with_retry', return_value=[]) as mock_fetch:
            self.provider.fetch_mf_holdings(
                symbol="RELIANCE.NS",
                action_type="FRESH_ENTRY",
                as_of_date="2026-07-31"
            )
            called_url = mock_fetch.call_args[0][0]
            self.assertIn("symbol=eq.RELIANCE.NS", called_url)
            self.assertIn("action_type=eq.FRESH_ENTRY", called_url)
            self.assertIn("as_of_date=eq.2026-07-31", called_url)

    def test_fetch_holdings_incremental_sync_filter(self):
        with patch.object(self.provider, '_fetch_with_retry', return_value=[]) as mock_fetch:
            self.provider.fetch_mf_holdings(last_synced_at="2026-07-10T08:30:00Z")
            called_url = mock_fetch.call_args[0][0]
            self.assertIn("created_at=gt.2026-07-10T08:30:00Z", called_url)



if __name__ == '__main__':
    unittest.main()
