"""
Unit tests for Dynamic N-Quarter Analysis Engine:
- QuarterlyCashflowEngine
- MultiQuarterDivergenceAnalyzer
- Freshness verification in StockAnalyzer
"""
import datetime
import unittest
from unittest.mock import patch
from models.stock import QuarterlyResult
from analyzers.quarterly_cashflow_engine import QuarterlyCashflowEngine
from analyzers.multi_quarter_divergence import MultiQuarterDivergenceAnalyzer
from stock_analyzer import StockAnalyzer


class MockDate(datetime.date):
    _target_date = datetime.date.today()

    @classmethod
    def today(cls):
        return cls._target_date


class TestQuarterlyEngine(unittest.TestCase):

    def setUp(self):
        self.sample_quarters = [
            QuarterlyResult(quarter="Q1 FY25", revenue=1000.0, operating_profit=150.0, opm_percent=15.0, net_profit=100.0, eps=5.0),
            QuarterlyResult(quarter="Q2 FY25", revenue=1050.0, operating_profit=168.0, opm_percent=16.0, net_profit=112.0, eps=5.6),
            QuarterlyResult(quarter="Q3 FY25", revenue=1100.0, operating_profit=187.0, opm_percent=17.0, net_profit=125.0, eps=6.25),
            QuarterlyResult(quarter="Q4 FY25", revenue=1150.0, operating_profit=195.5, opm_percent=17.0, net_profit=130.0, eps=6.5),
            QuarterlyResult(quarter="Q1 FY26", revenue=1250.0, operating_profit=225.0, opm_percent=18.0, net_profit=150.0, eps=7.5),
        ]

    def test_quarterly_cashflow_engine_5_quarters(self):
        """Verify dynamic 5-quarter cash flow analysis."""
        engine = QuarterlyCashflowEngine()
        res = engine.analyze_quarterly_cashflow(self.sample_quarters, num_quarters=5)

        self.assertEqual(res["num_quarters_analyzed"], 5)
        self.assertGreater(res["overall_cfo_pat"], 0)
        self.assertGreater(res["velocity_score"], 0)
        self.assertEqual(len(res["quarters"]), 5)
        self.assertIn("latest_quarter_summary", res)

    def test_latest_quarter_summary_and_badges(self):
        """Verify latest quarter summary dictionary and cashflow/PAT badges."""
        engine = QuarterlyCashflowEngine()
        res = engine.analyze_quarterly_cashflow(self.sample_quarters, num_quarters=5)
        l_summary = res.get("latest_quarter_summary", {})

        self.assertEqual(l_summary.get("quarter"), "Q1 FY26")
        self.assertIn("fcf_badge", l_summary)
        self.assertIn("cfo_pat_badge", l_summary)
        self.assertEqual(l_summary["fcf_badge"], "🟢 Strong FCF")

        # Test loss-making quarter for Negative PAT Drain badge
        loss_quarter = [
            QuarterlyResult(quarter="Q2 FY26", revenue=500.0, operating_profit=-10.0, opm_percent=-2.0, net_profit=-20.0, eps=-1.0)
        ]
        res_loss = engine.analyze_quarterly_cashflow(loss_quarter, num_quarters=1)
        l_loss_summary = res_loss.get("latest_quarter_summary", {})
        self.assertEqual(l_loss_summary.get("cfo_pat_badge"), "🔴 Negative PAT Drain")
        self.assertEqual(l_loss_summary.get("fcf_badge"), "🔴 Cash Drain")

    def test_multi_quarter_divergence_analyzer(self):
        """Verify QoQ and YoY metric divergence matrix calculation."""
        analyzer = MultiQuarterDivergenceAnalyzer()
        res = analyzer.compute_divergence(self.sample_quarters, num_quarters=5)

        self.assertEqual(res["num_quarters"], 5)
        self.assertIn("Accelerating Growth", res["trajectory_badge"])
        self.assertGreater(res["avg_rev_growth_pct"], 0)
        self.assertEqual(len(res["matrix"]), 5)

    def test_sector_capex_buffer(self):
        """Verify sector capex ratios and non-negative EBITDA capex protection."""
        engine = QuarterlyCashflowEngine()

        # Test IT (0.05)
        res_it = engine.analyze_quarterly_cashflow(self.sample_quarters, num_quarters=5, sector="IT")
        q1_it = res_it["quarters"][0]
        ebitda_q1 = 150.0
        cfo_q1 = q1_it["est_cfo"]
        self.assertEqual(q1_it["fcf"], round(cfo_q1 - (ebitda_q1 * 0.05), 2))

        # Test FMCG (0.08)
        res_fmcg = engine.analyze_quarterly_cashflow(self.sample_quarters, num_quarters=5, sector="FMCG")
        q1_fmcg = res_fmcg["quarters"][0]
        self.assertEqual(q1_fmcg["fcf"], round(cfo_q1 - (ebitda_q1 * 0.08), 2))

        # Test Auto (0.20)
        res_auto = engine.analyze_quarterly_cashflow(self.sample_quarters, num_quarters=5, sector="Auto")
        q1_auto = res_auto["quarters"][0]
        self.assertEqual(q1_auto["fcf"], round(cfo_q1 - (ebitda_q1 * 0.20), 2))

        # Test Metals / Infra (0.30)
        res_metals = engine.analyze_quarterly_cashflow(self.sample_quarters, num_quarters=5, sector="Metals")
        q1_metals = res_metals["quarters"][0]
        self.assertEqual(q1_metals["fcf"], round(cfo_q1 - (ebitda_q1 * 0.30), 2))

        # Test Default (0.15)
        res_def = engine.analyze_quarterly_cashflow(self.sample_quarters, num_quarters=5, sector="Other")
        q1_def = res_def["quarters"][0]
        self.assertEqual(q1_def["fcf"], round(cfo_q1 - (ebitda_q1 * 0.15), 2))

        # Test Negative EBITDA protection
        neg_quarters = [
            QuarterlyResult(quarter="Q1 FY25", revenue=100.0, operating_profit=-50.0, opm_percent=-50.0, net_profit=-60.0, eps=-3.0)
        ]
        res_neg = engine.analyze_quarterly_cashflow(neg_quarters, num_quarters=1, sector="IT")
        q_neg = res_neg["quarters"][0]
        self.assertEqual(q_neg["fcf"], q_neg["est_cfo"])

    def test_turnaround_badge(self):
        """Verify loss-to-profit turnaround detection and trajectory badge addition."""
        turnaround_quarters = [
            QuarterlyResult(quarter="Q3 FY25", revenue=1000.0, operating_profit=50.0, opm_percent=5.0, net_profit=-20.0, eps=-1.0),
            QuarterlyResult(quarter="Q4 FY25", revenue=1200.0, operating_profit=150.0, opm_percent=12.5, net_profit=80.0, eps=4.0),
        ]
        analyzer = MultiQuarterDivergenceAnalyzer()
        res = analyzer.compute_divergence(turnaround_quarters, num_quarters=2)

        self.assertTrue(res["turnaround_flag"])
        self.assertIn("🔄 Loss-to-Profit Turnaround", res["trajectory_badge"])

    def test_percentage_clamping(self):
        """Verify clamping of cfo_pat_ratio [0.0, 5.0] and QoQ growth [%-500.0, 500.0]."""
        # Test cfo_pat_ratio clamping
        engine = QuarterlyCashflowEngine()
        extreme_quarters = [
            QuarterlyResult(quarter="Q1 FY25", revenue=10000.0, operating_profit=2000.0, opm_percent=20.0, net_profit=1.0, eps=0.05)
        ]
        res_cfo = engine.analyze_quarterly_cashflow(extreme_quarters, num_quarters=1)
        self.assertEqual(res_cfo["quarters"][0]["cfo_pat_ratio"], 5.0)

        # Test QoQ growth clamping
        div_quarters = [
            QuarterlyResult(quarter="Q1 FY25", revenue=1.0, operating_profit=0.1, opm_percent=10.0, net_profit=0.01, eps=0.001),
            QuarterlyResult(quarter="Q2 FY25", revenue=1000.0, operating_profit=100.0, opm_percent=10.0, net_profit=100.0, eps=10.0),
        ]
        analyzer = MultiQuarterDivergenceAnalyzer()
        res_div = analyzer.compute_divergence(div_quarters, num_quarters=2)
        q2_metrics = res_div["matrix"][1]
        self.assertEqual(q2_metrics["qoq_revenue_growth_pct"], 500.0)
        self.assertEqual(q2_metrics["qoq_pat_growth_pct"], 500.0)

    def test_recency_math(self):
        """Verify date parsing and freshness badge categorization in StockAnalyzer."""
        analyzer = StockAnalyzer()

        with patch.object(analyzer, 'fetch_quarterly_results') as mock_fetch, \
             patch.object(analyzer, 'fetch_documents') as mock_docs:
            mock_docs.return_value = {"transcripts": []}

            recent_q = [QuarterlyResult(quarter="Q1 FY27", revenue=100.0)]
            mock_fetch.return_value = recent_q

            # Scenario 1: Fresh Data (<= 100 days)
            with patch('stock_analyzer.datetime.date', MockDate):
                MockDate._target_date = datetime.date(2026, 7, 15)  # Q1 FY27 is 2026-06-01, ~44 days elapsed
                res_fresh = analyzer.verify_latest_quarter_freshness("TEST")
                self.assertTrue(res_fresh["is_fresh"])
                self.assertIn("🟢 Fresh Data", res_fresh["badge"])

            # Scenario 2: Recent Data (<= 150 days)
            with patch('stock_analyzer.datetime.date', MockDate):
                MockDate._target_date = datetime.date(2026, 10, 1)  # Q1 FY27 is 2026-06-01, ~122 days elapsed
                res_recent = analyzer.verify_latest_quarter_freshness("TEST")
                self.assertTrue(res_recent["is_fresh"])
                self.assertIn("🟡 Recent Data", res_recent["badge"])

            # Scenario 3: Stale Data (> 150 days)
            with patch('stock_analyzer.datetime.date', MockDate):
                MockDate._target_date = datetime.date(2027, 1, 15)  # Q1 FY27 is 2026-06-01, ~228 days elapsed
                res_stale = analyzer.verify_latest_quarter_freshness("TEST")
                self.assertFalse(res_stale["is_fresh"])
                self.assertIn("🔴 Stale Data", res_stale["badge"])


if __name__ == "__main__":
    unittest.main()

