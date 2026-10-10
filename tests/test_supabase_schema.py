"""
Unit & Integration validation tests for Supabase PostgreSQL Schema (docs/supabase_schema.sql).
Validates table DDL, RLS policies, indexing structures, and RPC definitions.
"""
import unittest
import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "docs" / "supabase_schema.sql"


class TestSupabaseSchema(unittest.TestCase):

    def setUp(self):
        self.assertTrue(SCHEMA_PATH.exists(), f"Schema file {SCHEMA_PATH} must exist")
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            self.schema_sql = f.read()

    def test_required_extensions_present(self):
        """Verify PostgreSQL extensions are enabled."""
        for ext in ["uuid-ossp", "pg_trgm", "citext"]:
            pattern = rf'CREATE\s+EXTENSION\s+IF\s+NOT\s+EXISTS\s+["\']?{ext}["\']?'
            self.assertRegex(self.schema_sql, pattern, f"Extension {ext} must be enabled")

    def test_core_tables_defined(self):
        """Verify all core tables are declared in DDL."""
        tables = [
            "index_stocks",
            "mf_schemes",
            "mf_stock_holdings",
            "stock_financials",
            "stock_predictions",
            "concall_analyses",
        ]
        for tbl in tables:
            pattern = rf'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{tbl}\s*\('
            self.assertRegex(self.schema_sql, pattern, f"Table {tbl} must be defined in schema")

    def test_rls_enabled_and_hardened(self):
        """Verify RLS is enabled on all tables and public mutations are not permitted."""
        tables = [
            "index_stocks",
            "mf_schemes",
            "mf_stock_holdings",
            "stock_financials",
            "stock_predictions",
            "concall_analyses",
        ]
        for tbl in tables:
            enable_pattern = rf'ALTER\s+TABLE\s+{tbl}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY'
            self.assertRegex(self.schema_sql, enable_pattern, f"RLS must be enabled on {tbl}")
            
            read_policy_pattern = rf'CREATE\s+POLICY\s+\w+\s+ON\s+{tbl}\s+FOR\s+SELECT\s+TO\s+anon,\s*authenticated'
            self.assertRegex(self.schema_sql, read_policy_pattern, f"Read policy for anon/authenticated must exist on {tbl}")

        # Ensure no overly permissive 'FOR ALL TO public' policies exist
        self.assertNotRegex(
            self.schema_sql,
            r'CREATE\s+POLICY\s+\w+\s+ON\s+\w+\s+FOR\s+ALL\s+TO\s+public',
            "Insecure 'FOR ALL TO public' policy must NOT exist"
        )

    def test_rpc_contribute_snapshot_exists(self):
        """Verify contribute_stock_holding_snapshot RPC function is defined with SECURITY DEFINER."""
        pattern = r'CREATE\s+OR\s+REPLACE\s+FUNCTION\s+contribute_stock_holding_snapshot'
        self.assertRegex(self.schema_sql, pattern, "contribute_stock_holding_snapshot RPC must exist")
        self.assertIn("SECURITY DEFINER", self.schema_sql)

    def test_incremental_sync_indexes_exist(self):
        """Verify indexes on created_at and updated_at exist for efficient delta syncing."""
        self.assertIn("idx_holdings_created_at", self.schema_sql)
        self.assertIn("idx_holdings_updated_at", self.schema_sql)
        self.assertIn("idx_holdings_scheme_id", self.schema_sql)

    def test_stock_concalls_compatibility_view(self):
        """Verify stock_concalls compatibility view is defined for mobile client backwards compatibility."""
        self.assertIn("CREATE OR REPLACE VIEW stock_concalls AS", self.schema_sql)

    def test_stock_predictions_aligned_columns(self):
        """Verify stock_predictions supports stance, targets, and signal scores."""
        for col in ["stance", "target_bear", "target_base", "target_bull", "signal_scores", "key_drivers"]:
            self.assertIn(col, self.schema_sql, f"Column {col} must be present in stock_predictions DDL")

    def test_concall_analyses_aligned_columns(self):
        """Verify concall_analyses supports score, summary, and driver arrays."""
        for col in ["score", "summary", "positive_drivers", "key_risks", "guidance_numbers"]:
            self.assertIn(col, self.schema_sql, f"Column {col} must be present in concall_analyses DDL")


if __name__ == "__main__":
    unittest.main()

