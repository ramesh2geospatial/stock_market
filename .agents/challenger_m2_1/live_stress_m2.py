"""
Live empirical verification of BSEProvider, ScreenerProvider, and MultiSourceDocFetcher against live endpoints.
"""
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from providers.bse_provider import BSEProvider
from providers.multi_source_doc_fetcher import MultiSourceDocFetcher
from storage.sqlite_store import SQLiteStore

def run_live_tests():
    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / "live_test.db"
    db = SQLiteStore(db_path=db_path)
    fetcher = MultiSourceDocFetcher(db_store=db, docs_base_dir=Path(temp_dir.name) / "docs")
    bse = BSEProvider(timeout=10)

    print("=== LIVE TEST 1: BSE Announcement Fetch for HDFCBANK (500180) ===")
    ann = bse.fetch_announcements("500180")
    print(f"Fetched {len(ann)} announcements from BSE for HDFCBANK.")
    if ann:
        print(f"Sample announcement: {ann[0]}")
        bse_docs = bse.fetch_documents("HDFCBANK")
        print(f"Parsed {len(bse_docs)} UnifiedDocument instances from BSE for HDFCBANK.")
        if bse_docs:
            print(f"Sample BSE doc: {bse_docs[0]}")

    print("\n=== LIVE TEST 2: MultiSourceDocFetcher for HDFCBANK ===")
    ms_docs = fetcher.fetch_documents("HDFCBANK", force_refresh=True)
    print(f"MultiSourceDocFetcher fetched {len(ms_docs)} documents for HDFCBANK.")
    sources = set(d.source_used for d in ms_docs)
    print(f"Sources used: {sources}")

    print("\n=== LIVE TEST 3: Unmapped Ticker (ZOMATO) Fallback ===")
    zomato_docs = fetcher.fetch_documents("ZOMATO", force_refresh=True)
    print(f"MultiSourceDocFetcher fetched {len(zomato_docs)} documents for ZOMATO.")
    z_sources = set(d.source_used for d in zomato_docs)
    print(f"Sources used for ZOMATO: {z_sources}")

    print("\n=== LIVE TEST 4: Invalid Ticker (INVALID_TICKER_XYZ_99) ===")
    inv_docs = fetcher.fetch_documents("INVALID_TICKER_XYZ_99", force_refresh=True)
    print(f"MultiSourceDocFetcher fetched {len(inv_docs)} documents for INVALID_TICKER_XYZ_99.")

    temp_dir.cleanup()

if __name__ == "__main__":
    run_live_tests()
