"""
Empirical Verification Script for Milestone 3 (Ground-Truth PDF Metric Extraction Engine).
Executed by Challenger 2.
"""
import sys
import os
import json
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

from models.ground_truth import GroundTruthFinancials
from providers.pdf_extraction_provider import PDFGroundTruthExtractor
from storage.sqlite_store import SQLiteStore


def test_sqlite_storage_and_retrieval():
    print("--- 1. Testing SQLite GroundTruthFinancials Storage & Retrieval ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_m3_gt.db"
        store = SQLiteStore(db_path=str(db_path))

        # Test A: Insert Object
        gt_pres = GroundTruthFinancials(
            symbol="TATASTEEL",
            quarter="Q3 FY25",
            doc_type="presentation",
            revenue_cr=55000.0,
            ebitda_cr=7500.0,
            pat_cr=2100.0,
            revenue_growth_pct=5.2,
            ebitda_margin_pct=13.64,
            pat_growth_pct=-12.5,
            segment_results=[{"name": "India Operations", "revenue_cr": 35000.0}],
            capex_cr=3200.0,
            guidance_numbers={"capex_guidance": "10000 Cr in FY26"},
            extraction_confidence=1.0,
            source_pdf_url="https://example.com/tatasteel_q3.pdf",
            source_local_path="/tmp/tatasteel_q3.pdf",
        )
        res_a = store.save_ground_truth(gt_pres)
        assert res_a is True, "Failed to save GroundTruthFinancials object"

        # Test B: Insert Dict & Upsert with financial_results
        gt_fin_dict = {
            "symbol": "TATASTEEL",
            "quarter": "Q3 FY25",
            "doc_type": "financial_results",
            "revenue_cr": 55120.5,
            "ebitda_cr": 7550.0,
            "pat_cr": 2150.0,
            "extraction_confidence": 1.0,
        }
        res_b = store.save_ground_truth(gt_fin_dict)
        assert res_b is True, "Failed to save GroundTruthFinancials dict"

        # Test C: Retrieve exact doc_type
        retrieved_pres = store.get_ground_truth("TATASTEEL", "Q3 FY25", doc_type="presentation")
        assert retrieved_pres is not None, "Failed to retrieve presentation"
        assert retrieved_pres.symbol == "TATASTEEL"
        assert retrieved_pres.revenue_cr == 55000.0
        assert retrieved_pres.segment_results[0]["name"] == "India Operations"

        retrieved_fin = store.get_ground_truth("TATASTEEL", "Q3 FY25", doc_type="financial_results")
        assert retrieved_fin is not None, "Failed to retrieve financial_results"
        assert retrieved_fin.revenue_cr == 55120.5

        # Test D: Priority fallback when doc_type is None (should favor financial_results)
        prio_retrieved = store.get_ground_truth("TATASTEEL", "Q3 FY25")
        assert prio_retrieved is not None
        assert prio_retrieved.doc_type == "financial_results", f"Expected financial_results, got {prio_retrieved.doc_type}"
        assert prio_retrieved.revenue_cr == 55120.5

        # Test E: Get all for symbol
        all_gt = store.get_all_ground_truth_for_symbol("TATASTEEL")
        assert len(all_gt) == 2, f"Expected 2 entries, got {len(all_gt)}"

        # Test F: Non-existent symbol
        assert store.get_ground_truth("NONEXISTENT", "Q1 FY26") is None
        assert store.get_all_ground_truth_for_symbol("NONEXISTENT") == []

        print("--> Storage and Retrieval Tests PASSED!")


def test_unit_conversion_and_confidence():
    print("--- 2. Testing Unit Conversion Scale Accuracy & Confidence Scoring ---")
    extractor = PDFGroundTruthExtractor()

    scale_lakh = extractor.detect_unit_scale("Revenue in Lakhs: 10000")
    print(f"  Lakhs scale: {scale_lakh} (expected 0.01)")
    assert scale_lakh == 0.01, f"Lakhs scale expected 0.01, got {scale_lakh}"

    scale_million = extractor.detect_unit_scale("Figures in Millions: 500")
    print(f"  Millions scale: {scale_million} (expected 0.1)")
    assert scale_million == 0.1, f"Millions scale expected 0.1, got {scale_million}"

    scale_usd = extractor.detect_unit_scale("Amounts in USD Millions: 100")
    print(f"  USD Millions scale: {scale_usd} (expected 8.3)")
    assert scale_usd == 8.3, f"USD scale expected 8.3, got {scale_usd}"

    scale_crore = extractor.detect_unit_scale("Rs. in Crores: 450")
    print(f"  Crores scale: {scale_crore} (expected 1.0)")
    assert scale_crore == 1.0, f"Crores scale expected 1.0, got {scale_crore}"

    print("Checking UNIT_SCALES dictionary:")
    assert extractor.UNIT_SCALES["lakh"] == 0.01
    assert extractor.UNIT_SCALES["million"] == 0.1
    assert extractor.UNIT_SCALES["usd_million"] == 8.3
    assert extractor.UNIT_SCALES["crore"] == 1.0

    scale_th = extractor.UNIT_SCALES.get("thousand")
    print(f"  Thousands scale in UNIT_SCALES: {scale_th} (expected 0.0001, actual {scale_th})")
    th_bug_found = False
    if scale_th != 0.0001:
        print(f"  [DISCOVERY/BUG] Thousands scale is {scale_th}, which is off by a factor of 10! (Should be 0.0001)")
        th_bug_found = True

    print("Checking confidence scoring:")
    gt3 = extractor.extract_metrics_from_text("Total Revenue: 100 Cr\nEBITDA: 20 Cr\nPAT: 10 Cr")
    print(f"  3/3 metrics confidence: {gt3.extraction_confidence} (expected 1.0)")
    assert gt3.extraction_confidence == 1.0

    gt2 = extractor.extract_metrics_from_text("Total Revenue: 100 Cr\nPAT: 10 Cr")
    print(f"  2/3 metrics confidence: {gt2.extraction_confidence} (expected 0.67)")
    assert gt2.extraction_confidence == 0.67

    gt1 = extractor.extract_metrics_from_text("Total Revenue: 100 Cr")
    print(f"  1/3 metrics confidence: {gt1.extraction_confidence} (expected 0.33)")
    assert gt1.extraction_confidence == 0.33

    gt0_margin = extractor.extract_metrics_from_text("Operating Margin: 15.5%")
    print(f"  0/3 core metrics + margin confidence: {gt0_margin.extraction_confidence} (expected 0.33)")
    assert gt0_margin.extraction_confidence == 0.33

    gt0 = extractor.extract_metrics_from_text("No metrics here")
    print(f"  0 metrics confidence: {gt0.extraction_confidence} (expected 0.0)")
    assert gt0.extraction_confidence == 0.0

    print("--> Unit Conversion and Confidence Tests Complete!")
    return th_bug_found


def test_edge_case_payloads():
    print("--- 3. Testing Edge Case Payloads ---")
    extractor = PDFGroundTruthExtractor()
    neg_bug_found = False
    op_bug_found = False

    # Case A: Net Loss / Negative PAT & Negative EBITDA
    loss_text = """
    RELIANCE POWER LIMITED
    QUARTERLY RESULTS (in Cr)
    Total Revenue: 1,200.5
    Operating EBITDA: -150.0
    PAT: -350.2
    PAT Growth: -45.0%
    """
    gt_loss = extractor.extract_metrics_from_text(loss_text, symbol="RPOWER", quarter="Q3 FY25")
    print(f"  Negative PAT extraction: pat_cr={gt_loss.pat_cr}, ebitda_cr={gt_loss.ebitda_cr}")
    if gt_loss.ebitda_cr != -150.0 or gt_loss.pat_cr != -350.2:
        print(r"  [DISCOVERY/BUG] Negative EBITDA/PAT extraction failed! Regex ([\d,]+\.?\d*) rejects negative sign '-'!")
        neg_bug_found = True

    # Case B: USD Million Conversion
    usd_text = """
    WIPRO LIMITED - US SEC FILING
    (in USD Millions)
    Net Revenue: $2,650.0
    EBITDA: $530.0
    PAT: $397.5
    """
    gt_usd = extractor.extract_metrics_from_text(usd_text, symbol="WIPRO", quarter="Q3 FY25")
    print(f"  USD conversion: revenue_cr={gt_usd.revenue_cr} (2650 * 8.3 = 21995.0)")
    assert gt_usd.revenue_cr == round(2650.0 * 8.3, 2)  # 21995.0
    assert gt_usd.ebitda_cr == round(530.0 * 8.3, 2)    # 4399.0
    assert gt_usd.pat_cr == round(397.5 * 8.3, 2)       # 3299.25

    # Case C: Operating Profit Regex check (NUL byte inspection)
    op_profit_text = """
    TCS LIMITED
    (in Crores)
    Total Income: 60,000
    Operating Profit: 15,000
    PAT: 12,000
    """
    gt_op = extractor.extract_metrics_from_text(op_profit_text, symbol="TCS", quarter="Q3 FY25")
    print(f"  Operating Profit matching: ebitda_cr={gt_op.ebitda_cr}")
    if gt_op.ebitda_cr is None:
        print("  [DISCOVERY/BUG] Operating Profit was NOT extracted as EBITDA! Pattern has 'operating\\0 profit' null byte typo!")
        op_bug_found = True

    # Case D: Extremely Large Number (2,50,000.50)
    large_text = "Total Revenue: 2,50,000.50 Cr\nEBITDA: 50,000 Cr\nPAT: 30,000 Cr"
    gt_large = extractor.extract_metrics_from_text(large_text, symbol="BIGCO", quarter="Q1 FY26")
    assert gt_large.revenue_cr == 250000.50

    # Case E: Segment results parsing with multiple lines
    seg_text = """
    BUSINESS SEGMENTS (in Lakhs):
    Segment Automobile | Revenue: 50,00,000
    Segment Aerospace | Revenue: 20,00,000
    """
    gt_seg = extractor.extract_metrics_from_text(seg_text, symbol="AUTO", quarter="Q1 FY26")
    print(f"  Segments extracted: {len(gt_seg.segment_results)}")
    assert len(gt_seg.segment_results) == 2
    assert gt_seg.segment_results[0]["revenue_cr"] == 50000.0  # 50,00,000 Lakhs = 50,000 Cr

    print("--> Edge Case Payloads Complete!")
    return neg_bug_found, op_bug_found


if __name__ == "__main__":
    test_sqlite_storage_and_retrieval()
    th_bug = test_unit_conversion_and_confidence()
    neg_bug, op_bug = test_edge_case_payloads()

    print("\n================ SUMMARY OF EMPIRICAL VERIFICATION ================")
    print("1. GroundTruthFinancials Storage & Retrieval (SQLite): PASS")
    print("2. Unit Conversion Scale Accuracy (Lakhs=0.01, Millions=0.1, USD=8.3, Crores=1.0): PASS")
    print("3. Extraction Confidence Scoring (0.0 to 1.0): PASS")
    if th_bug:
        print("4. Thousands Unit Scale (0.0001): FAIL (Off by 10x: set to 0.00001)")
    else:
        print("4. Thousands Unit Scale (0.0001): PASS")
    if neg_bug:
        print("5. Negative Financial Numbers (Losses): FAIL (Regex [\\d,]+\\.?\\d* rejects negative sign)")
    else:
        print("5. Negative Financial Numbers (Losses): PASS")
    if op_bug:
        print("6. Operating Profit Extraction: FAIL (Null-byte ASCII typo 'operating\\0 profit')")
    else:
        print("6. Operating Profit Extraction: PASS")
