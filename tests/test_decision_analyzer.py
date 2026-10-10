import os
import sys
import unittest

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzers.decision_analyzer import DecisionAnalyzer
from models.stock import QuarterlyResult


class TestDecisionAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = DecisionAnalyzer()

    def test_build_valuation_positive_eps(self):
        quarters = [
            QuarterlyResult(quarter="Jun 2024", revenue=100, operating_profit=18, opm_percent=18, eps=2.0),
            QuarterlyResult(quarter="Sep 2024", revenue=110, operating_profit=22, opm_percent=20, eps=2.5),
            QuarterlyResult(quarter="Dec 2024", revenue=120, operating_profit=25, opm_percent=21, eps=3.0),
            QuarterlyResult(quarter="Mar 2025", revenue=140, operating_profit=31, opm_percent=22, eps=3.5),
            QuarterlyResult(quarter="Jun 2025", revenue=160, operating_profit=38, opm_percent=24, eps=4.0),
        ]
        info = {"currentPrice": 120, "trailingPE": 20}

        valuation = self.analyzer.build_valuation(info, quarters)

        self.assertGreater(valuation.eps_ttm, 0)
        self.assertGreater(valuation.base_value, 0)
        self.assertIn(valuation.valuation_state, {"Attractive", "Fair", "Expensive"})

    def test_assess_risks_flags_declines_and_expensive_valuation(self):
        quarters = [
            QuarterlyResult(quarter="Jun 2024", revenue=200, operating_profit=40, opm_percent=20, eps=8, interest=5),
            QuarterlyResult(quarter="Sep 2024", revenue=190, operating_profit=36, opm_percent=19, eps=7, interest=6),
            QuarterlyResult(quarter="Dec 2024", revenue=180, operating_profit=30, opm_percent=17, eps=6, interest=7),
            QuarterlyResult(quarter="Mar 2025", revenue=170, operating_profit=24, opm_percent=14, eps=4, interest=8),
            QuarterlyResult(quarter="Jun 2025", revenue=150, operating_profit=15, opm_percent=10, eps=2, interest=18),
        ]
        info = {"trailingPE": 75, "priceToBook": 14, "beta": 1.8}
        hist = pd.DataFrame({"Close": [100, 150, 90]})

        risks = self.analyzer.assess_risks(info, hist, quarters)
        messages = " ".join(r.message for r in risks)

        self.assertTrue(any(r.severity == "High" for r in risks))
        self.assertIn("multiple", messages)
        self.assertIn("Revenue", messages)

    def test_build_research_snapshot_returns_all_sections(self):
        quarters = [
            QuarterlyResult(quarter="Jun 2024", revenue=100, operating_profit=20, opm_percent=20, eps=2),
            QuarterlyResult(quarter="Sep 2024", revenue=110, operating_profit=24, opm_percent=22, eps=3),
            QuarterlyResult(quarter="Dec 2024", revenue=120, operating_profit=28, opm_percent=23, eps=3),
            QuarterlyResult(quarter="Mar 2025", revenue=130, operating_profit=32, opm_percent=25, eps=4),
            QuarterlyResult(quarter="Jun 2025", revenue=145, operating_profit=38, opm_percent=26, eps=5),
        ]

        snapshot = self.analyzer.build_research_snapshot(
            {"currentPrice": 100, "sector": "Technology", "industry": "IT Services"},
            pd.DataFrame({"Close": [90, 100]}),
            quarters,
        )

        self.assertIn("valuation", snapshot)
        self.assertIn("risks", snapshot)
        self.assertIn("thesis", snapshot)
        self.assertGreaterEqual(snapshot["thesis"].score, 0)
        self.assertLessEqual(snapshot["thesis"].score, 100)


if __name__ == "__main__":
    unittest.main()
