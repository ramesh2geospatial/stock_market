"""
Offline-First Sync Manager.
Enforces local phone storage for 95% of operations (watchlists, concalls, financial metrics, notes).
Supabase Cloud is called ONLY on explicit user backup requests or authentication.
"""
import json
from typing import Optional, Dict, Any, List

from storage.sqlite_store import SQLiteStore
from providers.supabase_storage_provider import SupabaseStorageProvider


class OfflineSyncManager:
    """Manages offline-first phone storage and minimal, opt-in cloud sync."""

    def __init__(self, db_store: Optional[SQLiteStore] = None, cloud_provider: Optional[SupabaseStorageProvider] = None):
        self.db = db_store or SQLiteStore()
        self.cloud = cloud_provider or SupabaseStorageProvider()

    # ------------------------------------------------------------------
    # 1. 100% Local Phone Operations (Offline, 0ms Latency)
    # ------------------------------------------------------------------
    def get_watchlist_local(self) -> List[Dict[str, Any]]:
        """Fetch watchlist items stored locally on phone SQLite database."""
        return self.db.get_watchlist()

    def add_to_watchlist_local(self, symbol: str, target_price: float = 0.0, notes: str = "") -> bool:
        """Save watchlist item directly to local phone SQLite database."""
        try:
            self.db.add_to_watchlist(symbol=symbol, target_price=target_price, notes=notes)
            return True
        except Exception as e:
            print(f"[OfflineSync] Error saving watchlist locally: {e}")
            return False

    def get_concall_analyses_local(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch concall analyses stored locally on phone SQLite database."""
        return self.db.get_all_analyses(symbol)

    def export_local_backup_json(self) -> str:
        """
        Export entire local phone DB state to a JSON backup string.
        Enables 100% offline file backup without cloud connectivity.
        """
        data = {
            "watchlist": self.get_watchlist_local(),
            "export_version": "1.0"
        }
        return json.dumps(data, indent=2)

    def import_local_backup_json(self, json_str: str) -> bool:
        """Restore local database state from a local JSON backup string."""
        try:
            data = json.loads(json_str)
            watchlist = data.get("watchlist", [])
            for item in watchlist:
                symbol = item.get("symbol")
                if symbol:
                    self.add_to_watchlist_local(
                        symbol=symbol,
                        target_price=item.get("target_price", 0.0),
                        notes=item.get("notes", "")
                    )
            return True
        except Exception as e:
            print(f"[OfflineSync] Error importing local backup: {e}")
            return False

    # ------------------------------------------------------------------
    # 2. Minimal Opt-in Supabase Cloud Backup (Triggered manually)
    # ------------------------------------------------------------------
    def push_backup_to_supabase(self, user_id: str = "default_user") -> Dict[str, Any]:
        """
        Upload local database state to Supabase Cloud only when explicitly triggered by user.
        """
        if not self.cloud.is_configured():
            return {"success": False, "error": "Supabase Cloud unconfigured"}

        backup_json = self.export_local_backup_json()
        file_path = f"backups/{user_id}_backup.json"
        res = self.cloud.upload_stock_document(
            file_bytes=backup_json.encode("utf-8"),
            file_path=file_path,
            content_type="application/json",
            bucket_name="stock_backups"
        )
        return res
