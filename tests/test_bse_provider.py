"""
Unit tests for BSEProvider (providers/bse_provider.py).
"""
import pytest
from unittest.mock import MagicMock, patch
from providers.bse_provider import BSEProvider, NSE_TO_BSE_MAPPING
from models.stock import UnifiedDocument


def test_bse_scrip_code_mapping():
    provider = BSEProvider()

    # Test direct mapped tickers
    assert provider.get_bse_scrip_code("HDFCBANK") == "500180"
    assert provider.get_bse_scrip_code("RELIANCE") == "500325"
    assert provider.get_bse_scrip_code("INFY") == "500209"

    # Test case insensitivity and suffix handling
    assert provider.get_bse_scrip_code("hdfcbank.ns") == "500180"
    assert provider.get_bse_scrip_code("RELIANCE.BO") == "500325"

    # Test 6-digit numeric scrip code passthrough
    assert provider.get_bse_scrip_code("500180") == "500180"
    assert provider.get_bse_scrip_code("532540") == "532540"

    # Test unknown ticker
    assert provider.get_bse_scrip_code("UNKNOWN_TICKER_XYZ") is None
    assert provider.get_bse_scrip_code("") is None


def test_classify_announcement():
    provider = BSEProvider()

    assert provider.classify_announcement("Transcript of Concall held on July 20, 2025") == "transcript"
    assert provider.classify_announcement("Audio recording of Earnings Call") == "transcript"

    assert provider.classify_announcement("Investor Presentation for Q1 FY26") == "presentation"
    assert provider.classify_announcement("Analyst Presentation Factsheet") == "presentation"

    assert provider.classify_announcement("Financial Results for the quarter ended June 30, 2025") == "financial_results"
    assert provider.classify_announcement("Outcome of Board Meeting - Unaudited Financial Results") == "financial_results"

    assert provider.classify_announcement("Annual Report 2024-25") == "annual_report"
    assert provider.classify_announcement("Credit Rating Update by CRISIL") == "credit_rating"

    assert provider.classify_announcement("Closure of Trading Window") == "other"


def test_resolve_quarter_from_filing_date():
    provider = BSEProvider()

    # Filing in Jul 2025 -> Q1 FY26
    assert provider.resolve_quarter_from_filing_date("2025-07-20T10:00:00") == "Q1 FY26"

    # Filing in Oct 2025 -> Q2 FY26
    assert provider.resolve_quarter_from_filing_date("2025-10-15T15:30:00") == "Q2 FY26"

    # Filing in Jan 2026 -> Q3 FY26
    assert provider.resolve_quarter_from_filing_date("2026-01-25T11:00:00") == "Q3 FY26"

    # Filing in Apr 2026 -> Q4 FY26
    assert provider.resolve_quarter_from_filing_date("2026-04-18T18:00:00") == "Q4 FY26"

    # Empty date -> ""
    assert provider.resolve_quarter_from_filing_date("") == ""


@patch("requests.get")
def test_fetch_announcements_mocked(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "SCRIP_CD": "500180",
            "HEADLINE": "Transcript of Earnings Call Q1 FY26",
            "ATTACHMENTNAME": "a8f9d123.pdf",
            "NEWS_DT": "2025-07-20T10:00:00",
        }
    ]
    mock_get.return_value = mock_resp

    provider = BSEProvider()
    announcements = provider.fetch_announcements("500180")

    assert len(announcements) == 1
    assert announcements[0]["HEADLINE"] == "Transcript of Earnings Call Q1 FY26"
    assert announcements[0]["ATTACHMENTNAME"] == "a8f9d123.pdf"


@patch("providers.bse_provider.BSEProvider.fetch_announcements")
def test_fetch_documents_mocked(mock_fetch_announcements):
    mock_fetch_announcements.return_value = [
        {
            "SCRIP_CD": "500180",
            "HEADLINE": "Transcript of Earnings Call Q1 FY26",
            "NEWSSUB": "Concall Transcript",
            "ATTACHMENTNAME": "transcript_q1fy26.pdf",
            "NEWS_DT": "2025-07-20T10:00:00",
        },
        {
            "SCRIP_CD": "500180",
            "HEADLINE": "Investor Presentation Q1 FY26",
            "NEWSSUB": "Presentation",
            "ATTACHMENTNAME": "presentation_q1fy26.pdf",
            "NEWS_DT": "2025-07-20T10:30:00",
        },
        {
            "SCRIP_CD": "500180",
            "HEADLINE": "General Disclosure Notice",
            "ATTACHMENTNAME": "notice.pdf",
            "NEWS_DT": "2025-07-20T11:00:00",
        },
    ]

    provider = BSEProvider()
    docs = provider.fetch_documents("HDFCBANK")

    assert len(docs) == 2  # General Disclosure ("other") is skipped
    categories = [d.category for d in docs]
    assert "transcript" in categories
    assert "presentation" in categories

    t_doc = next(d for d in docs if d.category == "transcript")
    assert t_doc.symbol == "HDFCBANK"
    assert t_doc.quarter == "Q1 FY26"
    assert t_doc.source_used == "BSE"
    assert t_doc.bse_scrip_code == "500180"
    assert t_doc.url == "https://www.bseindia.com/xml-data/corpfiling/AttachLive/transcript_q1fy26.pdf"


@patch("providers.bse_provider.BSEProvider.fetch_announcements")
def test_bse_api_error_response_robustness(mock_fetch_announcements):
    provider = BSEProvider()

    # Case A: String error payload returned from BSE API
    mock_fetch_announcements.return_value = "Error: Rate limit exceeded"
    docs_a = provider.fetch_documents("HDFCBANK")
    assert docs_a == []

    # Case B: List containing string error messages mixed with non-dict objects
    mock_fetch_announcements.return_value = [
        "Internal Server Error",
        12345,
        {
            "SCRIP_CD": "500180",
            "HEADLINE": "Transcript of Earnings Call Q3 FY26",
            "NEWSSUB": "Concall Transcript",
            "ATTACHMENTNAME": "transcript_q3fy26.pdf",
            "NEWS_DT": "2026-01-20T10:00:00",
        },
    ]
    docs_b = provider.fetch_documents("HDFCBANK")
    assert len(docs_b) == 1
    assert docs_b[0].category == "transcript"


def test_resolve_quarter_march_filing_date_maps_to_q4():
    from providers.multi_source_doc_fetcher import normalize_quarter_label

    provider = BSEProvider()

    # March filing date (e.g. 2026-03-15) must map to Q4 FY26 in BSEProvider
    bse_q = provider.resolve_quarter_from_filing_date("2026-03-15T10:00:00")
    assert bse_q == "Q4 FY26"

    # Verify alignment with normalize_quarter_label
    norm_q = normalize_quarter_label("", filing_date="2026-03-15")
    assert bse_q == norm_q == "Q4 FY26"

