import unittest
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.analysis import SentimentResult
from stock_analyzer import StockAnalyzer

class TestMilestoneTracker(unittest.TestCase):
    def setUp(self):
        self.analyzer = StockAnalyzer()

    def test_resolve_quarter_and_date_maps_transcript_months(self):
        """Test Screener transcript dates map to reported Indian financial quarters."""
        self.assertEqual(
            self.analyzer.resolve_quarter_and_date("May 2026"),
            ("Q4 FY26", "May 2026"),
        )
        self.assertEqual(
            self.analyzer.resolve_quarter_and_date("28 May 2026"),
            ("Q4 FY26", "May 2026"),
        )
        self.assertEqual(
            self.analyzer.resolve_quarter_and_date("Feb 2026"),
            ("Q3 FY26", "Feb 2026"),
        )
        self.assertEqual(
            self.analyzer.resolve_quarter_and_date("Q1 FY26"),
            ("Q1 FY26", ""),
        )

    def test_rule_based_milestone_grouping(self):
        """Test rule-based milestone grouping maps keywords to tracks correctly."""
        raw_items = [
            {"quarter": "Jun 2023", "text": "Plan to reduce debt by 50 Cr", "type": "Future Target"},
            {"quarter": "Sep 2023", "text": "Reduced debt by 20 Cr", "type": "Milestone Achieved"},
            {"quarter": "Jun 2023", "text": "Open 10 new stores", "type": "Future Target"},
            {"quarter": "Sep 2023", "text": "Margins under pressure due to raw material costs", "type": "Concern"},
        ]

        tracks = self.analyzer._rule_based_milestone_grouping(raw_items)
        self.assertGreater(len(tracks), 0)

        # Check for Debt Management track
        debt_track = next((t for t in tracks if "Debt" in t.name), None)
        self.assertIsNotNone(debt_track)
        self.assertEqual(len(debt_track.quarterly_updates), 2)
        
        # Check updates are sorted chronological (oldest first: Jun 2023, then Sep 2023)
        # Note: raw_items was ordered Jun 2023 first, then Sep 2023.
        # But _rule_based_milestone_grouping reverses the items from the extracted list because raw concalls are latest first.
        # Let's verify that chronological tracking logic works.
        self.assertEqual(debt_track.quarterly_updates[0]["quarter"], "Jun 2023")
        self.assertEqual(debt_track.quarterly_updates[1]["quarter"], "Sep 2023")

    def test_rule_based_milestone_grouping_combines_same_quarter_items(self):
        """Test multiple items in the same quarter are combined instead of skipped."""
        raw_items = [
            {
                "quarter": "Q4 FY26",
                "display_quarter": "Q4 FY26 (May 2026)",
                "text": "Reduced debt by 20 Cr",
                "type": "Milestone Achieved",
            },
            {
                "quarter": "Q4 FY26",
                "display_quarter": "Q4 FY26 (May 2026)",
                "text": "Plan to reduce debt by another 30 Cr",
                "type": "Future Target",
            },
        ]

        tracks = self.analyzer._rule_based_milestone_grouping(raw_items)
        debt_track = next((t for t in tracks if "Debt" in t.name), None)

        self.assertIsNotNone(debt_track)
        self.assertEqual(len(debt_track.quarterly_updates), 1)
        self.assertEqual(debt_track.quarterly_updates[0]["quarter"], "Q4 FY26 (May 2026)")
        self.assertIn("Reduced debt by 20 Cr", debt_track.quarterly_updates[0]["note"])
        self.assertIn("another 30 Cr", debt_track.quarterly_updates[0]["note"])

    def test_gemini_milestone_grouping_uses_configured_model(self):
        """Test Gemini milestone grouping parses JSON and saves returned tracks."""
        saved = []

        class FakeResponse:
            text = """
            [
              {
                "name": "Debt Reduction",
                "status": "In Progress",
                "start_quarter": "Jun 2023",
                "current_quarter": "Sep 2023",
                "description": "Management is reducing borrowings over time.",
                "quarterly_updates": [
                  {
                    "quarter": "Jun 2023",
                    "status": "Future Target",
                    "note": "Plan to reduce debt by 50 Cr"
                  },
                  {
                    "quarter": "Sep 2023",
                    "status": "In Progress",
                    "note": "Reduced debt by 20 Cr"
                  }
                ]
              }
            ]
            """

        class FakeModels:
            def generate_content(self, model, contents):
                self.model = model
                self.contents = contents
                return FakeResponse()

        class FakeClient:
            def __init__(self):
                self.models = FakeModels()

        class FakeSentimentAnalyzer:
            def __init__(self):
                self.client = FakeClient()
                self.rate_limited = False

            def _rate_limit(self):
                self.rate_limited = True

        class FakeDb:
            def get_milestones(self, symbol):
                return []

            def save_milestone(self, symbol, milestone):
                saved.append((symbol, milestone))

        self.analyzer.analyzer_type = "gemini"
        self.analyzer.sentiment_analyzer = FakeSentimentAnalyzer()
        self.analyzer.db = FakeDb()

        analyses = [
            SentimentResult(
                quarter="Jun 2023",
                future_targets=["Plan to reduce debt by 50 Cr"],
            ),
            SentimentResult(
                quarter="Sep 2023",
                milestones_achieved=["Reduced debt by 20 Cr"],
            ),
        ]

        tracks = self.analyzer.track_milestone_evolution(
            "TEST.NS", analyses, force_refresh=True
        )

        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].name, "Debt Reduction")
        self.assertEqual(saved[0][0], "TEST.NS")
        self.assertTrue(self.analyzer.sentiment_analyzer.rate_limited)

if __name__ == "__main__":
    unittest.main()
