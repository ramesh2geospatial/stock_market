"""
Empirical Stress & Edge Case Verification Suite for PDFGroundTruthExtractor.
Challenger 1 - Milestone 3
"""
import io
import os
import pytest
import pypdf
from providers.pdf_extraction_provider import PDFGroundTruthExtractor
from models.ground_truth import GroundTruthFinancials


def create_mock_pdf_with_text(text_content: str) -> bytes:
    """Helper to generate a real PDF in memory containing given text."""
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    # Note: pypdf blank pages don't add text content directly without stream manipulation,
    # so we test extract_metrics_from_text directly or mock text extraction.
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


# =====================================================================
# Vector 1: Negative Numbers / Loss Representation in Parentheses
# =====================================================================
def test_negative_numbers_parentheses():
    """Financial statements represent net losses in parentheses e.g. PAT: (1,200.00)."""
    text = """
    COMPANY XYZ LIMITED
    UNAUDITED FINANCIAL RESULTS (₹ in Crores)
    Total Revenue: 5,000.00
    Operating EBITDA: 800.00
    PAT: (1,200.00)
    """
    extractor = PDFGroundTruthExtractor()
    gt = extractor.extract_metrics_from_text(text, symbol="XYZ", quarter="Q1 FY26")
    
    print(f"\n[Vector 1] Negative Numbers Check:")
    print(f"  Extracted PAT: {gt.pat_cr}")
    
    # Assert PAT should be negative (-1200.00), not positive (+1200.00)
    assert gt.pat_cr == -1200.00, f"FAILED: PAT (1,200.00) extracted as positive {gt.pat_cr} instead of -1200.00"


# =====================================================================
# Vector 2: Unit Scale Detection Priority & Order Ambiguity
# =====================================================================
def test_unit_scale_crores_with_lakhs_mention():
    """
    Document is reported in Crores: 'Financial Results (₹ in Crores)', 
    but mentions Lakhs in a footnote: 'Last year PAT was Rs. 50 Lakhs'.
    Because Lakhs regex is evaluated before Crores regex in detect_unit_scale,
    it might mistakenly choose Lakhs (0.01) instead of Crores (1.0).
    """
    text = """
    ABC LIMITED
    UNAUDITED FINANCIAL RESULTS FOR QUARTER ENDED JUNE 30, 2025
    (₹ in Crores)
    
    Total Income: 4,000.00
    Operating EBITDA: 1,000.00
    PAT: 600.00
    
    Note: Prior period audit fee was Rs. 50 Lakhs.
    """
    extractor = PDFGroundTruthExtractor()
    scale = extractor.detect_unit_scale(text)
    gt = extractor.extract_metrics_from_text(text, symbol="ABC", quarter="Q1 FY26")

    print(f"\n[Vector 2A] Unit Scale Priority Check:")
    print(f"  Detected Unit Scale: {scale} (Expected 1.0 for Crores)")
    print(f"  Extracted Revenue: {gt.revenue_cr} Cr (Expected 4000.0 Cr)")

    assert scale == 1.0, f"FAILED: detect_unit_scale detected scale {scale} instead of 1.0 for Crores"
    assert gt.revenue_cr == 4000.0, f"FAILED: Revenue extracted as {gt.revenue_cr} instead of 4000.0"


def test_unit_scale_billions():
    """Text is reported in Billions: '(₹ in Billions)' or 'Rs. 10 Bn'."""
    text = """
    GLOBAL INDIA LTD
    FINANCIAL RESULTS (₹ in Billions)
    Total Revenue: 50.0
    EBITDA: 12.0
    PAT: 8.0
    """
    extractor = PDFGroundTruthExtractor()
    scale = extractor.detect_unit_scale(text)
    gt = extractor.extract_metrics_from_text(text, symbol="GIL", quarter="Q1 FY26")

    print(f"\n[Vector 2B] Billions Unit Scale Check:")
    print(f"  Detected Scale for Billions: {scale}")
    print(f"  Extracted Revenue: {gt.revenue_cr}")

    # 1 Billion INR = 100 Crores INR -> scale should be 100.0
    assert scale == 100.0, f"FAILED: Billions scale detected as {scale} instead of 100.0"
    assert gt.revenue_cr == 5000.0, f"FAILED: Revenue 50.0 Billions extracted as {gt.revenue_cr} Cr instead of 5000.0 Cr"


