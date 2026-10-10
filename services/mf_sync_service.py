"""
MF Holdings Sync Service — Incremental Delta Sync from Supabase Cloud to Local SQLite Cache.

Orchestrates the fetch → upsert → watermark update pipeline for:
- MF Schemes (mf_schemes table)
- MF Stock Holdings (mf_stock_holdings table)
- Index Stocks (index_stocks table)

Follows the incremental sync protocol defined in ADR-0007:
  Client sends last_synced_at → Server returns only rows with created_at > timestamp.
"""
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from providers.mf_holdings_provider import MFHoldingsProvider
from storage.sqlite_store import SQLiteStore
from config import DB_PATH


class MFHoldingsSyncService:
    """Orchestrates incremental sync from Supabase Cloud to local SQLite cache."""

    TABLE_SCHEMES = "mf_schemes"
    TABLE_HOLDINGS = "mf_stock_holdings"
    TABLE_INDEX_STOCKS = "index_stocks"

    def __init__(
        self,
        provider: Optional[MFHoldingsProvider] = None,
        store: Optional[SQLiteStore] = None
    ):
        self.provider = provider or MFHoldingsProvider()
        self.store = store or SQLiteStore(str(DB_PATH))

    def _now_iso(self) -> str:
        """Current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def sync_schemes(self, force_full: bool = False) -> Dict[str, Any]:
        """Sync MF scheme metadata from Supabase to local cache.
        
        Args:
            force_full: If True, fetch all schemes regardless of last sync time.
        """
        start_time = time.time()
        last_sync = None if force_full else self.store.get_last_sync_time(self.TABLE_SCHEMES)
        
        try:
            schemes = self.provider.fetch_mf_schemes(last_synced_at=last_sync)
            if not schemes:
                return {
                    "table": self.TABLE_SCHEMES,
                    "synced": 0,
                    "status": "no_new_data",
                    "duration_ms": int((time.time() - start_time) * 1000)
                }
            
            count = self.store.save_mf_schemes_cache(schemes)
            sync_timestamp = self._now_iso()
            self.store.set_last_sync_time(self.TABLE_SCHEMES, sync_timestamp, count)
            
            return {
                "table": self.TABLE_SCHEMES,
                "synced": count,
                "status": "success",
                "last_synced_at": sync_timestamp,
                "duration_ms": int((time.time() - start_time) * 1000)
            }
        except Exception as e:
            return {
                "table": self.TABLE_SCHEMES,
                "synced": 0,
                "status": "error",
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000)
            }

    def sync_holdings(self, force_full: bool = False) -> Dict[str, Any]:
        """Sync MF stock holdings from Supabase to local cache (incremental by default).
        
        Uses paginated fetch to handle large datasets.
        """
        start_time = time.time()
        last_sync = None if force_full else self.store.get_last_sync_time(self.TABLE_HOLDINGS)
        
        try:
            holdings = self.provider.fetch_all_holdings_paginated(last_synced_at=last_sync)
            if not holdings:
                return {
                    "table": self.TABLE_HOLDINGS,
                    "synced": 0,
                    "total_cached": self.store.get_mf_holdings_count(),
                    "status": "no_new_data",
                    "duration_ms": int((time.time() - start_time) * 1000)
                }
            
            count = self.store.save_mf_holdings_cache(holdings)
            sync_timestamp = self._now_iso()
            total = self.store.get_mf_holdings_count()
            self.store.set_last_sync_time(self.TABLE_HOLDINGS, sync_timestamp, total)
            
            return {
                "table": self.TABLE_HOLDINGS,
                "synced": count,
                "total_cached": total,
                "status": "success",
                "last_synced_at": sync_timestamp,
                "duration_ms": int((time.time() - start_time) * 1000)
            }
        except Exception as e:
            return {
                "table": self.TABLE_HOLDINGS,
                "synced": 0,
                "total_cached": self.store.get_mf_holdings_count(),
                "status": "error",
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000)
            }

    def sync_all(self, force_full: bool = False) -> Dict[str, Any]:
        """Run full incremental sync for all MF tables.
        
        Sync order: schemes first (foreign key dependency), then holdings.
        """
        results = {}
        results["schemes"] = self.sync_schemes(force_full=force_full)
        results["holdings"] = self.sync_holdings(force_full=force_full)
        
        total_synced = sum(r.get("synced", 0) for r in results.values())
        all_success = all(r.get("status") in ("success", "no_new_data") for r in results.values())
        
        results["summary"] = {
            "total_synced": total_synced,
            "status": "success" if all_success else "partial_error",
            "synced_at": self._now_iso()
        }
        return results

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status for all tracked tables."""
        status_rows = self.store.get_sync_status()
        holdings_count = self.store.get_mf_holdings_count()
        schemes = self.store.get_mf_schemes_cache()
        available_dates = self.store.get_mf_holdings_available_dates()
        
        return {
            "tables": {row["table_name"]: row for row in status_rows},
            "total_holdings_cached": holdings_count,
            "total_schemes_cached": len(schemes),
            "available_dates": available_dates,
            "is_configured": self.provider.is_configured()
        }

    def needs_sync(self, max_age_seconds: int = 86400) -> bool:
        """Check if local cache is stale and needs refresh.
        
        Args:
            max_age_seconds: Maximum allowed age before considering stale (default: 24h)
        """
        last_sync = self.store.get_last_sync_time(self.TABLE_HOLDINGS)
        if not last_sync:
            return True  # Never synced
        try:
            last_dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - last_dt).total_seconds()
            return age > max_age_seconds
        except (ValueError, TypeError):
            return True
