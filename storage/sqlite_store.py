"""
SQLite persistence layer for watchlists, notes, and AI analysis cache.
"""
import datetime
import json
import sqlite3
from typing import Optional, List, Dict, Any
import pandas as pd

from config import DB_PATH
from models.ground_truth import GroundTruthFinancials



class SQLiteStore:
    """Manages all SQLite operations for the platform."""

    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def _conn(self):
        """Create a new SQLite connection with WAL mode for concurrent access."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        conn = self._conn()
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE,
                company_name TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS stock_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # NEW: Cache for AI concall analysis results
        c.execute("""
            CREATE TABLE IF NOT EXISTS concall_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                quarter TEXT,
                transcript_url TEXT,
                sentiment_json TEXT,
                analyzer_type TEXT DEFAULT 'lexicon',
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, quarter, analyzer_type)
            )
        """)

        # NEW: Milestone tracking extracted from concalls
        c.execute("""
            CREATE TABLE IF NOT EXISTS milestone_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                milestone_name TEXT,
                status TEXT,
                start_quarter TEXT,
                last_updated_quarter TEXT,
                description_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, milestone_name)
            )
        """)

        # NEW: Cashflow analysis cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS cashflow_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE,
                analysis_json TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # NEW: Cross-quarter intelligence cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS cross_quarter_intelligence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE,
                intelligence_json TEXT,
                quarters_analyzed INTEGER DEFAULT 0,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # NEW: Vahan daily sales cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS vahan_daily_sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                maker TEXT,
                date TEXT,
                registrations INTEGER,
                UNIQUE(maker, date)
            )
        """)

        # NEW: Vahan cumulative MTD snapshots (source of truth)
        c.execute("""
            CREATE TABLE IF NOT EXISTS vahan_cumulative_snapshots (
                maker TEXT,
                date TEXT,
                cumulative_mtd INTEGER,
                month INTEGER,
                year INTEGER,
                source TEXT DEFAULT 'estimated',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(maker, date)
            )
        """)

        # NEW: Financial statements cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS financial_statements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                quarter TEXT,
                statement_json TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, quarter)
            )
        """)

        # NEW: Insider SAST trades cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS insider_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                trade_date TEXT,
                person_category TEXT,
                transaction_type TEXT,
                quantity INTEGER,
                value_in_lakhs REAL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, trade_date, person_category, quantity, transaction_type)
            )
        """)

        # NEW: 10-Signal Stock Predictions cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS stock_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE,
                trajectory_score REAL,
                stance TEXT,
                signal_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # NEW: Pipeline Checkpoint resumable state cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_checkpoint (
                pipeline_name TEXT PRIMARY KEY,
                current_stage INTEGER,
                stage_name TEXT,
                last_processed_symbol TEXT,
                completed_symbols_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # NEW: Backtest Results cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE,
                hit_rate_pct REAL,
                backtest_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # NEW: Multi-Source Document Catalog Index
        c.execute("""
            CREATE TABLE IF NOT EXISTS documents_index (
                doc_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                quarter TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                source_used TEXT NOT NULL,
                category TEXT NOT NULL,
                local_path TEXT,
                checksum TEXT,
                filing_date TEXT,
                bse_scrip_code TEXT,
                file_size_bytes INTEGER DEFAULT 0,
                extraction_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, quarter, category, source_used, url)
            )
        """)

        # NEW: Ground-Truth Financial Metrics extracted from PDFs
        c.execute("""
            CREATE TABLE IF NOT EXISTS ground_truth_financials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                quarter TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                revenue_cr REAL,
                ebitda_cr REAL,
                pat_cr REAL,
                revenue_growth_pct REAL,
                ebitda_margin_pct REAL,
                pat_growth_pct REAL,
                segment_results_json TEXT,
                capex_cr REAL,
                guidance_numbers_json TEXT,
                extraction_confidence REAL DEFAULT 1.0,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_pdf_url TEXT,
                source_local_path TEXT,
                ground_truth_json TEXT,
                UNIQUE(symbol, quarter, doc_type)
            )
        """)

        # NEW: Index Stocks Catalog Cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS index_stocks (
                symbol TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'LARGE_CAP',
                index_name TEXT DEFAULT 'BSE 500',
                mcap_cr REAL DEFAULT 0.0,
                sector TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # NEW: Mutual Fund Schemes Cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS mf_schemes_cache (
                scheme_id INTEGER PRIMARY KEY,
                scheme_name TEXT NOT NULL,
                amc_name TEXT NOT NULL,
                category TEXT,
                aum_cr REAL,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # NEW: Mutual Fund Stock Holdings Monthly Snapshots Cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS mf_holdings_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scheme_id INTEGER,
                symbol TEXT,
                as_of_date TEXT,
                shares_held INTEGER,
                market_value_cr REAL,
                portfolio_weight_pct REAL,
                mom_share_change INTEGER DEFAULT 0,
                action_type TEXT,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(scheme_id, symbol, as_of_date)
            )
        """)

        # NEW: Incremental Sync Metadata Watermark Tracker
        c.execute("""
            CREATE TABLE IF NOT EXISTS sync_metadata (
                table_name TEXT PRIMARY KEY,
                last_synced_at TEXT,
                row_count INTEGER DEFAULT 0
            )
        """)

        conn.commit()
        self._migrate_schema(conn)

    def _migrate_schema(self, conn):
        """Ensure all table schemas are up-to-date by adding any missing columns."""
        column_migrations = {
            "concall_analysis": [
                ("analyzer_type", "TEXT DEFAULT 'lexicon'"),
                ("score", "REAL DEFAULT 0.7"),
                ("sentiment", "TEXT DEFAULT 'positive'"),
                ("confidence", "TEXT DEFAULT 'high'"),
                ("summary", "TEXT"),
                ("positive_drivers", "TEXT"),
                ("key_risks", "TEXT"),
                ("guidance_numbers", "TEXT"),
            ],
            "cross_quarter_intelligence": [("quarters_analyzed", "INTEGER DEFAULT 0")],
            "vahan_cumulative_snapshots": [("source", "TEXT DEFAULT 'estimated'")],
            "stock_predictions": [
                ("stance", "TEXT DEFAULT 'ACCUMULATE'"),
                ("signal_json", "TEXT"),
                ("current_price", "REAL DEFAULT 0.0"),
                ("target_bear", "REAL"),
                ("target_base", "REAL"),
                ("target_bull", "REAL"),
                ("signal_scores", "TEXT"),
                ("key_drivers", "TEXT"),
                ("governance_flags", "TEXT"),
            ],
            "index_stocks": [
                ("market_cap_tier", "TEXT DEFAULT 'LARGE_CAP'"),
                ("market_cap_cr", "REAL DEFAULT 0.0"),
            ],
        }
        c = conn.cursor()
        for table, cols in column_migrations.items():
            try:
                c.execute(f"PRAGMA table_info({table})")
                existing_cols = {row[1] for row in c.fetchall()}
                for col_name, col_def in cols:
                    if col_name not in existing_cols:
                        c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass
        conn.commit()
        conn.close()



    # --- Watchlist ---
    def add_to_watchlist(self, symbol: str, company_name: str) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO watchlist (symbol, company_name) VALUES (?, ?)",
                (symbol, company_name),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def remove_from_watchlist(self, symbol: str):
        conn = self._conn()
        conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
        conn.commit()
        conn.close()

    def get_watchlist(self) -> pd.DataFrame:
        conn = self._conn()
        df = pd.read_sql_query(
            "SELECT symbol, company_name, added_date FROM watchlist ORDER BY added_date DESC",
            conn,
        )
        conn.close()
        return df

    # --- Notes ---
    def add_note(self, symbol: str, note: str):
        conn = self._conn()
        conn.execute(
            "INSERT INTO stock_notes (symbol, note) VALUES (?, ?)",
            (symbol, note),
        )
        conn.commit()
        conn.close()

    def get_notes(self, symbol: str) -> pd.DataFrame:
        conn = self._conn()
        df = pd.read_sql_query(
            "SELECT note, created_at FROM stock_notes WHERE symbol = ? ORDER BY created_at DESC",
            conn,
            params=(symbol,),
        )
        conn.close()
        return df

    # --- Concall Analysis Cache ---
    def save_analysis(self, symbol: str, quarter: str, transcript_url: str,
                      sentiment_dict: dict, analyzer_type: str = "lexicon"):
        """Cache an analysis result so we don't re-analyze the same transcript."""
        conn = self._conn()
        try:
            # Delete any existing record for this transcript_url to prevent duplicate rows
            conn.execute(
                "DELETE FROM concall_analysis WHERE symbol=? AND transcript_url=? AND analyzer_type=?",
                (symbol, transcript_url, analyzer_type),
            )
            conn.execute(
                """INSERT INTO concall_analysis
                   (symbol, quarter, transcript_url, sentiment_json, analyzer_type, analyzed_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (symbol, quarter, transcript_url,
                 json.dumps(sentiment_dict, ensure_ascii=False), analyzer_type),
            )
            conn.commit()
        finally:
            conn.close()

    def get_analysis(self, symbol: str, quarter: str,
                     analyzer_type: str = "lexicon") -> Optional[dict]:
        """Retrieve cached analysis for a specific quarter."""
        conn = self._conn()
        row = conn.execute(
            "SELECT sentiment_json FROM concall_analysis WHERE symbol=? AND quarter=? AND analyzer_type=?",
            (symbol, quarter, analyzer_type),
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None

    def get_all_analyses(self, symbol: str, analyzer_type: str = None) -> list[dict]:
        """Retrieve all cached analyses for a stock."""
        conn = self._conn()
        if analyzer_type:
            rows = conn.execute(
                "SELECT quarter, sentiment_json, analyzer_type, analyzed_at FROM concall_analysis WHERE symbol=? AND analyzer_type=? ORDER BY analyzed_at ASC",
                (symbol, analyzer_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT quarter, sentiment_json, analyzer_type, analyzed_at FROM concall_analysis WHERE symbol=? ORDER BY analyzed_at ASC",
                (symbol,),
            ).fetchall()
        conn.close()

        results = []
        for quarter, sj, at, analyzed_at in rows:
            data = json.loads(sj)
            data["quarter"] = quarter
            data["analyzer_type"] = at
            data["analyzed_at"] = analyzed_at
            results.append(data)
        return results

    def get_analysis_by_url(self, symbol: str, url: str,
                            analyzer_type: str = "lexicon") -> Optional[dict]:
        """Retrieve cached analysis by transcript URL (for incremental re-analysis)."""
        conn = self._conn()
        row = conn.execute(
            "SELECT sentiment_json FROM concall_analysis WHERE symbol=? AND transcript_url=? AND analyzer_type=?",
            (symbol, url, analyzer_type),
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None

    # --- Milestone Tracks ---
    def save_milestone(self, symbol: str, milestone: dict):
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO milestone_tracks
               (symbol, milestone_name, status, start_quarter, last_updated_quarter,
                description_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (symbol, milestone["name"], milestone["status"],
             milestone.get("start_quarter", ""),
             milestone.get("current_quarter", ""),
             json.dumps(milestone, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def get_milestones(self, symbol: str) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT description_json FROM milestone_tracks WHERE symbol=? ORDER BY start_quarter",
            (symbol,),
        ).fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]

    def clear_analyses(self, symbol: str):
        """Clear cached analyses and document catalog index for a stock (force re-analysis)."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM concall_analysis WHERE symbol = ?", (symbol,))
            conn.execute("DELETE FROM milestone_tracks WHERE symbol = ?", (symbol,))
            conn.execute("DELETE FROM documents_index WHERE symbol = ?", (symbol,))
            conn.execute("DELETE FROM ground_truth_financials WHERE symbol = ?", (symbol,))
            conn.commit()
        except sqlite3.OperationalError as e:
            print(f"[SQLiteStore] Error clearing analyses: {e}")
        finally:
            conn.close()

    def clear_documents(self, symbol: str):
        """Clear document catalog index for a symbol to force fresh document discovery."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM documents_index WHERE symbol = ?", (symbol,))
            conn.execute("DELETE FROM ground_truth_financials WHERE symbol = ?", (symbol,))
            conn.commit()
        except sqlite3.OperationalError as e:
            print(f"[SQLiteStore] Error clearing documents index: {e}")
        finally:
            conn.close()

    def delete_analysis(self, symbol: str, quarter: str, analyzer_type: str):
        """Delete a specific analysis record (Issue #4: public interface for cleanup)."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM concall_analysis WHERE symbol=? AND quarter=? AND analyzer_type=?",
                (symbol, quarter, analyzer_type)
            )
            conn.commit()
        except sqlite3.OperationalError as e:
            print(f"[SQLiteStore] Error deleting analysis: {e}")
        finally:
            conn.close()

    # --- Cashflow Data Cache ---
    def save_cashflow(self, symbol: str, analysis_dict: dict):
        """Cache the complete cashflow analysis result."""
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO cashflow_data
               (symbol, analysis_json, fetched_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (symbol, json.dumps(analysis_dict, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def get_cashflow(self, symbol: str) -> Optional[dict]:
        """Retrieve cached cashflow analysis."""
        conn = self._conn()
        row = conn.execute(
            "SELECT analysis_json FROM cashflow_data WHERE symbol=?",
            (symbol,),
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None

    def clear_cashflow(self, symbol: str):
        """Clear cached cashflow data for a stock."""
        conn = self._conn()
        conn.execute("DELETE FROM cashflow_data WHERE symbol = ?", (symbol,))
        conn.commit()
        conn.close()

    # --- Cross-Quarter Intelligence ---
    def save_intelligence(self, symbol: str, intelligence_dict: dict, quarters: int = 0):
        """Cache cross-quarter intelligence synthesis."""
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO cross_quarter_intelligence
               (symbol, intelligence_json, quarters_analyzed)
               VALUES (?, ?, ?)""",
            (symbol, json.dumps(intelligence_dict, ensure_ascii=False), quarters),
        )
        conn.commit()
        conn.close()

    def get_intelligence(self, symbol: str) -> Optional[dict]:
        """Retrieve cached intelligence synthesis.
        Returns tuple of (intelligence_dict, cached_quarters) or (None, 0)."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT intelligence_json, quarters_analyzed FROM cross_quarter_intelligence WHERE symbol=?",
                (symbol,),
            ).fetchone()
        except sqlite3.OperationalError as e:
            print(f"[SQLiteStore] Error reading intelligence: {e}")
            conn.close()
            return None
        conn.close()
        if row:
            data = json.loads(row[0])
            # Issue: Don't inject _cached_quarters into the dict. Store it separately.
            data["_cached_quarters"] = row[1]
            return data
        return None

    def clear_intelligence(self, symbol: str):
        """Clear cached intelligence for a stock."""
        conn = self._conn()
        conn.execute("DELETE FROM cross_quarter_intelligence WHERE symbol = ?", (symbol,))
        conn.commit()
        conn.close()

    # --- Vahan Daily Sales Cache ---
    def save_vahan_daily_sales(self, maker: str, date: str, registrations: int):
        """Insert or replace daily registration record."""
        conn = self._conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO vahan_daily_sales (maker, date, registrations)
                VALUES (?, ?, ?)
            """, (maker, date, registrations))
            conn.commit()
        finally:
            conn.close()

    def get_vahan_daily_sales(self) -> pd.DataFrame:
        """Fetch all saved daily registration records."""
        conn = self._conn()
        try:
            df = pd.read_sql_query("SELECT maker, date, registrations FROM vahan_daily_sales", conn)
            return df
        finally:
            conn.close()

    def clear_vahan_daily_sales_month(self, maker: str, month: int, year: int):
        """Clear interpolated daily values for a maker in a specific month (for re-interpolation)."""
        conn = self._conn()
        try:
            date_prefix = f"{year}-{month:02d}-%"
            conn.execute("DELETE FROM vahan_daily_sales WHERE maker = ? AND date LIKE ?", (maker, date_prefix))
            conn.commit()
        finally:
            conn.close()

    # --- Vahan Cumulative Snapshots ---
    def save_vahan_snapshot(self, maker: str, date: str, cumulative_mtd: int,
                           month: int, year: int, source: str = "estimated"):
        """Insert or replace a cumulative MTD snapshot for a maker on a date."""
        conn = self._conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO vahan_cumulative_snapshots
                (maker, date, cumulative_mtd, month, year, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (maker, date, cumulative_mtd, month, year, source))
            conn.commit()
        finally:
            conn.close()

    def get_vahan_snapshots(self, maker: str, month: int, year: int) -> list[dict]:
        """Get all cumulative snapshots for a maker in a given month, ordered by date."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT date, cumulative_mtd, source FROM vahan_cumulative_snapshots "
                "WHERE maker = ? AND month = ? AND year = ? ORDER BY date ASC",
                (maker, month, year)
            ).fetchall()
            return [{"date": r[0], "cumulative_mtd": r[1], "source": r[2]} for r in rows]
        finally:
            conn.close()

    def get_latest_vahan_snapshot(self, maker: str, month: int, year: int) -> Optional[dict]:
        """Get the most recent cumulative snapshot for a maker in a given month."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT date, cumulative_mtd, source FROM vahan_cumulative_snapshots "
                "WHERE maker = ? AND month = ? AND year = ? ORDER BY date DESC LIMIT 1",
                (maker, month, year)
            ).fetchone()
            if row:
                return {"date": row[0], "cumulative_mtd": row[1], "source": row[2]}
            return None
        finally:
            conn.close()

    def get_vahan_snapshot_for_date(self, maker: str, date: str) -> Optional[dict]:
        """Get the snapshot for a specific maker and date."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT date, cumulative_mtd, source FROM vahan_cumulative_snapshots "
                "WHERE maker = ? AND date = ?",
                (maker, date)
            ).fetchone()
            if row:
                return {"date": row[0], "cumulative_mtd": row[1], "source": row[2]}
            return None
        finally:
            conn.close()

    # --- Predictions Cache ---
    def save_prediction(self, symbol: str, score: float, stance: str, signal_dict: dict):
        """Insert or replace stock trajectory prediction."""
        conn = self._conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO stock_predictions (symbol, trajectory_score, stance, signal_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (symbol, score, stance, json.dumps(signal_dict)))
            conn.commit()
        finally:
            conn.close()

    def get_prediction(self, symbol: str) -> Optional[dict]:
        """Fetch saved prediction for a ticker."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT trajectory_score, stance, signal_json FROM stock_predictions WHERE symbol=?", (symbol,)).fetchone()
            if row:
                return {
                    "trajectory_score": row[0],
                    "stance": row[1],
                    "signal_breakdown": json.loads(row[2])
                }
            return None
        finally:
            conn.close()

    def get_all_predictions(self) -> pd.DataFrame:
        """Fetch all stock predictions as a DataFrame."""
        conn = self._conn()
        try:
            df = pd.read_sql_query("SELECT symbol, trajectory_score, stance, updated_at FROM stock_predictions", conn)
            return df
        finally:
            conn.close()

    # --- Pipeline Checkpoints (Resumable State) ---
    def save_checkpoint(self, pipeline_name: str, current_stage: int, stage_name: str, last_processed_symbol: str, completed_symbols_list: list):
        """Save pipeline progress state for resumability."""
        conn = self._conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO pipeline_checkpoint (pipeline_name, current_stage, stage_name, last_processed_symbol, completed_symbols_json, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (pipeline_name, current_stage, stage_name, last_processed_symbol, json.dumps(completed_symbols_list)))
            conn.commit()
        except Exception as e:
            print(f"[SQLiteStore] Checkpoint save error: {e}")
        finally:
            conn.close()

    def get_checkpoint(self, pipeline_name: str) -> Optional[dict]:
        """Load saved checkpoint for a pipeline."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT current_stage, stage_name, last_processed_symbol, completed_symbols_json FROM pipeline_checkpoint WHERE pipeline_name=?", (pipeline_name,)).fetchone()
            if row:
                return {
                    "current_stage": row[0],
                    "stage_name": row[1],
                    "last_processed_symbol": row[2],
                    "completed_symbols": json.loads(row[3])
                }
            return None
        finally:
            conn.close()

    # --- Backtest Cache ---
    def save_backtest_result(self, symbol: str, hit_rate_pct: float, backtest_dict: dict):
        """Save a historical backtest result."""
        conn = self._conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO backtest_results (symbol, hit_rate_pct, backtest_json, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (symbol, hit_rate_pct, json.dumps(backtest_dict)))
            conn.commit()
        finally:
            conn.close()

    def get_backtest_result(self, symbol: str) -> Optional[dict]:
        """Load a historical backtest result."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT hit_rate_pct, backtest_json FROM backtest_results WHERE symbol=?", (symbol,)).fetchone()
            if row:
                res = json.loads(row[1])
                res["hit_rate_pct"] = row[0]
                return res
            return None
        finally:
            conn.close()

    # --- Multi-Source Document Catalog Index ---
    def save_document_index(self, doc) -> str:
        """Insert or update a document record in documents_index table."""
        conn = self._conn()
        try:
            if hasattr(doc, "model_dump"):
                data = doc.model_dump()
            elif isinstance(doc, dict):
                data = doc.copy()
            else:
                raise ValueError("doc must be a Pydantic model or dict")

            import hashlib
            doc_id = data.get("doc_id")
            symbol = data.get("symbol", "")
            quarter = data.get("quarter", "")
            title = data.get("title", "")
            url = data.get("url", "")
            source_used = data.get("source_used", "BSE")
            category = data.get("category", "other")
            local_path = data.get("local_path")
            checksum = data.get("checksum")
            filing_date = data.get("filing_date")
            bse_scrip_code = data.get("bse_scrip_code")
            file_size_bytes = data.get("file_size_bytes", 0)
            extraction_status = data.get("extraction_status", "pending")

            if not doc_id:
                raw_key = f"{symbol}:{quarter}:{category}:{source_used}:{url}"
                doc_id = hashlib.md5(raw_key.encode('utf-8')).hexdigest()

            conn.execute("""
                INSERT OR REPLACE INTO documents_index
                (doc_id, symbol, quarter, title, url, source_used, category,
                 local_path, checksum, filing_date, bse_scrip_code, file_size_bytes, extraction_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id, symbol, quarter, title, url, source_used, category,
                local_path, checksum, filing_date, bse_scrip_code, file_size_bytes, extraction_status
            ))
            conn.commit()
            return doc_id
        finally:
            conn.close()

    def get_documents_index(self, symbol: str = None, category: str = None) -> list[dict]:
        """Fetch documents from documents_index table filtered by symbol and/or category."""
        conn = self._conn()
        try:
            query = "SELECT doc_id, symbol, quarter, title, url, source_used, category, local_path, checksum, filing_date, bse_scrip_code, file_size_bytes, extraction_status, created_at FROM documents_index"
            params = []
            conditions = []
            if symbol:
                conditions.append("symbol = ?")
                params.append(symbol)
            if category:
                conditions.append("category = ?")
                params.append(category)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, params).fetchall()
            cols = ["doc_id", "symbol", "quarter", "title", "url", "source_used", "category", "local_path", "checksum", "filing_date", "bse_scrip_code", "file_size_bytes", "extraction_status", "created_at"]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            conn.close()

    def get_documents_by_symbol_and_quarter(self, symbol: str, quarter: str) -> list[dict]:
        """Fetch documents for a specific symbol and quarter."""
        conn = self._conn()
        try:
            query = "SELECT doc_id, symbol, quarter, title, url, source_used, category, local_path, checksum, filing_date, bse_scrip_code, file_size_bytes, extraction_status, created_at FROM documents_index WHERE symbol = ? AND quarter = ? ORDER BY created_at DESC"
            rows = conn.execute(query, (symbol, quarter)).fetchall()
            cols = ["doc_id", "symbol", "quarter", "title", "url", "source_used", "category", "local_path", "checksum", "filing_date", "bse_scrip_code", "file_size_bytes", "extraction_status", "created_at"]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            conn.close()

    # --- Ground Truth Financials ---
    def save_ground_truth(self, ground_truth: GroundTruthFinancials | dict) -> bool:
        """
        Save or update ground-truth financial metrics in SQLite.
        Accepts a GroundTruthFinancials object or a dictionary.
        """
        if isinstance(ground_truth, dict):
            gt = GroundTruthFinancials(**ground_truth)
        else:
            gt = ground_truth

        gt_dict = gt.model_dump()
        if not gt_dict.get("extracted_at"):
            gt_dict["extracted_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO ground_truth_financials (
                    symbol, quarter, doc_type, revenue_cr, ebitda_cr, pat_cr,
                    revenue_growth_pct, ebitda_margin_pct, pat_growth_pct,
                    segment_results_json, capex_cr, guidance_numbers_json,
                    extraction_confidence, extracted_at, source_pdf_url,
                    source_local_path, ground_truth_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gt.symbol,
                    gt.quarter,
                    gt.doc_type,
                    gt.revenue_cr,
                    gt.ebitda_cr,
                    gt.pat_cr,
                    gt.revenue_growth_pct,
                    gt.ebitda_margin_pct,
                    gt.pat_growth_pct,
                    json.dumps(gt.segment_results, ensure_ascii=False),
                    gt.capex_cr,
                    json.dumps(gt.guidance_numbers, ensure_ascii=False),
                    gt.extraction_confidence,
                    gt_dict["extracted_at"],
                    gt.source_pdf_url,
                    gt.source_local_path,
                    json.dumps(gt_dict, ensure_ascii=False),
                ),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_ground_truth(
        self, symbol: str, quarter: str, doc_type: Optional[str] = None
    ) -> Optional[GroundTruthFinancials]:
        """
        Retrieve ground-truth financial metrics for a symbol and quarter.
        If doc_type is omitted, prioritizes 'financial_results' over 'presentation'.
        Returns GroundTruthFinancials or None.
        """
        conn = self._conn()
        try:
            if doc_type:
                row = conn.execute(
                    """
                    SELECT ground_truth_json FROM ground_truth_financials
                    WHERE symbol = ? AND quarter = ? AND doc_type = ?
                    """,
                    (symbol, quarter, doc_type),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT ground_truth_json FROM ground_truth_financials
                    WHERE symbol = ? AND quarter = ?
                    ORDER BY CASE doc_type
                        WHEN 'financial_results' THEN 1
                        WHEN 'presentation' THEN 2
                        ELSE 3 END ASC
                    LIMIT 1
                    """,
                    (symbol, quarter),
                ).fetchone()

            if not row or not row[0]:
                return None
            data = json.loads(row[0])
            return GroundTruthFinancials(**data)
        finally:
            conn.close()

    def get_all_ground_truth_for_symbol(
        self, symbol: str
    ) -> list[GroundTruthFinancials]:
        """
        Retrieve all ground-truth financial entries for a given symbol.
        Returns list of GroundTruthFinancials objects.
        """
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT ground_truth_json FROM ground_truth_financials
                WHERE symbol = ?
                ORDER BY extracted_at DESC
                """,
                (symbol,),
            ).fetchall()
            results = []
            for r in rows:
                if r[0]:
                    try:
                        data = json.loads(r[0])
                        results.append(GroundTruthFinancials(**data))
                    except Exception:
                        pass
            return results
        finally:
            conn.close()

    # ====================================================================
    # MF Holdings & Index Stock Cache Operations
    # ====================================================================

    def save_index_stocks(self, stocks: list) -> int:
        """Bulk upsert NSE/BSE index stocks into local catalog cache."""
        if not stocks:
            return 0
        conn = self._conn()
        count = 0
        try:
            for s in stocks:
                conn.execute(
                    """
                    INSERT INTO index_stocks (symbol, company_name, tier, index_name, mcap_cr, sector, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(symbol) DO UPDATE SET
                        company_name = excluded.company_name,
                        tier = excluded.tier,
                        index_name = excluded.index_name,
                        mcap_cr = excluded.mcap_cr,
                        sector = excluded.sector,
                        updated_at = datetime('now')
                    """,
                    (
                        s.get("symbol"),
                        s.get("company_name", ""),
                        s.get("tier", s.get("market_cap_tier", "LARGE_CAP")),
                        s.get("index_name", "BSE 500"),
                        s.get("mcap_cr", s.get("market_cap_cr", 0.0)),
                        s.get("sector", "Equities"),
                    )
                )
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def get_index_stocks(self, tier: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch cached index stocks, optionally filtered by market cap tier."""
        conn = self._conn()
        try:
            if tier and tier != "ALL":
                rows = conn.execute(
                    "SELECT symbol, company_name, tier, index_name, mcap_cr, sector, updated_at FROM index_stocks WHERE tier = ? ORDER BY symbol ASC",
                    (tier,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT symbol, company_name, tier, index_name, mcap_cr, sector, updated_at FROM index_stocks ORDER BY symbol ASC"
                ).fetchall()
            cols = ["symbol", "company_name", "tier", "index_name", "mcap_cr", "sector", "updated_at"]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            conn.close()

    def search_index_stocks(self, query: str = "", tier: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        """Search stocks in index universe with scheme holding count."""
        conn = self._conn()
        try:
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
            cols = ["symbol", "company_name", "tier", "index_name", "mcap_cr", "sector", "mf_scheme_count"]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            conn.close()

    def save_mf_schemes_cache(self, schemes: list) -> int:
        """Bulk upsert MF scheme metadata into local cache."""
        if not schemes:
            return 0
        conn = self._conn()
        count = 0
        try:
            for s in schemes:
                conn.execute(
                    """
                    INSERT INTO mf_schemes_cache (scheme_id, scheme_name, amc_name, category, aum_cr, synced_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(scheme_id) DO UPDATE SET
                        scheme_name = excluded.scheme_name,
                        amc_name = excluded.amc_name,
                        category = excluded.category,
                        aum_cr = excluded.aum_cr,
                        synced_at = datetime('now')
                    """,
                    (
                        s.get("scheme_id"),
                        s.get("scheme_name", ""),
                        s.get("amc_name", ""),
                        s.get("category"),
                        s.get("aum_cr")
                    )
                )
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def get_mf_schemes_cache(self, amc_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch cached MF schemes, optionally filtered by AMC name."""
        conn = self._conn()
        try:
            if amc_name:
                rows = conn.execute(
                    "SELECT scheme_id, scheme_name, amc_name, category, aum_cr, synced_at FROM mf_schemes_cache WHERE amc_name = ? ORDER BY scheme_name",
                    (amc_name,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT scheme_id, scheme_name, amc_name, category, aum_cr, synced_at FROM mf_schemes_cache ORDER BY amc_name, scheme_name"
                ).fetchall()
            cols = ["scheme_id", "scheme_name", "amc_name", "category", "aum_cr", "synced_at"]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            conn.close()

    def save_mf_holdings_cache(self, holdings: list) -> int:
        """Bulk upsert MF stock holdings into local cache."""
        if not holdings:
            return 0
        conn = self._conn()
        count = 0
        try:
            for h in holdings:
                conn.execute(
                    """
                    INSERT INTO mf_holdings_cache 
                    (scheme_id, symbol, as_of_date, shares_held, market_value_cr,
                     portfolio_weight_pct, mom_share_change, action_type, synced_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(scheme_id, symbol, as_of_date) DO UPDATE SET
                        shares_held = excluded.shares_held,
                        market_value_cr = excluded.market_value_cr,
                        portfolio_weight_pct = excluded.portfolio_weight_pct,
                        mom_share_change = excluded.mom_share_change,
                        action_type = excluded.action_type,
                        synced_at = datetime('now')
                    """,
                    (
                        h.get("scheme_id"),
                        h.get("symbol"),
                        h.get("as_of_date"),
                        h.get("shares_held", 0),
                        h.get("market_value_cr"),
                        h.get("portfolio_weight_pct"),
                        h.get("mom_share_change", 0),
                        h.get("action_type")
                    )
                )
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def get_mf_holdings_cache(
        self,
        symbol: Optional[str] = None,
        action_type: Optional[str] = None,
        as_of_date: Optional[str] = None,
        scheme_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch cached MF holdings with optional filters."""
        conn = self._conn()
        try:
            query = "SELECT id, scheme_id, symbol, as_of_date, shares_held, market_value_cr, portfolio_weight_pct, mom_share_change, action_type, synced_at FROM mf_holdings_cache WHERE 1=1"
            params = []
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            if action_type:
                query += " AND action_type = ?"
                params.append(action_type)
            if as_of_date:
                query += " AND as_of_date = ?"
                params.append(as_of_date)
            if scheme_id is not None:
                query += " AND scheme_id = ?"
                params.append(scheme_id)
            query += " ORDER BY symbol, scheme_id"
            rows = conn.execute(query, params).fetchall()
            cols = ["id", "scheme_id", "symbol", "as_of_date", "shares_held", "market_value_cr", "portfolio_weight_pct", "mom_share_change", "action_type", "synced_at"]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            conn.close()

    def get_mf_holdings_summary(
        self,
        as_of_date: Optional[str] = None,
        action_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Aggregated stock-level MF holdings summary."""
        conn = self._conn()
        try:
            query = """
                SELECT
                    h.symbol,
                    COUNT(DISTINCT h.scheme_id) AS scheme_count,
                    SUM(h.shares_held) AS total_shares_held,
                    SUM(h.market_value_cr) AS total_market_value_cr,
                    SUM(h.mom_share_change) AS net_mom_change,
                    SUM(CASE WHEN h.action_type = 'FRESH_ENTRY' THEN 1 ELSE 0 END) AS fresh_entry_count,
                    SUM(CASE WHEN h.action_type = 'COMPLETE_EXIT' THEN 1 ELSE 0 END) AS exit_count,
                    SUM(CASE WHEN h.action_type = 'STAKE_INCREASE' THEN 1 ELSE 0 END) AS increase_count,
                    SUM(CASE WHEN h.action_type = 'STAKE_REDUCTION' THEN 1 ELSE 0 END) AS decrease_count
                FROM mf_holdings_cache h
                WHERE 1=1
            """
            params = []
            if as_of_date:
                query += " AND h.as_of_date = ?"
                params.append(as_of_date)
            if action_types:
                placeholders = ",".join(["?"] * len(action_types))
                query += f" AND h.action_type IN ({placeholders})"
                params.extend(action_types)
            query += " GROUP BY h.symbol ORDER BY net_mom_change DESC"
            rows = conn.execute(query, params).fetchall()
            cols = [
                "symbol", "scheme_count", "total_shares_held", "total_market_value_cr",
                "net_mom_change", "fresh_entry_count", "exit_count", "increase_count", "decrease_count"
            ]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            conn.close()

    def get_top_accumulated_stocks(self, as_of_date: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Top stocks by net accumulation (STAKE_INCREASE + FRESH_ENTRY)."""
        conn = self._conn()
        try:
            query = """
                SELECT symbol, 
                       SUM(mom_share_change) AS net_accumulation,
                       COUNT(DISTINCT scheme_id) AS scheme_count,
                       SUM(market_value_cr) AS total_value_cr
                FROM mf_holdings_cache
                WHERE action_type IN ('STAKE_INCREASE', 'FRESH_ENTRY')
            """
            params = []
            if as_of_date:
                query += " AND as_of_date = ?"
                params.append(as_of_date)
            query += " GROUP BY symbol ORDER BY net_accumulation DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            cols = ["symbol", "net_accumulation", "scheme_count", "total_value_cr"]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            conn.close()

    def get_top_distributed_stocks(self, as_of_date: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Top stocks by net distribution (STAKE_REDUCTION + COMPLETE_EXIT)."""
        conn = self._conn()
        try:
            query = """
                SELECT symbol,
                       SUM(mom_share_change) AS net_distribution,
                       COUNT(DISTINCT scheme_id) AS scheme_count,
                       SUM(market_value_cr) AS total_value_cr
                FROM mf_holdings_cache
                WHERE action_type IN ('STAKE_REDUCTION', 'COMPLETE_EXIT')
            """
            params = []
            if as_of_date:
                query += " AND as_of_date = ?"
                params.append(as_of_date)
            query += " GROUP BY symbol ORDER BY net_distribution ASC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            cols = ["symbol", "net_distribution", "scheme_count", "total_value_cr"]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            conn.close()

    def get_mf_holdings_available_dates(self) -> List[str]:
        """Get distinct reporting dates from cached holdings."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT DISTINCT as_of_date FROM mf_holdings_cache WHERE as_of_date IS NOT NULL ORDER BY as_of_date DESC"
            ).fetchall()
            return [r[0] for r in rows if r[0]]
        finally:
            conn.close()

    def get_last_sync_time(self, table_name: str) -> Optional[str]:
        """Get the last successful sync timestamp for a table."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT last_synced_at FROM sync_metadata WHERE table_name = ?",
                (table_name,)
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def set_last_sync_time(self, table_name: str, timestamp: str, row_count: int = 0) -> None:
        """Update the sync watermark for a table."""
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO sync_metadata (table_name, last_synced_at, row_count)
                VALUES (?, ?, ?)
                ON CONFLICT(table_name) DO UPDATE SET
                    last_synced_at = excluded.last_synced_at,
                    row_count = excluded.row_count
                """,
                (table_name, timestamp, row_count)
            )
            conn.commit()
        finally:
            conn.close()

    def get_sync_status(self) -> List[Dict[str, Any]]:
        """Get sync status for all tracked tables."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT table_name, last_synced_at, row_count FROM sync_metadata ORDER BY table_name"
            ).fetchall()
            cols = ["table_name", "last_synced_at", "row_count"]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            conn.close()

    def get_mf_holdings_count(self) -> int:
        """Get total count of cached MF holdings."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) FROM mf_holdings_cache").fetchone()
            return row[0] if row else 0
        finally:
            conn.close()




