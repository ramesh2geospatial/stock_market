"""
Unit tests for 8 Institutional Concall Analysis Sections.
"""
import unittest
from models.analysis import SentimentResult
from analyzers.lexicon_analyzer import LexiconAnalyzer
from analyzers.gemini_analyzer import GeminiAnalyzer


class TestInstitutionalConcallSections(unittest.TestCase):
    def test_sentiment_result_defaults(self):
        result = SentimentResult()
        self.assertEqual(result.key_takeaways, [])
        self.assertEqual(result.volume_yield_flywheel, [])
        self.assertEqual(result.productivity_efficiency, [])
        self.assertEqual(result.margin_architecture, [])
        self.assertEqual(result.customer_segmentation, [])
        self.assertEqual(result.capital_allocation, [])
        self.assertEqual(result.guidance_commitments, [])
        self.assertEqual(result.key_operational_metrics, {})

    def test_lexicon_analyzer_institutional_sections(self):
        analyzer = LexiconAnalyzer()
        transcript = """
        Good morning everyone. Our volume grew 12% driven by strong demand and blended realization improved.
        Our productivity and capacity utilization reached 88% efficiency with cost per unit dropping.
        EBITDA margin architecture expanded 150 bps to 22% due to operating leverage and raw material gains.
        Retail customer segmentation expanded while enterprise B2B sales saw steady growth in Tier 2 cities.
        Capex capital allocation will remain focused on deleveraging debt reduction and ROIC improvement.
        Our forward guidance target for FY26 is 18% revenue growth and on track.
        Revenue of Rs 2,400 Cr and PAT of Rs 300 Cr.
        """
        result = analyzer.analyze_concall(transcript, "Q1 FY25")
        
        self.assertTrue(len(result.key_takeaways) > 0)
        self.assertTrue(len(result.volume_yield_flywheel) > 0)
        self.assertTrue(len(result.productivity_efficiency) > 0)
        self.assertTrue(len(result.margin_architecture) > 0)
        self.assertTrue(len(result.customer_segmentation) > 0)
        self.assertTrue(len(result.capital_allocation) > 0)
        self.assertTrue(len(result.guidance_commitments) > 0)
        self.assertIn("Revenue (Rs Cr)", result.key_operational_metrics)

    def test_gemini_analyzer_parse_response_sections(self):
        analyzer = GeminiAnalyzer(api_key="")
        mock_json = """{
            "sentiment_score": 0.8,
            "sentiment_label": "Positive",
            "management_tone": "Confident",
            "key_takeaways": ["Revenue grew 18% YoY"],
            "volume_yield_flywheel": ["Volume growth of 12% with 6% realization gain"],
            "productivity_efficiency": ["Capacity utilization increased to 85%"],
            "margin_architecture": ["EBITDA margin expanded 150 bps to 22%"],
            "customer_segmentation": ["Retail segment contributed 60% of revenues"],
            "capital_allocation": ["Rs 500 Cr capex planned for expansion"],
            "guidance_commitments": ["Targeting 20% growth in FY26"],
            "key_operational_metrics": {"capacity_utilization": "85%", "arpu": "Rs 210"}
        }"""
        result = analyzer._parse_response(mock_json, "Q1 FY25")
        self.assertIsNotNone(result)
        self.assertEqual(result.key_takeaways, ["Revenue grew 18% YoY"])
        self.assertEqual(result.volume_yield_flywheel, ["Volume growth of 12% with 6% realization gain"])
        self.assertEqual(result.productivity_efficiency, ["Capacity utilization increased to 85%"])
        self.assertEqual(result.margin_architecture, ["EBITDA margin expanded 150 bps to 22%"])
        self.assertEqual(result.customer_segmentation, ["Retail segment contributed 60% of revenues"])
        self.assertEqual(result.capital_allocation, ["Rs 500 Cr capex planned for expansion"])
        self.assertEqual(result.guidance_commitments, ["Targeting 20% growth in FY26"])
        self.assertEqual(result.key_operational_metrics, {"capacity_utilization": "85%", "arpu": "Rs 210"})


if __name__ == "__main__":
    unittest.main()
