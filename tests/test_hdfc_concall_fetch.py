"""
Tests for HDFC Bank concall fetching, Indian FY quarter resolution, and cache auto-sync.
"""
import pytest
from stock_analyzer import StockAnalyzer
from models.analysis import SentimentResult


@pytest.fixture
def analyzer():
    return StockAnalyzer()


class TestQuarterResolution:
    def test_indian_fy_quarter_mapping(self, analyzer):
        """Test Indian Financial Year quarter mapping for standard earnings call months."""
        # Jul 2025 call -> Q1 FY26 (Quarter ended Jun 30, 2025)
        q, label = analyzer.resolve_quarter_and_date("Jul 2025")
        assert q == "Q1 FY26"
        assert label == "Jul 2025"

        # Oct 2025 call -> Q2 FY26 (Quarter ended Sep 30, 2025)
        q, label = analyzer.resolve_quarter_and_date("Oct 2025")
        assert q == "Q2 FY26"
        assert label == "Oct 2025"

        # Jan 2026 call -> Q3 FY26 (Quarter ended Dec 31, 2025)
        q, label = analyzer.resolve_quarter_and_date("Jan 2026")
        assert q == "Q3 FY26"
        assert label == "Jan 2026"

        # Apr 2026 call -> Q4 FY26 (Quarter ended Mar 31, 2026)
        q, label = analyzer.resolve_quarter_and_date("Apr 2026")
        assert q == "Q4 FY26"
        assert label == "Apr 2026"

    def test_intra_quarter_disambiguation(self, analyzer):
        """Test disambiguation for off-cycle/intra-quarter transcript dates."""
        # Mar 2026 call -> Q4 FY26 (Mar) (does not collide with Jan 2026 Q3 FY26)
        q, label = analyzer.resolve_quarter_and_date("Mar 2026")
        assert q == "Q4 FY26 (Mar)"
        assert label == "Mar 2026"

        # Jun 2025 call -> Q1 FY26 (Jun)
        q, label = analyzer.resolve_quarter_and_date("Jun 2025")
        assert q == "Q1 FY26 (Jun)"
        assert label == "Jun 2025"

        # Sep 2025 call -> Q2 FY26 (Sep)
        q, label = analyzer.resolve_quarter_and_date("Sep 2025")
        assert q == "Q2 FY26 (Sep)"
        assert label == "Sep 2025"

    def test_explicit_q_fy_label_preserved(self, analyzer):
        """Explicit Q1 FY26 labels are preserved without alteration."""
        q, label = analyzer.resolve_quarter_and_date("Q1 FY26")
        assert q == "Q1 FY26"


class TestIncrementalAutoSync:
    def test_auto_sync_fetches_latest_when_cached_exists(self, analyzer):
        """Verify analyze_concalls does not early-return old cached quarters when Screener has newer ones."""
        # Call analyze_concalls with force_refresh=False for HDFCBANK
        results = analyzer.analyze_concalls("HDFCBANK", max_transcripts=10, force_refresh=False)
        assert len(results) >= 5
        quarters = [r.quarter for r in results]
        # Q1 FY26 (Jul 2025) MUST be present in the results!
        assert "Q1 FY26" in quarters
