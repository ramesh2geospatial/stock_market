"""
Unit tests for Offline-First Storage Architecture:
- 100% offline local SQLite phone operations
- Local JSON database export & restore
- Explicit opt-in cloud backup push
"""
import unittest
import json
from unittest.mock import MagicMock

from storage.offline_sync_manager import OfflineSyncManager


class TestOfflineStorage(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_cloud = MagicMock()
        self.sync_manager = OfflineSyncManager(db_store=self.mock_db, cloud_provider=self.mock_cloud)

    def test_local_watchlist_add_and_retrieve(self):
        """Verify watchlist items are read and written to local phone SQLite storage."""
        self.mock_db.get_watchlist.return_value = [{"symbol": "RELIANCE", "target_price": 3000.0, "notes": "Local note"}]

        success = self.sync_manager.add_to_watchlist_local("RELIANCE", 3000.0, "Local note")
        self.assertTrue(success)
        self.mock_db.add_to_watchlist.assert_called_once_with(symbol="RELIANCE", target_price=3000.0, notes="Local note")

        watchlist = self.sync_manager.get_watchlist_local()
        self.assertEqual(len(watchlist), 1)
        self.assertEqual(watchlist[0]["symbol"], "RELIANCE")

    def test_local_backup_export_and_import(self):
        """Verify local JSON backup export and import works without cloud connection."""
        self.mock_db.get_watchlist.return_value = [{"symbol": "TATASTEEL", "target_price": 180.0, "notes": "Steel demand"}]

        backup_str = self.sync_manager.export_local_backup_json()
        self.assertIn("TATASTEEL", backup_str)

        restore_success = self.sync_manager.import_local_backup_json(backup_str)
        self.assertTrue(restore_success)

    def test_opt_in_cloud_backup_push(self):
        """Verify cloud backup is triggered only on explicit call."""
        self.mock_cloud.is_configured.return_value = True
        self.mock_cloud.upload_stock_document.return_value = {"success": True, "public_url": "https://nbyzclczjoxaemcckxne.supabase.co/storage/v1/object/public/stock_backups/backups/user123_backup.json"}
        self.mock_db.get_watchlist.return_value = []

        res = self.sync_manager.push_backup_to_supabase(user_id="user123")
        self.assertTrue(res["success"])
        self.mock_cloud.upload_stock_document.assert_called_once()


if __name__ == "__main__":
    unittest.main()
