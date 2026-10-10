"""
Supabase Storage & Data Provider for Stock Market Research Platform.
Handles document uploads (concall PDFs, investor presentations, database backups)
to Supabase Storage buckets and syncing watchlists/concall analysis via Postgrest REST API.
"""
import os
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Union

from config import SUPABASE_URL, SUPABASE_ANON_KEY, STOCK_DOCUMENTS_BUCKET, STOCK_BACKUPS_BUCKET


class SupabaseStorageProvider:
    """Interfaces with Supabase Storage and Postgres REST endpoints for Indian Stock Market Platform."""

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        default_bucket: str = STOCK_DOCUMENTS_BUCKET
    ):
        self.supabase_url = (supabase_url or SUPABASE_URL).rstrip("/")
        self.supabase_key = supabase_key or SUPABASE_ANON_KEY
        self.default_bucket = default_bucket

    def is_configured(self) -> bool:
        """Check if Supabase endpoint and key are configured."""
        return bool(self.supabase_url and self.supabase_key)

    def get_public_url(self, file_path: str, bucket_name: Optional[str] = None) -> str:
        """
        Generate public storage URL for a stock document or backup file.
        Format: https://<project_ref>.supabase.co/storage/v1/object/public/<bucket>/<file_path>
        """
        target_bucket = bucket_name or self.default_bucket
        cleaned_path = file_path.lstrip("/")
        return f"{self.supabase_url}/storage/v1/object/public/{target_bucket}/{cleaned_path}"

    def upload_stock_document(
        self,
        file_bytes: bytes,
        file_path: str,
        content_type: str = "application/pdf",
        bucket_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload stock concall transcript or result PDF bytes to Supabase Storage bucket.
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Supabase client unconfigured (missing URL or Key)",
                "public_url": None
            }

        target_bucket = bucket_name or self.default_bucket
        cleaned_path = file_path.lstrip("/")
        endpoint = f"{self.supabase_url}/storage/v1/object/{target_bucket}/{cleaned_path}"

        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": content_type,
            "x-upsert": "true"
        }

        try:
            req = urllib.request.Request(endpoint, data=file_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                public_url = self.get_public_url(cleaned_path, target_bucket)
                return {
                    "success": True,
                    "status_code": resp.status,
                    "file_path": cleaned_path,
                    "bucket": target_bucket,
                    "public_url": public_url,
                    "error": None
                }
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            return {
                "success": False,
                "status_code": e.code,
                "file_path": cleaned_path,
                "public_url": None,
                "error": f"HTTP {e.code}: {err_msg}"
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": 500,
                "file_path": cleaned_path,
                "public_url": None,
                "error": str(e)
            }

    def sync_concall_analysis(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sync concall sentiment analysis JSON to Supabase Postgrest REST table `concall_analyses`.
        """
        if not self.is_configured():
            return {"success": False, "error": "Supabase client unconfigured"}

        endpoint = f"{self.supabase_url}/rest/v1/concall_analyses"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation,resolution=merge-duplicates"
        }

        try:
            body = json.dumps(analysis_data).encode("utf-8")
            req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                return {
                    "success": True,
                    "data": res_data,
                    "error": None
                }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    def sync_index_stocks(self, stocks_list: list) -> Dict[str, Any]:
        """Push NSE/BSE index stocks catalog to Supabase Postgrest REST table `index_stocks`."""
        if not self.is_configured():
            return {"success": False, "error": "Supabase client unconfigured"}

        endpoint = f"{self.supabase_url}/rest/v1/index_stocks"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }

        try:
            body = json.dumps(stocks_list).encode("utf-8")
            req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return {"success": True, "status_code": resp.status, "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sync_mf_holdings(self, holdings_list: list) -> Dict[str, Any]:
        """Push monthly mutual fund scheme holdings to Supabase Postgrest REST table `mf_stock_holdings`."""
        if not self.is_configured():
            return {"success": False, "error": "Supabase client unconfigured"}

        endpoint = f"{self.supabase_url}/rest/v1/mf_stock_holdings"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }

        try:
            body = json.dumps(holdings_list).encode("utf-8")
            req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return {"success": True, "status_code": resp.status, "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