def test_unit_scale_past_3000_chars():
    """Unit scale table header appears after 3000 characters of introductory text."""
    filler = "Company background and disclaimer text line.\n" * 80  # ~3600 chars
    table_text = """
    STATEMENT OF FINANCIAL RESULTS (₹ in Lakhs)
    Total Income: 50,00,000
    Operating EBITDA: 10,00,000
    PAT: 5,00,000
    """
    text = filler + table_text
    extractor = PDFGroundTruthExtractor()
    scale = extractor.detect_unit_scale(text)
    gt = extractor.extract_metrics_from_text(text, symbol="LATE", quarter="Q1 FY26")

    print(f"\n[Vector 2C] Unit Scale >3000 chars Check:")
    print(f"  Text length: {len(text)}")
    print(f"  Detected Scale: {scale} (Expected 0.01 for Lakhs)")
    print(f"  Extracted Revenue: {gt.revenue_cr} Cr (Expected 50000.0 Cr)")

    assert scale == 0.01, f"FAILED: Unit scale after 3000 chars missed, detected {scale} instead of 0.01"
    assert gt.revenue_cr == 50000.0, f"FAILED: Revenue extracted as {gt.revenue_cr} instead of 50000.0"


# =====================================================================
# Vector 3: False Positive Regex Extractions
# =====================================================================
def test_ebitda_margin_extracted_as_absolute_ebitda():
    """
    Document has: 'EBITDA Margin: 22.5%' without explicitly writing absolute EBITDA rupees.
    The regex r'\\bebitda\\b...([\\d,]+\\.?\\d*)' matches 'EBITDA Margin: 22.5' and extracts 22.5 Cr as EBITDA!
    """
    text = """
    XYZ CORP Q1 FY26
    Revenue from Operations: Rs. 1,000 Cr
    EBITDA Margin: 22.5%
    Profit After Tax: Rs. 150 Cr
    """
    extractor = PDFGroundTruthExtractor()
    gt = extractor.extract_metrics_from_text(text, symbol="XYZ", quarter="Q1 FY26")

    print(f"\n[Vector 3A] EBITDA Margin Confusion Check:")
    print(f"  Extracted EBITDA Cr: {gt.ebitda_cr}")
    print(f"  Extracted EBITDA Margin %: {gt.ebitda_margin_pct}")

    # EBITDA Cr should NOT be 22.5 (22.5 is the margin percentage!)
    # Absolute EBITDA = 22.5% of 1000 = 225.0 Cr (or None if not explicitly stated as absolute figure)
    assert gt.ebitda_cr != 22.5, f"FAILED: EBITDA Margin 22.5% was extracted as absolute EBITDA {gt.ebitda_cr} Cr!"


def test_deferred_revenue_vs_total_revenue():
    """
    Document states: 'Deferred Revenue: 200 Cr' before 'Total Revenue: 5,000 Cr'.
    Regex r'(?:revenue|sales)...' matches Deferred Revenue first.
    """
    text = """
    TECH SOFTECH Q1 FY26
    Highlights:
    - Deferred Revenue stood at 200.0 Cr
    - Total Revenue from Operations reached 5,000.0 Cr
    - Operating EBITDA: 1,200.0 Cr
    - PAT: 800.0 Cr
    """
    extractor = PDFGroundTruthExtractor()
    gt = extractor.extract_metrics_from_text(text, symbol="TECH", quarter="Q1 FY26")

    print(f"\n[Vector 3B] Deferred vs Total Revenue Check:")
    print(f"  Extracted Revenue Cr: {gt.revenue_cr} (Expected 5000.0)")

    assert gt.revenue_cr == 5000.0, f"FAILED: Revenue matched Deferred Revenue ({gt.revenue_cr}) instead of Total Revenue (5000.0)"


