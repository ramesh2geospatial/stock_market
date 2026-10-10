import unittest
import sys
import os
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.analysis import SentimentResult
from models.intelligence import CrossQuarterIntelligence, PromiseTracker
from analyzers.intelligence_engine import IntelligenceEngine
from storage.sqlite_store import SQLiteStore
from stock_analyzer import StockAnalyzer

class TestIntelligenceEngine(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_temp_intel.db"
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass
        self.db = SQLiteStore(self.db_path)
        self.analyzer = StockAnalyzer()
        self.analyzer.db = self.db

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_intelligence_models(self):
        """Test instantiation and attributes of CrossQuarterIntelligence and PromiseTracker."""
        tracker = PromiseTracker(
            promise="Expand store count to 50",
            committed_quarter="Q1 FY24",
            target_quarter="Q4 FY24",
            current_status="Delivered",
            delivery_quarter="Q4 FY24",
            evidence="Reached 52 stores",
            credibility_impact=0.8,
        )
        self.assertEqual(tracker.promise, "Expand store count to 50")
        self.assertEqual(tracker.current_status, "Delivered")
        self.assertEqual(tracker.credibility_impact, 0.8)

        intel = CrossQuarterIntelligence(
            symbol="TEST.NS",
            quarters_analyzed=2,
            analysis_period="Q1 FY24 to Q2 FY24",
            management_credibility_score=85.0,
            overall_narrative="Strong execution and debt reduction.",
            promise_tracker=[tracker],
            red_flags=["Inflation pressure"],
            green_flags=["Margin expansion"],
        )
        self.assertEqual(intel.symbol, "TEST.NS")
        self.assertEqual(len(intel.promise_tracker), 1)
        self.assertEqual(intel.promise_tracker[0].promise, "Expand store count to 50")

    def test_sqlite_store_intelligence_caching(self):
        """Test caching and retrieving cross-quarter intelligence from SQLiteStore."""
        intel_dict = {
            "symbol": "TEST.NS",
            "quarters_analyzed": 2,
            "analysis_period": "Q1 FY24 to Q2 FY24",
            "management_credibility_score": 85.0,
            "overall_narrative": "Story arc text.",
            "promise_tracker": [
                {
                    "promise": "Reduce debt",
                    "committed_quarter": "Q1 FY24",
                    "target_quarter": "Q2 FY24",
                    "current_status": "Delivered",
                    "delivery_quarter": "Q2 FY24",
                    "evidence": "Debt free",
                    "credibility_impact": 0.5,
                }
            ],
            "analyst_concern_evolution": [],
            "segment_trends": [],
            "risk_trajectory": [],
            "key_inflection_points": [],
            "red_flags": ["Risk A"],
            "green_flags": ["Positive B"],
            "financial_progression": [],
        }

        # Cache
        self.db.save_intelligence("TEST.NS", intel_dict, quarters=2)

        # Retrieve
        cached = self.db.get_intelligence("TEST.NS")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["symbol"], "TEST.NS")
        self.assertEqual(cached["_cached_quarters"], 2)
        self.assertEqual(cached["management_credibility_score"], 85.0)

        # Clear
        self.db.clear_intelligence("TEST.NS")
        cleared = self.db.get_intelligence("TEST.NS")
        self.assertIsNone(cleared)

    def test_rule_based_synthesis_fallback(self):
        """Test that rule-based fallback works when Gemini client is not provided."""
        engine = IntelligenceEngine(gemini_client=None)
        
        analyses = [
            SentimentResult(
                quarter="Q1 FY24",
                sentiment_score=0.2,
                sentiment_label="Positive",
                management_tone="Confident",
                revenue_absolute=100.0,
                ebitda_margin_pct=15.0,
                pat_absolute=10.0,
                prior_guidance_met=[{"target": "Revenue Rs 100 Cr", "actual": "Rs 100 Cr"}],
            ),
            SentimentResult(
                quarter="Q2 FY24",
                sentiment_score=0.4,
                sentiment_label="Positive",
                management_tone="Optimistic",
                revenue_absolute=120.0,
                ebitda_margin_pct=16.0,
                pat_absolute=12.0,
                prior_guidance_missed=[{"target": "Debt free", "actual": "Rs 10 Cr debt"}],
            ),
        ]

        result = engine.synthesize(analyses, symbol="TEST.NS")
        self.assertEqual(result.symbol, "TEST.NS")
        self.assertEqual(result.quarters_analyzed, 2)
        self.assertEqual(result.management_credibility_score, 50.0)  # 1 met, 1 missed = 50%
        self.assertTrue(len(result.promise_tracker) >= 2)
        self.assertEqual(result.promise_tracker[0].current_status, "Delivered")
        self.assertEqual(result.promise_tracker[1].current_status, "Missed")

    def test_gemini_synthesis_with_fake_client(self):
        """Test Gemini-based synthesis using a fake/mock Gemini client."""
        class FakeResponse:
            text = """
            {
              "management_credibility_score": 90.0,
              "credibility_trend": "Improving",
              "overall_narrative": "Connected story arc of the company.",
              "promise_tracker": [
                {
                  "promise": "Launch product X",
                  "committed_quarter": "Q1 FY24",
                  "target_quarter": "Q2 FY24",
                  "current_status": "Delivered",
                  "delivery_quarter": "Q2 FY24",
                  "evidence": "Product launched in Q2",
                  "credibility_impact": 0.8
                }
              ],
              "analyst_concern_evolution": [],
              "segment_trends": [],
              "risk_trajectory": [],
              "key_inflection_points": [],
              "red_flags": [],
              "green_flags": ["Strong product sales"],
              "financial_progression": []
            }
            """

        class FakeModels:
            def generate_content(self, model, contents):
                self.model = model
                self.contents = contents
                return FakeResponse()

        class FakeClient:
            def __init__(self):
                self.models = FakeModels()

        fake_client = FakeClient()
        engine = IntelligenceEngine(gemini_client=fake_client)

        analyses = [
            SentimentResult(quarter="Q1 FY24", sentiment_score=0.1),
            SentimentResult(quarter="Q2 FY24", sentiment_score=0.3),
        ]

        result = engine.synthesize(analyses, symbol="TEST.NS")
        self.assertEqual(result.symbol, "TEST.NS")
        self.assertEqual(result.management_credibility_score, 90.0)
        self.assertEqual(result.credibility_trend, "Improving")
        self.assertEqual(result.overall_narrative, "Connected story arc of the company.")
        self.assertEqual(len(result.promise_tracker), 1)
        self.assertEqual(result.promise_tracker[0].promise, "Launch product X")

if __name__ == "__main__":
    unittest.main()
