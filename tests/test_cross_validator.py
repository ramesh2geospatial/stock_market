"""
Tests for CrossValidator — Gemini output validation against Screener quarterly data.
"""
import pytest
from datetime import datetime

from analyzers.cross_validator import CrossValidator, _parse_quarter_label_to_date, _parse_quarter_date
from models.analysis import SentimentResult
from models.stock import QuarterlyResult


@pytest.fixture
def validator():
    return CrossValidator()


@pytest.fixture
def sample_quarterly_results():
    return [
        QuarterlyResult(quarter="Jun 2024", revenue=2500.0, operating_profit=500.0,
                        opm_percent=20.0, net_profit=300.0),
        QuarterlyResult(quarter="Mar 2024", revenue=2200.0, operating_profit=440.0,
                        opm_percent=20.0, net_profit=280.0),
        QuarterlyResult(quarter="Dec 2023", revenue=2100.0, operating_profit=399.0,
                        opm_percent=19.0, net_profit=260.0),
    ]


class TestCrossValidator:
    def test_no_correction_when_values_match(self, validator, sample_quarterly_results):
        """No corrections when Gemini values are within 15% of Screener."""
        analysis = SentimentResult(
            quarter="Q1 FY25",  # Jun 2024
            sentiment_score=0.5,
            sentiment_label="Positive",
            revenue_absolute=2500.0,  # Exact match
            pat_absolute=300.0,       # Exact match
            ebitda_margin_pct=20.0,   # Exact match
            analyzer_type="gemini",
        )
        result = validator.validate_and_correct(analysis, sample_quarterly_results)
        assert result.data_confidence == "high"
        assert len(result.corrections) == 0

    def test_correction_when_revenue_diverges_over_15pct(self, validator, sample_quarterly_results):
        """Corrects revenue when divergence > 15%."""
        analysis = SentimentResult(
            quarter="Q1 FY25",  # Jun 2024 -> Screener revenue = 2500
            sentiment_score=0.5,
            sentiment_label="Positive",
            revenue_absolute=2000.0,  # 20% below Screener (2500)
            analyzer_type="gemini",
        )
        result = validator.validate_and_correct(analysis, sample_quarterly_results)
        assert result.data_confidence == "medium"
        assert len(result.corrections) == 1
        assert result.corrections[0]["field"] == "revenue_absolute"
        assert result.revenue_absolute == 2500.0  # Corrected to Screener value
        assert result.corrections[0]["severity"] == "correction"

    def test_hallucination_when_revenue_diverges_over_50pct(self, validator, sample_quarterly_results):
        """Flags hallucination when divergence > 50%."""
        analysis = SentimentResult(
            quarter="Q1 FY25",
            sentiment_score=0.5,
            sentiment_label="Positive",
            revenue_absolute=1000.0,  # 60% below Screener (2500)
            analyzer_type="gemini",
        )
        result = validator.validate_and_correct(analysis, sample_quarterly_results)
        assert result.data_confidence == "low"
        assert any(c["severity"] == "hallucination" for c in result.corrections)

    def test_margin_correction_uses_absolute_difference(self, validator, sample_quarterly_results):
        """Margin correction uses absolute percentage point difference, not relative."""
        analysis = SentimentResult(
            quarter="Q1 FY25",
            sentiment_score=0.5,
            sentiment_label="Positive",
            ebitda_margin_pct=25.0,  # 5pp above Screener (20%), > 3pp threshold
            analyzer_type="gemini",
        )
        result = validator.validate_and_correct(analysis, sample_quarterly_results)
        assert len(result.corrections) == 1
        assert result.corrections[0]["field"] == "ebitda_margin_pct"
        assert result.ebitda_margin_pct == 20.0  # Corrected

    def test_small_margin_difference_not_corrected(self, validator, sample_quarterly_results):
        """Margin within 3pp tolerance should not be corrected."""
        analysis = SentimentResult(
            quarter="Q1 FY25",
            sentiment_score=0.5,
            sentiment_label="Positive",
            ebitda_margin_pct=22.0,  # 2pp above Screener (20%), < 3pp threshold
            analyzer_type="gemini",
        )
        result = validator.validate_and_correct(analysis, sample_quarterly_results)
        assert result.ebitda_margin_pct == 22.0  # Not corrected
        assert len(result.corrections) == 0

    def test_no_quarterly_results_returns_unchanged(self, validator):
        """Returns analysis unchanged when no quarterly results are available."""
        analysis = SentimentResult(
            quarter="Q1 FY25",
            sentiment_score=0.5,
            sentiment_label="Positive",
            revenue_absolute=1000.0,
            analyzer_type="gemini",
        )
        result = validator.validate_and_correct(analysis, [])
        assert result.revenue_absolute == 1000.0
        assert result.data_confidence == "high"

    def test_no_match_returns_unchanged(self, validator):
        """Returns analysis unchanged when quarter doesn't match any Screener data."""
        qr = [QuarterlyResult(quarter="Jun 2020", revenue=1000.0, net_profit=100.0)]
        analysis = SentimentResult(
            quarter="Q1 FY26",  # Way in the future
            sentiment_score=0.5,
            sentiment_label="Positive",
            revenue_absolute=5000.0,
            analyzer_type="gemini",
        )
        result = validator.validate_and_correct(analysis, qr)
        assert result.revenue_absolute == 5000.0  # Not corrected

    def test_original_not_mutated(self, validator, sample_quarterly_results):
        """Cross-validation works on a copy, not the original."""
        analysis = SentimentResult(
            quarter="Q1 FY25",
            sentiment_score=0.5,
            sentiment_label="Positive",
            revenue_absolute=2000.0,  # Will be corrected
            analyzer_type="gemini",
        )
        result = validator.validate_and_correct(analysis, sample_quarterly_results)
        assert analysis.revenue_absolute == 2000.0  # Original unchanged
        assert result.revenue_absolute == 2500.0     # Corrected copy


class TestQuarterParsing:
    def test_q1_fy25_parsing(self):
        dt = _parse_quarter_label_to_date("Q1 FY25")
        assert dt is not None
        assert dt.month == 5  # May 2024 (mid Q1)
        assert dt.year == 2024

    def test_q4_fy25_parsing(self):
        dt = _parse_quarter_label_to_date("Q4 FY25")
        assert dt is not None
        assert dt.month == 2  # Feb 2025
        assert dt.year == 2025

    def test_invalid_quarter_label(self):
        dt = _parse_quarter_label_to_date("Some random text")
        assert dt is None

    def test_parse_quarter_date_mon_year(self):
        dt = _parse_quarter_date("Jun 2024")
        assert dt is not None
        assert dt.month == 6
        assert dt.year == 2024
