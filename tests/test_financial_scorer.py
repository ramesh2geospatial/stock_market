import unittest
import sys
import os

# Add parent directory to path so tests can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.stock import QuarterlyResult
from analyzers.financial_scorer import FinancialScorer

class TestFinancialScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = FinancialScorer()

    def test_compute_spider_data_empty(self):
        """Test with empty list of results."""
        self.assertEqual(self.scorer.compute_spider_data([]), [])

    def test_compute_spider_data_values(self):
        """Test with realistic quarterly results and assert correct scoring."""
        quarters = [
            QuarterlyResult(quarter="Jun 2023", revenue=100.0, expenses=80.0, operating_profit=20.0, opm_percent=20.0, eps=2.0),
            QuarterlyResult(quarter="Sep 2023", revenue=110.0, expenses=85.0, operating_profit=25.0, opm_percent=22.7, eps=2.5),
            QuarterlyResult(quarter="Dec 2023", revenue=120.0, expenses=90.0, operating_profit=30.0, opm_percent=25.0, eps=3.0),
            QuarterlyResult(quarter="Mar 2024", revenue=130.0, expenses=95.0, operating_profit=35.0, opm_percent=26.9, eps=3.5),
        ]
        
        spider_data = self.scorer.compute_spider_data(quarters)
        self.assertEqual(len(spider_data), 4)
        
        # Check Dec 2023 quarter data
        dec_q = spider_data[2]
        self.assertEqual(dec_q.quarter, "Dec 2023")
        self.assertGreater(dec_q.overall_score, 0)
        
        # Check metrics are all 6 required dimensions
        dimension_names = [m.name for m in dec_q.metrics]
        self.assertIn("Revenue Growth", dimension_names)
        self.assertIn("Profitability", dimension_names)
        self.assertIn("EBITDA Trend", dimension_names)
        self.assertIn("Debt Management", dimension_names)
        self.assertIn("EPS Growth", dimension_names)
        self.assertIn("Operational Efficiency", dimension_names)

        # Dec 2023 trend calculations:
        # Revenue: Jun=100, Sep=110, Dec=120 (direction > 0) -> "up"
        rev_metric = next(m for m in dec_q.metrics if m.name == "Revenue Growth")
        self.assertEqual(rev_metric.trend, "up")

if __name__ == "__main__":
    unittest.main()
