import logging
from typing import Dict, List, Set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amc_holdings_scraper")

# Sample institutional benchmark holdings database for top Indian Mutual Funds
# Scheme Code mapping:
# 122639: Parag Parikh Flexi Cap Fund - Direct Plan - Growth
# 119063: HDFC Top 100 Fund - Direct Plan - Growth
# 119598: SBI Bluechip Fund - Direct Plan - Growth
# 125497: Axis Small Cap Fund - Direct Plan - Growth
# 120503: UTI Nifty 50 Index Fund - Direct Plan - Growth

SAMPLE_SCHEME_HOLDINGS = {
    "122639": {
        "scheme_name": "Parag Parikh Flexi Cap Fund",
        "amc": "PPFAS Mutual Fund",
        "holdings": [
            {"stock_name": "HDFC Bank Ltd.", "isin": "INE040A01034", "sector": "Financial Services", "weight_pct": 7.85},
            {"stock_name": "Power Grid Corporation of India Ltd.", "isin": "INE752E01010", "sector": "Utilities", "weight_pct": 6.42},
            {"stock_name": "Bajaj Holdings & Investment Ltd.", "isin": "INE118A01012", "sector": "Financial Services", "weight_pct": 6.15},
            {"stock_name": "ITC Ltd.", "isin": "INE154A01025", "sector": "FMCG", "weight_pct": 5.90},
            {"stock_name": "Alphabet Inc. (Google)", "isin": "US02079K3059", "sector": "Technology", "weight_pct": 4.80},
            {"stock_name": "Microsoft Corporation", "isin": "US5949181045", "sector": "Technology", "weight_pct": 4.50},
            {"stock_name": "Coal India Ltd.", "isin": "INE522F01014", "sector": "Energy", "weight_pct": 4.10},
            {"stock_name": "ICICI Bank Ltd.", "isin": "INE090A01021", "sector": "Financial Services", "weight_pct": 3.95},
        ]
    },
    "119063": {
        "scheme_name": "HDFC Top 100 Fund",
        "amc": "HDFC Mutual Fund",
        "holdings": [
            {"stock_name": "HDFC Bank Ltd.", "isin": "INE040A01034", "sector": "Financial Services", "weight_pct": 9.80},
            {"stock_name": "ICICI Bank Ltd.", "isin": "INE090A01021", "sector": "Financial Services", "weight_pct": 8.40},
            {"stock_name": "Reliance Industries Ltd.", "isin": "INE002A01018", "sector": "Energy", "weight_pct": 7.60},
            {"stock_name": "Infosys Ltd.", "isin": "INE009A01021", "sector": "Technology", "weight_pct": 5.50},
            {"stock_name": "Larsen & Toubro Ltd.", "isin": "INE018A01030", "sector": "Construction", "weight_pct": 4.90},
            {"stock_name": "ITC Ltd.", "isin": "INE154A01025", "sector": "FMCG", "weight_pct": 4.20},
            {"stock_name": "State Bank of India", "isin": "INE062A01020", "sector": "Financial Services", "weight_pct": 3.80},
        ]
    },
    "119598": {
        "scheme_name": "SBI Bluechip Fund",
        "amc": "SBI Mutual Fund",
        "holdings": [
            {"stock_name": "ICICI Bank Ltd.", "isin": "INE090A01021", "sector": "Financial Services", "weight_pct": 8.90},
            {"stock_name": "HDFC Bank Ltd.", "isin": "INE040A01034", "sector": "Financial Services", "weight_pct": 8.20},
            {"stock_name": "Reliance Industries Ltd.", "isin": "INE002A01018", "sector": "Energy", "weight_pct": 6.80},
            {"stock_name": "Larsen & Toubro Ltd.", "isin": "INE018A01030", "sector": "Construction", "weight_pct": 4.50},
            {"stock_name": "Infosys Ltd.", "isin": "INE009A01021", "sector": "Technology", "weight_pct": 4.10},
            {"stock_name": "ITC Ltd.", "isin": "INE154A01025", "sector": "FMCG", "weight_pct": 3.70},
        ]
    }
}

try:
    from storage.sqlite_store import SQLiteStore
except ImportError:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from storage.sqlite_store import SQLiteStore

