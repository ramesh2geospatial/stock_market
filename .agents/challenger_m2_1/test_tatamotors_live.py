import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from providers.multi_source_doc_fetcher import MultiSourceDocFetcher
from storage.sqlite_store import SQLiteStore

temp_dir = tempfile.TemporaryDirectory()
db_path = Path(temp_dir.name) / "test_tatamotors.db"
db = SQLiteStore(db_path=db_path)
fetcher = MultiSourceDocFetcher(db_store=db, docs_base_dir=Path(temp_dir.name) / "docs")

docs = fetcher.fetch_documents("TATAMOTORS", force_refresh=True)
print(f"Total documents fetched for TATAMOTORS across all 3 tiers: {len(docs)}")
temp_dir.cleanup()
