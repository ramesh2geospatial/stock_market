"""
Unit tests for SQLiteStore MF Holdings cache operations.
"""
import os
import unittest
import tempfile

from storage.sqlite_store import SQLiteStore


class TestMFHoldingsCache(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.store = SQLiteStore(self.temp_db.name)

    def tearDown(self):
        try:
            os.unlink(self.temp_db.name)
        except (OSError, PermissionError):
            pass

    def test_save_and_get_mf_schemes_cache(self):
        schemes = [
            {"scheme_id": 101, "scheme_name": "Test Fund", "amc_name": "Test AMC", "category": "Large Cap", "aum_cr": 1000.0},
            {"scheme_id": 102, "scheme_name": "Other Fund", "amc_name": "Other AMC", "category": "Mid Cap", "aum_cr": 500.0},
        ]
        count = self.store.save_mf_schemes_cache(schemes)
        self.assertEqual(count, 2)

        result = self.store.get_mf_schemes_cache()
        self.assertEqual(len(result), 2)

    def test_get_mf_schemes_cache_filter_by_amc(self):
        schemes = [
            {"scheme_id": 101, "scheme_name": "Fund A", "amc_name": "AMC Alpha"},
            {"scheme_id": 102, "scheme_name": "Fund B", "amc_name": "AMC Beta"},
        ]
        self.store.save_mf_schemes_cache(schemes)
        result = self.store.get_mf_schemes_cache(amc_name="AMC Alpha")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["scheme_name"], "Fund A")

    def test_save_and_get_mf_holdings_cache(self):
        holdings = [
            {"scheme_id": 101, "symbol": "RELIANCE.NS", "as_of_date": "2026-07-31",
             "shares_held": 18200000, "market_value_cr": 5278.0, "portfolio_weight_pct": 7.12,
             "mom_share_change": 1200000, "action_type": "STAKE_INCREASE"},
        ]
        count = self.store.save_mf_holdings_cache(holdings)
        self.assertEqual(count, 1)

        result = self.store.get_mf_holdings_cache(symbol="RELIANCE.NS")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["shares_held"], 18200000)

    def test_upsert_updates_existing_holdings(self):
        h1 = [{"scheme_id": 101, "symbol": "TCS.NS", "as_of_date": "2026-07-31",
               "shares_held": 1000, "mom_share_change": 100, "action_type": "STAKE_INCREASE"}]
        h2 = [{"scheme_id": 101, "symbol": "TCS.NS", "as_of_date": "2026-07-31",
               "shares_held": 2000, "mom_share_change": 200, "action_type": "STAKE_INCREASE"}]
        self.store.save_mf_holdings_cache(h1)
        self.store.save_mf_holdings_cache(h2)

        result = self.store.get_mf_holdings_cache(symbol="TCS.NS")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["shares_held"], 2000)

    def test_filter_by_action_type(self):
        holdings = [
            {"scheme_id": 101, "symbol": "A.NS", "as_of_date": "2026-07-31",
             "shares_held": 100, "action_type": "FRESH_ENTRY"},
            {"scheme_id": 102, "symbol": "B.NS", "as_of_date": "2026-07-31",
             "shares_held": 200, "action_type": "STAKE_REDUCTION"},
        ]
        self.store.save_mf_holdings_cache(holdings)
        result = self.store.get_mf_holdings_cache(action_type="FRESH_ENTRY")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["symbol"], "A.NS")

    def test_get_mf_holdings_summary(self):
        holdings = [
            {"scheme_id": 101, "symbol": "REL.NS", "as_of_date": "2026-07-31",
             "shares_held": 1000, "market_value_cr": 100.0, "mom_share_change": 200,
             "action_type": "STAKE_INCREASE"},
            {"scheme_id": 102, "symbol": "REL.NS", "as_of_date": "2026-07-31",
             "shares_held": 500, "market_value_cr": 50.0, "mom_share_change": 500,
             "action_type": "FRESH_ENTRY"},
        ]
        self.store.save_mf_holdings_cache(holdings)
        summary = self.store.get_mf_holdings_summary(as_of_date="2026-07-31")
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["scheme_count"], 2)
        self.assertEqual(summary[0]["total_shares_held"], 1500)
        self.assertEqual(summary[0]["net_mom_change"], 700)
        self.assertEqual(summary[0]["fresh_entry_count"], 1)
        self.assertEqual(summary[0]["increase_count"], 1)

    def test_get_top_accumulated_stocks(self):
        holdings = [
            {"scheme_id": 101, "symbol": "A.NS", "as_of_date": "2026-07-31",
             "shares_held": 1000, "market_value_cr": 10.0, "mom_share_change": 500,
             "action_type": "STAKE_INCREASE"},
            {"scheme_id": 101, "symbol": "B.NS", "as_of_date": "2026-07-31",
             "shares_held": 2000, "market_value_cr": 20.0, "mom_share_change": 1000,
             "action_type": "FRESH_ENTRY"},
        ]
        self.store.save_mf_holdings_cache(holdings)
        top = self.store.get_top_accumulated_stocks(as_of_date="2026-07-31", limit=5)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]["symbol"], "B.NS")

    def test_sync_metadata_operations(self):
        self.assertIsNone(self.store.get_last_sync_time("test_table"))

        self.store.set_last_sync_time("test_table", "2026-07-10T08:30:00Z", 42)
        result = self.store.get_last_sync_time("test_table")
        self.assertEqual(result, "2026-07-10T08:30:00Z")

        status = self.store.get_sync_status()
        self.assertEqual(len(status), 1)
        self.assertEqual(status[0]["row_count"], 42)

    def test_get_mf_holdings_count(self):
        self.assertEqual(self.store.get_mf_holdings_count(), 0)
        holdings = [{"scheme_id": 1, "symbol": "X.NS", "as_of_date": "2026-07-31",
                     "shares_held": 100, "action_type": "FRESH_ENTRY"}]
        self.store.save_mf_holdings_cache(holdings)
        self.assertEqual(self.store.get_mf_holdings_count(), 1)

    def test_get_available_dates(self):
        holdings = [
            {"scheme_id": 1, "symbol": "A.NS", "as_of_date": "2026-07-31", "shares_held": 100},
            {"scheme_id": 1, "symbol": "B.NS", "as_of_date": "2026-06-30", "shares_held": 200},
        ]
        self.store.save_mf_holdings_cache(holdings)
        dates = self.store.get_mf_holdings_available_dates()
        self.assertEqual(len(dates), 2)
        self.assertEqual(dates[0], "2026-07-31")

    def test_empty_input_returns_zero(self):
        self.assertEqual(self.store.save_mf_schemes_cache([]), 0)
        self.assertEqual(self.store.save_mf_holdings_cache([]), 0)


if __name__ == '__main__':
    unittest.main()