AMFI_TO_INTERNAL_SCHEME = {
    "122639": 101,  # Parag Parikh Flexi Cap Fund
    "119598": 102,  # SBI Bluechip Fund
    "119063": 103,  # HDFC Top 100 Fund
    "120503": 203,  # UTI Nifty 50 Index Fund
    "125497": 109,  # Small Cap Fund
}

class AMCHoldingsEngine:
    """Manages scheme portfolio holdings & fund overlap calculations across multiple sources."""

    @classmethod
    def get_holdings(cls, scheme_code: str) -> Dict:
        """Fetch all stock holdings for a specific scheme code from SQLite, Supabase, or AMFI mapping."""
        code_str = str(scheme_code).strip()
        try:
            store = SQLiteStore()
            schemes = store.get_mf_schemes_cache()
            numeric_id = None

            # 1. Check known AMFI code mapping first
            if code_str in AMFI_TO_INTERNAL_SCHEME:
                numeric_id = AMFI_TO_INTERNAL_SCHEME[code_str]
            elif code_str.isdigit():
                numeric_id = int(code_str)

            # 2. Find scheme info
            scheme_info = None
            if numeric_id is not None:
                for s in schemes:
                    if s.get("scheme_id") == numeric_id:
                        scheme_info = s
                        break

            # 3. If not found by ID, search by name
            if not scheme_info:
                q_lower = code_str.lower()
                for s in schemes:
                    s_name = s.get("scheme_name", "").lower()
                    if q_lower in s_name or s_name in q_lower:
                        scheme_info = s
                        numeric_id = s.get("scheme_id")
                        break

            # 4. Fetch holdings from SQLite
            db_holdings = []
            if numeric_id is not None:
                db_holdings = store.get_mf_holdings_cache(scheme_id=numeric_id)

                # 5. If local cache empty, attempt auto-pull from Supabase Cloud
                if not db_holdings:
                    try:
                        from providers.mf_holdings_provider import MFHoldingsProvider
                        provider = MFHoldingsProvider()
                        if provider.is_configured():
                            cloud_h = provider.fetch_mf_holdings(scheme_id=numeric_id)
                            if cloud_h:
                                store.save_mf_holdings_cache(cloud_h)
                                db_holdings = store.get_mf_holdings_cache(scheme_id=numeric_id)
                    except Exception as cloud_err:
                        logger.debug(f"Supabase auto-fetch error for scheme {numeric_id}: {cloud_err}")

            if db_holdings and scheme_info:
                # 6. Lookup index stocks metadata (company names, sectors)
                stocks_meta = {}
                try:
                    conn = store._conn()
                    rows = conn.execute("SELECT symbol, company_name, sector FROM index_stocks").fetchall()
                    conn.close()
                    stocks_meta = {r[0]: {"name": r[1], "sector": r[2]} for r in rows}
                except Exception:
                    pass

                formatted_holdings = []
                for h in db_holdings:
                    sym = h.get("symbol", "")
                    meta = stocks_meta.get(sym, {})
                    stock_name = meta.get("name") or sym.replace(".NS", "").replace(".BO", "")
                    formatted_holdings.append({
                        "stock_name": stock_name,
                        "symbol": sym,
                        "isin": "",
                        "sector": meta.get("sector") or "Equity",
                        "weight_pct": h.get("portfolio_weight_pct") or 0.0,
                        "shares_held": h.get("shares_held") or 0,
                        "market_value_cr": h.get("market_value_cr") or 0.0,
                        "action": h.get("action_type") or "MAINTAINED",
                        "mom_change": h.get("mom_share_change") or 0,
                    })

                # Sort by portfolio weight descending
                formatted_holdings.sort(key=lambda x: x["weight_pct"], reverse=True)

                return {
                    "scheme_id": scheme_info.get("scheme_id"),
                    "scheme_name": scheme_info.get("scheme_name", f"Scheme {scheme_code}"),
                    "amc": scheme_info.get("amc_name", "Mutual Fund AMC"),
                    "category": scheme_info.get("category", "Equity"),
                    "aum_cr": scheme_info.get("aum_cr", 0.0),
                    "holdings_count": len(formatted_holdings),
                    "holdings": formatted_holdings
                }
        except Exception as e:
            logger.debug(f"SQLite lookup skipped for scheme {scheme_code}: {e}")

        return SAMPLE_SCHEME_HOLDINGS.get(code_str, {
            "scheme_name": "Generic Scheme",
            "amc": "Mutual Fund AMC",
            "holdings": []
        })

    @classmethod
    def calculate_portfolio_overlap(cls, scheme_code_a: str, scheme_code_b: str) -> Dict:
        """Calculate common stock holdings & overlap percentage between two schemes."""
        fund_a = cls.get_holdings(scheme_code_a)
        fund_b = cls.get_holdings(scheme_code_b)

        if not fund_a or not fund_b or not fund_a.get("holdings") or not fund_b.get("holdings"):
            return {
                "fund_a": fund_a.get("scheme_name", "Scheme A") if fund_a else "Scheme A",
                "fund_b": fund_b.get("scheme_name", "Scheme B") if fund_b else "Scheme B",
                "overlap_pct": 0.0,
                "common_stock_count": 0,
                "common_stocks": []
            }

        map_a = {item["stock_name"]: item["weight_pct"] for item in fund_a["holdings"]}
        map_b = {item["stock_name"]: item["weight_pct"] for item in fund_b["holdings"]}

        common_stocks = []
        total_overlap = 0.0

        for stock, weight_a in map_a.items():
            if stock in map_b:
                weight_b = map_b[stock]
                min_weight = min(weight_a, weight_b)
                total_overlap += min_weight
                common_stocks.append({
                    "stock_name": stock,
                    "weight_in_fund_a": weight_a,
                    "weight_in_fund_b": weight_b,
                    "overlap_contribution": min_weight
                })

        return {
            "fund_a": fund_a["scheme_name"],
            "fund_b": fund_b["scheme_name"],
            "overlap_pct": round(total_overlap, 2),
            "common_stock_count": len(common_stocks),
            "common_stocks": common_stocks
        }

    @classmethod
    def aggregate_user_portfolio(cls, user_holdings: List[Dict]) -> Dict:
        """
        Aggregate underlying stock & sector exposure across multiple schemes.
        user_holdings: list of {"scheme_code": str, "current_value": float}
        """
        total_portfolio_val = sum(item.get("current_value", 0.0) for item in user_holdings)
        if total_portfolio_val <= 0:
            return {"total_value": 0, "stocks": [], "sectors": {}}

        stock_weighted_val: Dict[str, float] = {}
        sector_weighted_val: Dict[str, float] = {}

        for item in user_holdings:
            code = str(item.get("scheme_code"))
            val = float(item.get("current_value", 0.0))
            scheme_data = cls.get_holdings(code)
            if not scheme_data or not scheme_data.get("holdings"):
                continue

            for h in scheme_data["holdings"]:
                stock_name = h["stock_name"]
                sector = h.get("sector", "Equity")
                weight_pct = h["weight_pct"]

                # Effective monetary value in this stock
                stock_val = val * (weight_pct / 100.0)
                stock_weighted_val[stock_name] = stock_weighted_val.get(stock_name, 0.0) + stock_val
                sector_weighted_val[sector] = sector_weighted_val.get(sector, 0.0) + stock_val

        # Format stock breakdown
        aggregated_stocks = []
        for stock, stock_val in sorted(stock_weighted_val.items(), key=lambda x: x[1], reverse=True):
            aggregated_stocks.append({
                "stock_name": stock,
                "effective_value": round(stock_val, 2),
                "effective_weight_pct": round((stock_val / total_portfolio_val) * 100, 2)
            })

        # Format sector breakdown
        sector_breakdown = {
            sec: round((sval / total_portfolio_val) * 100, 2)
            for sec, sval in sorted(sector_weighted_val.items(), key=lambda x: x[1], reverse=True)
        }

        return {
            "total_portfolio_value": round(total_portfolio_val, 2),
            "stock_count": len(aggregated_stocks),
            "top_stocks": aggregated_stocks,
            "sector_allocation_pct": sector_breakdown
        }

if __name__ == "__main__":
    res = AMCHoldingsEngine.calculate_portfolio_overlap("122639", "119063")
    print(f"Overlap result: {res}")