def test_prior_quarter_vs_current_quarter():
    """
    Document compares prior quarter with current quarter:
    'In Q1 FY25 PAT was Rs 100 Cr while in Q1 FY26 PAT grew to Rs 250 Cr'.
    """
    text = """
    GROWTH CORP Q1 FY26
    In Q1 FY25, Total Revenue was 800.0 Cr and PAT was 100.0 Cr.
    In Q1 FY26, Total Revenue reached 1,500.0 Cr and PAT reached 250.0 Cr.
    Operating EBITDA for Q1 FY26 was 400.0 Cr.
    """
    extractor = PDFGroundTruthExtractor()
    gt = extractor.extract_metrics_from_text(text, symbol="GROWTH", quarter="Q1 FY26")

    print(f"\n[Vector 3C] Prior vs Current Quarter Match Check:")
    print(f"  Extracted Revenue Cr: {gt.revenue_cr} (Expected 1500.0)")
    print(f"  Extracted PAT Cr: {gt.pat_cr} (Expected 250.0)")

    assert gt.revenue_cr == 1500.0, f"FAILED: Extracted prior quarter revenue {gt.revenue_cr} instead of target quarter 1500.0"
    assert gt.pat_cr == 250.0, f"FAILED: Extracted prior quarter PAT {gt.pat_cr} instead of target quarter 250.0"


# =====================================================================
# Vector 4: Scanned / Textless / Malformed PDFs & Corrupted Inputs
# =====================================================================
def test_scanned_textless_pdf():
    """Scanned PDF returns empty string from page extract_text()."""
    extractor = PDFGroundTruthExtractor()
    gt = extractor.extract_metrics_from_text("", symbol="SCAN", quarter="Q1 FY26")

    print(f"\n[Vector 4A] Scanned PDF Check:")
    print(f"  Confidence: {gt.extraction_confidence}")
    print(f"  Revenue: {gt.revenue_cr}")

    assert gt.extraction_confidence == 0.0
    assert gt.revenue_cr is None


def test_corrupted_pdf_bytes():
    """Passing invalid non-PDF binary bytes to extract_text_from_pdf."""
    corrupted_bytes = b"NOT_A_PDF_HEADER_SOMETHING_ELSE_12345"
    extractor = PDFGroundTruthExtractor()
    text = extractor.extract_text_from_pdf(corrupted_bytes)

    print(f"\n[Vector 4B] Corrupted Bytes Check:")
    print(f"  Extracted text length: {len(text)}")

    assert text == "" or text == "NOT_A_PDF_HEADER_SOMETHING_ELSE_12345"


def test_malformed_segment_extraction():
    """
    Line containing 'segment' in generic context e.g.:
    'Segment reporting is in accordance with Ind AS 108 Note 4'.
    """
    text = """
    ABC CORP Q1 FY26 (in Crores)
    Total Revenue: 1,000.0
    Operating EBITDA: 200.0
    PAT: 100.0
    Note 4: Segment reporting is prepared in accordance with Ind AS 108.
    """
    extractor = PDFGroundTruthExtractor()
    gt = extractor.extract_metrics_from_text(text, symbol="ABC", quarter="Q1 FY26")

    print(f"\n[Vector 4C] Malformed Segment Line Check:")
    print(f"  Segments Extracted: {gt.segment_results}")

    # Should not capture "Segment reporting is prepared in accordance with Ind AS " with revenue 108 Cr!
    for s in gt.segment_results:
        assert "Ind AS" not in s["name"], f"FAILED: False segment extracted from accounting note: {s}"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
