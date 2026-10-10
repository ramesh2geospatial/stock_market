"""
TTL-based file cache for API responses.
Prevents redundant network calls and speeds up repeated analysis.
"""
import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Any

from config import CACHE_DIR, CACHE_TTL


class FileCache:
    """File-system JSON cache with per-namespace TTL."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, namespace: str, params: dict) -> str:
        """Generate a deterministic cache key from namespace + params."""
        raw = f"{namespace}:{json.dumps(params, sort_keys=True, default=str)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, namespace: str, params: dict) -> Optional[Any]:
        """
        Retrieve a cached value if it exists and hasn't expired.
        Returns None on miss.
        """
        key = self._key(namespace, params)
        path = self.cache_dir / f"{key}.json"

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ttl = data.get("ttl", CACHE_TTL.get(namespace, 3600))
            if time.time() - data["timestamp"] < ttl:
                return data["value"]
            # Expired — delete the file
            path.unlink(missing_ok=True)
        except (json.JSONDecodeError, KeyError):
            path.unlink(missing_ok=True)

        return None

    def set(self, namespace: str, params: dict, value: Any, ttl: int = None):
        """Store a value in cache with TTL."""
        key = self._key(namespace, params)
        path = self.cache_dir / f"{key}.json"

        cache_entry = {
            "timestamp": time.time(),
            "ttl": ttl or CACHE_TTL.get(namespace, 3600),
            "namespace": namespace,
            "params": params,
            "value": value,
        }

        path.write_text(
            json.dumps(cache_entry, default=str, ensure_ascii=False),
            encoding="utf-8",
        )

    def invalidate(self, namespace: str, params: dict):
        """Remove a specific cache entry."""
        key = self._key(namespace, params)
        path = self.cache_dir / f"{key}.json"
        path.unlink(missing_ok=True)

    def clear_namespace(self, namespace: str):
        """Clear all entries for a namespace (brute force scan)."""
        for path in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("namespace") == namespace:
                    path.unlink(missing_ok=True)
            except Exception:
                pass

    def clear_all(self):
        """Nuke the entire cache."""
        for path in self.cache_dir.glob("*.json"):
            path.unlink(missing_ok=True)
