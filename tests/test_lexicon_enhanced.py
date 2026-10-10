"""
Tests for LexiconAnalyzer enhanced — regex financial number extraction.
"""
import pytest

from analyzers.lexicon_analyzer import LexiconAnalyzer


@pytest.fixture
def analyzer():
    return LexiconAnalyzer()


class TestFinancialNumberExtraction:
    def test_revenue_rs_cr(self, analyzer):
        """Extracts 'revenue of Rs X Cr' pattern."""
        result = analyzer._extract_financial_numbers(
            "Our revenue of Rs 2,400 Cr was driven by strong demand."
        )
        assert result.get("revenue_absolute") == 2400.0
        assert result["analyzer_type"] == "lexicon_enhanced"

    def test_revenue_inr(self, analyzer):
        """Extracts 'sales at INR X Cr' pattern."""
        result = analyzer._extract_financial_numbers(
            "Total sales at INR 1200 Cr for the quarter."
        )
        assert result.get("revenue_absolute") == 1200.0

    def test_pat_extraction(self, analyzer):
        """Extracts PAT / net profit."""
        result = analyzer._extract_financial_numbers(
            "PAT of Rs 300 Cr was up 22% YoY."
        )
        assert result.get("pat_absolute") == 300.0

    def test_net_profit_extraction(self, analyzer):
        """Extracts net profit pattern."""
        result = analyzer._extract_financial_numbers(
            "Net profit stood at Rs 450 crore this quarter."
        )
        assert result.get("pat_absolute") == 450.0

    def test_revenue_growth_pct(self, analyzer):
        """Extracts revenue growth percentage."""
        result = analyzer._extract_financial_numbers(
            "Revenue grew 18.5% driven by volume expansion."
        )
        assert result.get("revenue_growth_pct") == 18.5

    def test_ebitda_margin_pct(self, analyzer):
        """Extracts EBITDA margin percentage."""
        result = analyzer._extract_financial_numbers(
            "Our EBITDA margin of 22.3% was the highest in 5 quarters."
        )
        assert result.get("ebitda_margin_pct") == 22.3

    def test_opm_margin(self, analyzer):
        """Extracts OPM pattern."""
        result = analyzer._extract_financial_numbers(
            "OPM at 19.5% compared to 18.2% last year."
        )
        assert result.get("ebitda_margin_pct") == 19.5

    def test_net_debt(self, analyzer):
        """Extracts net debt."""
        result = analyzer._extract_financial_numbers(
            "Net debt of Rs 1,500 Cr reduced from Rs 1,800 Cr last quarter."
        )
        assert result.get("net_debt_cr") == 1500.0

    def test_order_book(self, analyzer):
        """Extracts order book."""
        result = analyzer._extract_financial_numbers(
            "Order book of Rs 8,500 Cr provides strong revenue visibility."
        )
        assert result.get("order_book_cr") == 8500.0

    def test_no_numbers_returns_lexicon_type(self, analyzer):
        """Returns 'lexicon' analyzer_type when no numbers found."""
        result = analyzer._extract_financial_numbers(
            "The management discussed various strategic initiatives."
        )
        assert result["analyzer_type"] == "lexicon"
        assert "revenue_absolute" not in result

    def test_multiple_numbers(self, analyzer):
        """Extracts multiple financial metrics from same text."""
        text = (
            "Revenue of Rs 2,400 Cr grew 18% YoY. "
            "EBITDA margin of 22% was strong. "
            "PAT of Rs 300 Cr. "
            "Net debt of Rs 1,500 Cr. "
            "Order book of Rs 8,500 Cr."
        )
        result = analyzer._extract_financial_numbers(text)
        assert result.get("revenue_absolute") == 2400.0
        assert result.get("ebitda_margin_pct") == 22.0
        assert result.get("pat_absolute") == 300.0
        assert result.get("net_debt_cr") == 1500.0
        assert result.get("order_book_cr") == 8500.0
        assert result["analyzer_type"] == "lexicon_enhanced"


class TestLexiconAnalyzeConcall:
    def test_concall_with_financial_numbers(self, analyzer):
        """Full analyze_concall extracts regex numbers and keyword sentiment."""
        text = """
        Good morning. Our revenue of Rs 2,400 Cr for the quarter.
        Revenue grew 18% driven by volume expansion.
        EBITDA margin of 22% was the highest in 5 quarters.
        We achieved a major milestone with the new plant commissioning.
        Growth was strong across all segments with expansion plans underway.
        """
        result = analyzer.analyze_concall(text, "Q1 FY25")
        assert result.quarter == "Q1 FY25"
        assert result.revenue_absolute == 2400.0
        assert result.ebitda_margin_pct == 22.0
        assert result.revenue_growth_pct == 18.0
        assert result.analyzer_type == "lexicon_enhanced"

    def test_concall_without_numbers(self, analyzer):
        """Concall without financial number patterns stays as 'lexicon'."""
        text = """
        The company discussed its strategic initiatives.
        Management remains optimistic about the future.
        Growth prospects are positive across segments.
        """
        result = analyzer.analyze_concall(text, "Q1 FY25")
        assert result.analyzer_type == "lexicon"

    def test_segment_operational_metrics(self, analyzer):
        """Analyze concall formats segment data into key_operational_metrics."""
        text = """
        Retail segment revenue of Rs 500 Cr was up 15%.
        Automotive division revenue of Rs 800 Cr was strong.
        """
        result = analyzer.analyze_concall(text, "Q1 FY25")
        assert "Segment: Retail Revenue" in result.key_operational_metrics
        assert "Segment: Automotive Revenue" in result.key_operational_metrics
