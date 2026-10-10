"""
Unit tests for MFHoldingsSyncService — Incremental sync orchestrator.
"""
import unittest
from unittest.mock import MagicMock

from services.mf_sync_service import MFHoldingsSyncService


class TestMFHoldingsSyncService(unittest.TestCase):

    def setUp(self):
        self.mock_provider = MagicMock()
        self.mock_store = MagicMock()
        self.sync_service = MFHoldingsSyncService(
            provider=self.mock_provider,
            store=self.mock_store
        )

    def test_sync_schemes_success(self):
        self.mock_store.get_last_sync_time.return_value = None
        self.mock_provider.fetch_mf_schemes.return_value = [
            {"scheme_id": 101, "scheme_name": "Test Fund", "amc_name": "Test AMC"}
        ]
        self.mock_store.save_mf_schemes_cache.return_value = 1

        result = self.sync_service.sync_schemes()
        self.assertEqual(result["synced"], 1)
        self.assertEqual(result["status"], "success")
        self.mock_store.set_last_sync_time.assert_called_once()

    def test_sync_schemes_no_new_data(self):
        self.mock_store.get_last_sync_time.return_value = "2026-07-10T00:00:00Z"
        self.mock_provider.fetch_mf_schemes.return_value = []

        result = self.sync_service.sync_schemes()
        self.assertEqual(result["synced"], 0)
        self.assertEqual(result["status"], "no_new_data")

    def test_sync_holdings_success(self):
        self.mock_store.get_last_sync_time.return_value = None
        self.mock_provider.fetch_all_holdings_paginated.return_value = [
            {"scheme_id": 101, "symbol": "RELIANCE.NS", "shares_held": 1000000}
        ]
        self.mock_store.save_mf_holdings_cache.return_value = 1
        self.mock_store.get_mf_holdings_count.return_value = 1

        result = self.sync_service.sync_holdings()
        self.assertEqual(result["synced"], 1)
        self.assertEqual(result["status"], "success")

    def test_sync_holdings_incremental(self):
        self.mock_store.get_last_sync_time.return_value = "2026-07-10T00:00:00Z"
        self.mock_provider.fetch_all_holdings_paginated.return_value = []
        self.mock_store.get_mf_holdings_count.return_value = 50

        result = self.sync_service.sync_holdings()
        self.assertEqual(result["status"], "no_new_data")
        self.mock_provider.fetch_all_holdings_paginated.assert_called_with(
            last_synced_at="2026-07-10T00:00:00Z"
        )

    def test_sync_all_orchestrates_correctly(self):
        self.mock_store.get_last_sync_time.return_value = None
        self.mock_provider.fetch_mf_schemes.return_value = [{"scheme_id": 101}]
        self.mock_provider.fetch_all_holdings_paginated.return_value = [{"symbol": "TCS.NS"}]
        self.mock_store.save_mf_schemes_cache.return_value = 1
        self.mock_store.save_mf_holdings_cache.return_value = 1
        self.mock_store.get_mf_holdings_count.return_value = 1

        result = self.sync_service.sync_all()
        self.assertIn("schemes", result)
        self.assertIn("holdings", result)
        self.assertIn("summary", result)
        self.assertEqual(result["summary"]["status"], "success")

    def test_sync_all_force_full(self):
        self.mock_store.get_last_sync_time.return_value = "2026-07-10T00:00:00Z"
        self.mock_provider.fetch_mf_schemes.return_value = []
        self.mock_provider.fetch_all_holdings_paginated.return_value = []
        self.mock_store.get_mf_holdings_count.return_value = 0

        result = self.sync_service.sync_all(force_full=True)
        # When force_full=True, last_synced_at should be None
        self.mock_provider.fetch_mf_schemes.assert_called_with(last_synced_at=None)
        self.mock_provider.fetch_all_holdings_paginated.assert_called_with(last_synced_at=None)

    def test_get_sync_status(self):
        self.mock_store.get_sync_status.return_value = [
            {"table_name": "mf_stock_holdings", "last_synced_at": "2026-07-10T00:00:00Z", "row_count": 50}
        ]
        self.mock_store.get_mf_holdings_count.return_value = 50
        self.mock_store.get_mf_schemes_cache.return_value = [{"scheme_id": 101}]
        self.mock_store.get_mf_holdings_available_dates.return_value = ["2026-07-31"]
        self.mock_provider.is_configured.return_value = True

        status = self.sync_service.get_sync_status()
        self.assertEqual(status["total_holdings_cached"], 50)
        self.assertTrue(status["is_configured"])

    def test_needs_sync_when_never_synced(self):
        self.mock_store.get_last_sync_time.return_value = None
        self.assertTrue(self.sync_service.needs_sync())

    def test_sync_handles_provider_error(self):
        self.mock_store.get_last_sync_time.return_value = None
        self.mock_provider.fetch_mf_schemes.side_effect = Exception("Network error")

        result = self.sync_service.sync_schemes()
        self.assertEqual(result["status"], "error")
        self.assertIn("Network error", result["error"])


if __name__ == '__main__':
    unittest.main()
