"""
Supabase PostgREST Read & Local Query Provider for Mutual Fund Holdings and Index Stocks.
Fetches MF holdings, schemes, and index stocks from Supabase Cloud with incremental sync,
and provides fast local SQLite search & drilldown methods.
"""
import json
import time
import sqlite3
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any

try:
    from config import DB_PATH, SUPABASE_URL, SUPABASE_ANON_KEY, MF_SYNC_BATCH_SIZE, MF_SYNC_TIMEOUT
except ImportError:
    from config import DB_PATH, SUPABASE_URL, SUPABASE_ANON_KEY
    MF_SYNC_BATCH_SIZE = 500
    MF_SYNC_TIMEOUT = 30


class MFHoldingsProvider:
    """Fetches Mutual Fund holdings data from Supabase Cloud via PostgREST REST API
    and provides zero-latency local querying over SQLite cache.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        db_path: Optional[str] = None
    ):
        raw_url = SUPABASE_URL if supabase_url is None else supabase_url
        self.supabase_url = raw_url.rstrip("/") if raw_url else ""
        self.supabase_key = SUPABASE_ANON_KEY if supabase_key is None else supabase_key
        self.batch_size = MF_SYNC_BATCH_SIZE
        self.timeout = MF_SYNC_TIMEOUT
        self.db_path = str(db_path or DB_PATH)
        self._ensure_db_schema()

    def _ensure_db_schema(self):
        """Ensure SQLite schema is initialized and seed basic constituent catalog if empty."""
        try:
            from storage.sqlite_store import SQLiteStore
            store = SQLiteStore(db_path=self.db_path)
            conn = self._get_conn()
            count = conn.execute("SELECT COUNT(*) FROM index_stocks").fetchone()[0]
            if count == 0:
                default_stocks = [
                    ("RELIANCE.NS", "Reliance Industries Ltd.", "LARGE_CAP", "Nifty 50", 1950000.0, "Energy"),
                    ("TCS.NS", "Tata Consultancy Services Ltd.", "LARGE_CAP", "Nifty 50", 1420000.0, "Technology"),
                    ("HDFCBANK.NS", "HDFC Bank Ltd.", "LARGE_CAP", "Nifty 50", 1280000.0, "Financial Services"),
                    ("BHARTIARTL.NS", "Bharti Airtel Ltd.", "LARGE_CAP", "Nifty 50", 920000.0, "Telecommunication"),
                    ("ICICIBANK.NS", "ICICI Bank Ltd.", "LARGE_CAP", "Nifty 50", 890000.0, "Financial Services"),
                    ("POLYCAB.NS", "Polycab India Ltd.", "MID_CAP", "Nifty Midcap 150", 95000.0, "Capital Goods"),
                    ("BSE.NS", "BSE Ltd.", "SMALL_CAP", "Nifty Smallcap 250", 48000.0, "Financial Services"),
                    ("CDSL.NS", "Central Depository Services Ltd.", "SMALL_CAP", "Nifty Smallcap 250", 38000.0, "Financial Services"),
                    ("SENCO.NS", "Senco Gold Ltd.", "MICRO_CAP", "Nifty Microcap 250", 9500.0, "Consumer Discretionary"),
                ]
                conn.executemany(
                    "INSERT OR IGNORE INTO index_stocks (symbol, company_name, tier, index_name, mcap_cr, sector) VALUES (?, ?, ?, ?, ?, ?)",
                    default_stocks
                )

                # Seed sample schemes
                sample_schemes = [
                    (119598, "SBI Bluechip Fund", "SBI Mutual Fund", "Large Cap", 45000.0),
                    (119063, "HDFC Top 100 Fund", "HDFC Mutual Fund", "Large Cap", 32000.0),
                    (122639, "Parag Parikh Flexi Cap Fund", "PPFAS Mutual Fund", "Flexi Cap", 68000.0),
                ]
                conn.executemany(
                    "INSERT OR IGNORE INTO mf_schemes_cache (scheme_id, scheme_name, amc_name, category, aum_cr) VALUES (?, ?, ?, ?, ?)",
                    sample_schemes
                )

                # Seed sample holdings
                sample_holdings = [
                    (119598, "RELIANCE.NS", "2026-07-31", 14500000, 4250.0, 6.85, 450000, "STAKE_INCREASE"),
                    (119063, "RELIANCE.NS", "2026-07-31", 9800000, 2870.0, 5.10, 320000, "STAKE_INCREASE"),
                    (122639, "RELIANCE.NS", "2026-07-31", 8500000, 2490.0, 4.20, 8500000, "FRESH_ENTRY"),
                ]
                conn.executemany(
                    "INSERT OR IGNORE INTO mf_holdings_cache (scheme_id, symbol, as_of_date, shares_held, market_value_cr, portfolio_weight_pct, mom_share_change, action_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    sample_holdings
                )
                conn.commit()
            conn.close()
        except Exception:
            pass

    def is_configured(self) -> bool:
        """Check if Supabase URL and Key are configured."""
        return bool(self.supabase_url and self.supabase_key)

    def _get_conn(self):
        """Create a local SQLite connection."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _get_headers(self) -> Dict[str, str]:
        """Build HTTP headers for PostgREST requests."""
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "count=exact"
        }

    def _fetch_with_retry(self, url: str, max_retries: int = 3) -> List[Dict[str, Any]]:
        """Fetch data from Supabase PostgREST with exponential backoff retry."""
        last_error = None
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers=self._get_headers(), method="GET")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data if isinstance(data, list) else []
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')}"
                if e.code == 429:  # Rate limited
                    time.sleep(2 ** attempt)
                    continue
                elif e.code >= 500:  # Server error, retry
                    time.sleep(2 ** attempt)
                    continue
                else:
                    print(f"[MFHoldingsProvider] Error fetching {url}: {last_error}")
                    return []
            except Exception as e:
                last_error = str(e)
                time.sleep(2 ** attempt)
        print(f"[MFHoldingsProvider] Failed after {max_retries} retries: {last_error}")
        return []

    def _build_query_params(self, filters: Dict[str, Any]) -> str:
        """Build PostgREST query parameter string from filter dict."""
        params = []
        for key, value in filters.items():
            if value is not None:
                params.append(f"{key}={value}")
        return "&".join(params)

    # -------------------------------------------------------------------------
    # Cloud Fetch Methods (Supabase REST API)
    # -------------------------------------------------------------------------

    def fetch_index_stocks(
        self,
        market_cap_tier: Optional[str] = None,
        last_synced_at: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch index stocks from Supabase, optionally filtered by tier and sync timestamp."""
        if not self.is_configured():
            return []
        filters = {"order": "symbol.asc"}
        if market_cap_tier:
            filters["market_cap_tier"] = f"eq.{market_cap_tier}"
        if last_synced_at:
            filters["updated_at"] = f"gt.{last_synced_at}"
        if limit:
            filters["limit"] = str(limit)
        else:
            filters["limit"] = str(self.batch_size)
        query = self._build_query_params(filters)
        url = f"{self.supabase_url}/rest/v1/index_stocks?{query}"
        return self._fetch_with_retry(url)

    def fetch_mf_schemes(
        self,
        amc_name: Optional[str] = None,
        last_synced_at: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch mutual fund scheme metadata from Supabase."""
        if not self.is_configured():
            return []
        filters = {"order": "scheme_id.asc", "limit": str(self.batch_size)}
        if amc_name:
            filters["amc_name"] = f"eq.{amc_name}"
        if last_synced_at:
            filters["created_at"] = f"gt.{last_synced_at}"
        query = self._build_query_params(filters)
        url = f"{self.supabase_url}/rest/v1/mf_schemes?{query}"
        return self._fetch_with_retry(url)

    def fetch_mf_holdings(
        self,
        symbol: Optional[str] = None,
        scheme_id: Optional[int] = None,
        as_of_date: Optional[str] = None,
        action_type: Optional[str] = None,
        last_synced_at: Optional[str] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch MF stock holdings from Supabase with flexible filtering."""
        if not self.is_configured():
            return []
        filters = {"order": order or "created_at.asc"}
        if symbol:
            filters["symbol"] = f"eq.{symbol}"
        if scheme_id is not None:
            filters["scheme_id"] = f"eq.{scheme_id}"
        if as_of_date:
            filters["as_of_date"] = f"eq.{as_of_date}"
        if action_type:
            filters["action_type"] = f"eq.{action_type}"
        if last_synced_at:
            filters["created_at"] = f"gt.{last_synced_at}"
        filters["limit"] = str(limit or self.batch_size)
        query = self._build_query_params(filters)
        url = f"{self.supabase_url}/rest/v1/mf_stock_holdings?{query}"
        return self._fetch_with_retry(url)

    def fetch_holdings_by_stock(
        self,
        symbol: str,
        as_of_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all MF scheme holdings for a specific stock with joined scheme details."""
        if not self.is_configured():
            return []
        clean_sym = symbol.strip().upper()
        sym_ns = clean_sym if clean_sym.endswith(".NS") or clean_sym.endswith(".BO") else f"{clean_sym}.NS"
        sym_raw = clean_sym.replace(".NS", "").replace(".BO", "")
        
        filters = {
            "symbol": f"in.({clean_sym},{sym_ns},{sym_raw})",
            "select": "*,mf_schemes(scheme_name,amc_name,category)",
            "order": "market_value_cr.desc",
            "limit": "200"
        }
        if as_of_date:
            filters["as_of_date"] = f"eq.{as_of_date}"
        query = self._build_query_params(filters)
        url = f"{self.supabase_url}/rest/v1/mf_stock_holdings?{query}"
        rows = self._fetch_with_retry(url)
        if not rows:
            return self.fetch_mf_holdings(symbol=sym_ns, as_of_date=as_of_date, limit=200, order="market_value_cr.desc")
        return rows

    def fetch_available_dates(self) -> List[str]:
        """Fetch distinct as_of_date values from mf_stock_holdings."""
        if not self.is_configured():
            return []
        url = f"{self.supabase_url}/rest/v1/mf_stock_holdings?select=as_of_date&order=as_of_date.desc&limit=50"
        rows = self._fetch_with_retry(url)
        dates = sorted(set(r.get("as_of_date", "") for r in rows if r.get("as_of_date")), reverse=True)
        return dates

    def fetch_all_holdings_paginated(
        self,
        last_synced_at: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch ALL holdings with pagination for full/incremental sync."""
        if not self.is_configured():
            return []
        all_rows = []
        offset = 0
        while True:
            filters = {
                "order": "created_at.asc",
                "limit": str(self.batch_size),
                "offset": str(offset)
            }
            if last_synced_at:
                filters["created_at"] = f"gt.{last_synced_at}"
            query = self._build_query_params(filters)
            url = f"{self.supabase_url}/rest/v1/mf_stock_holdings?{query}"
            batch = self._fetch_with_retry(url)
            if not batch:
                break
            all_rows.extend(batch)
            if len(batch) < self.batch_size:
                break
            offset += self.batch_size
        return all_rows


    # -------------------------------------------------------------------------
    # Local SQLite Query Methods (used by StockAnalyzer & Mobile APIs)
    # -------------------------------------------------------------------------

    def search_stocks(self, query: str = "", tier: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        """Search stocks in index universe with scheme holding count."""
        try:
            conn = self._get_conn()
            sql = """
                SELECT 
                    s.symbol, s.company_name, s.tier, s.index_name, s.mcap_cr, s.sector,
                    COUNT(DISTINCT h.scheme_id) as mf_scheme_count
                FROM index_stocks s
                LEFT JOIN mf_holdings_cache h ON s.symbol = h.symbol
                WHERE 1=1
            """
            params = []
            if tier and tier != "ALL":
                sql += " AND s.tier = ?"
                params.append(tier)
            if query:
                pattern = f"%{query.strip()}%"
                sql += " AND (s.symbol LIKE ? OR s.company_name LIKE ? OR s.sector LIKE ?)"
                params.extend([pattern, pattern, pattern])
            sql += " GROUP BY s.symbol ORDER BY mf_scheme_count DESC, s.symbol ASC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            conn.close()
            cols = ["symbol", "company_name", "tier", "index_name", "mcap_cr", "sector", "mf_scheme_count"]
            return [dict(zip(cols, r)) for r in rows]
        except Exception as e:
            print(f"[MFHoldingsProvider] search_stocks error: {e}")
            return []

    def get_stock_mf_ownership(self, symbol: str) -> Dict[str, Any]:
        """Fetch scheme breakdown and MoM buy/sell diffs for a stock."""
        clean_sym = symbol.strip().upper()
        sym_ns = clean_sym if clean_sym.endswith(".NS") or clean_sym.endswith(".BO") else f"{clean_sym}.NS"

        try:
            conn = self._get_conn()
            
            # 1. Fetch stock info
            s_row = conn.execute(
                "SELECT symbol, company_name, tier, index_name, mcap_cr, sector FROM index_stocks WHERE symbol = ? OR symbol = ?",
                (clean_sym, sym_ns)
            ).fetchone()
            
            stock_info = {}
            if s_row:
                stock_info = {
                    "symbol": s_row[0],
                    "company_name": s_row[1],
                    "tier": s_row[2],
                    "index_name": s_row[3],
                    "mcap_cr": s_row[4],
                    "sector": s_row[5],
                }
            elif self.is_configured():
                try:
                    s_cloud = self._fetch_with_retry(
                        f"{self.supabase_url}/rest/v1/index_stocks?symbol=in.({clean_sym},{sym_ns})&limit=1"
                    )
                    if s_cloud:
                        sc = s_cloud[0]
                        stock_info = {
                            "symbol": sc.get("symbol", sym_ns),
                            "company_name": sc.get("company_name", clean_sym),
                            "tier": sc.get("market_cap_tier", "LARGE_CAP"),
                            "index_name": sc.get("index_name", "Nifty 50"),
                            "mcap_cr": sc.get("market_cap_cr", 0.0),
                            "sector": sc.get("sector", "Diversified"),
                        }
                        conn.execute(
                            "INSERT OR REPLACE INTO index_stocks (symbol, company_name, tier, index_name, mcap_cr, sector) VALUES (?, ?, ?, ?, ?, ?)",
                            (stock_info["symbol"], stock_info["company_name"], stock_info["tier"], stock_info["index_name"], stock_info["mcap_cr"], stock_info["sector"])
                        )
                        conn.commit()
                except Exception as sc_err:
                    print(f"[MFHoldingsProvider] Cloud stock info error: {sc_err}")

            # 2. Fetch scheme holdings joined with scheme names
            sql_holdings = """
                SELECT 
                    h.scheme_id, s.scheme_name, s.amc_name, s.category,
                    h.shares_held, h.market_value_cr, h.portfolio_weight_pct,
                    h.mom_share_change, h.action_type, h.as_of_date
                FROM mf_holdings_cache h
                LEFT JOIN mf_schemes_cache s ON h.scheme_id = s.scheme_id
                WHERE h.symbol = ? OR h.symbol = ?
                ORDER BY h.market_value_cr DESC, h.shares_held DESC
            """
            h_rows = conn.execute(sql_holdings, (clean_sym, sym_ns)).fetchall()

            # Auto-fetch from Supabase Cloud if local cache is empty for this stock
            if not h_rows and self.is_configured():
                try:
                    cloud_holdings = self.fetch_holdings_by_stock(symbol)
                    if cloud_holdings:
                        for ch in cloud_holdings:
                            sch_id = ch.get("scheme_id")
                            scheme_info = ch.get("mf_schemes") or {}
                            if sch_id and scheme_info:
                                conn.execute(
                                    "INSERT OR IGNORE INTO mf_schemes_cache (scheme_id, scheme_name, amc_name, category) VALUES (?, ?, ?, ?)",
                                    (sch_id, scheme_info.get("scheme_name", ""), scheme_info.get("amc_name", ""), scheme_info.get("category", "Equity"))
                                )
                            conn.execute(
                                """INSERT OR REPLACE INTO mf_holdings_cache 
                                   (scheme_id, symbol, as_of_date, shares_held, market_value_cr, portfolio_weight_pct, mom_share_change, action_type)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    sch_id,
                                    ch.get("symbol", sym_ns),
                                    ch.get("as_of_date"),
                                    ch.get("shares_held", 0),
                                    ch.get("market_value_cr", 0.0),
                                    ch.get("portfolio_weight_pct", 0.0),
                                    ch.get("mom_share_change", 0),
                                    ch.get("action_type", "HOLD")
                                )
                            )
                        conn.commit()
                        h_rows = conn.execute(sql_holdings, (clean_sym, sym_ns)).fetchall()
                except Exception as sync_err:
                    print(f"[MFHoldingsProvider] Auto-sync holdings error: {sync_err}")

            conn.close()

            holdings_matrix = []
            total_shares = 0
            total_value = 0.0
            net_mom_change = 0

            for r in h_rows:
                scheme_id = r[0]
                scheme_name = r[1] or f"Scheme #{scheme_id}"
                amc_name = r[2] or "Unknown AMC"
                category = r[3] or "Equity"
                shares = r[4] or 0
                val_cr = r[5] or 0.0
                weight_pct = r[6] or 0.0
                mom_change = r[7] or 0
                action = r[8] or ("STAKE_INCREASE" if mom_change > 0 else "STAKE_REDUCTION" if mom_change < 0 else "HOLD")
                as_of = r[9]

                total_shares += shares
                total_value += val_cr
                net_mom_change += mom_change

                holdings_matrix.append({
                    "scheme_id": scheme_id,
                    "scheme_name": scheme_name,
                    "amc_name": amc_name,
                    "category": category,
                    "shares_held": shares,
                    "market_value_cr": val_cr,
                    "portfolio_weight_pct": weight_pct,
                    "mom_share_change": mom_change,
                    "action_type": action,
                    "as_of_date": as_of
                })

            sentiment = "BULLISH_ACCUMULATION" if net_mom_change > 0 else "BEARISH_DISTRIBUTION" if net_mom_change < 0 else "NEUTRAL"

            return {
                "symbol": sym_ns,
                "stock_info": stock_info,
                "summary": {
                    "total_mf_schemes_holding": len(holdings_matrix),
                    "total_mf_shares_held": total_shares,
                    "total_mf_value_cr": round(total_value, 2),
                    "net_mom_share_change": net_mom_change,
                    "sentiment_signal": sentiment
                },
                "holdings_matrix": holdings_matrix
            }
        except Exception as e:
            print(f"[MFHoldingsProvider] get_stock_mf_ownership error: {e}")
            return {
                "symbol": sym_ns,
                "error": str(e),
                "stock_info": {},
                "summary": {},
                "holdings_matrix": []
            }

    def get_market_cap_tier_stocks(self, tier: str) -> List[Dict[str, Any]]:
        """Fetch index stocks categorized by SEBI market cap tier."""
        try:
            conn = self._get_conn()
            if tier and tier.upper() != "ALL":
                rows = conn.execute(
                    "SELECT symbol, company_name, tier, index_name, mcap_cr, sector FROM index_stocks WHERE tier = ? ORDER BY symbol ASC",
                    (tier.upper(),)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT symbol, company_name, tier, index_name, mcap_cr, sector FROM index_stocks ORDER BY symbol ASC"
                ).fetchall()
            conn.close()
            cols = ["symbol", "company_name", "tier", "index_name", "mcap_cr", "sector"]
            return [dict(zip(cols, r)) for r in rows]
        except Exception as e:
            print(f"[MFHoldingsProvider] get_market_cap_tier_stocks error: {e}")
            return []
