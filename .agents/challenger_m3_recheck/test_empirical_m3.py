"""
Empirical Stress Verification Suite for Milestone 3 Remediation Fixes
Worker 4 Fixes Verification in providers/pdf_extraction_provider.py
"""
import sys
import os
import re
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from providers.pdf_extraction_provider import PDFGroundTruthExtractor


def run_empirical_tests():
    extractor = PDFGroundTruthExtractor()
    results = {}
    failures = []

    print("============================================================")
    print("STARTING EMPIRICAL VERIFICATION FOR MILESTONE 3 FIXES")
    print("============================================================")

    # ------------------------------------------------------------------
    # FIX 1: Negative numbers `-1200` and parenthesis loss figures `(1,200.00)`
    # ------------------------------------------------------------------
    print("\n--- Testing Fix 1: Negative numbers and parenthesis loss figures ---")
    fix1_tests = [
        ("-1200", -1200.0),
        ("-1,200.00", -1200.0),
        ("(1,200.00)", -1200.0),
        ("(1200)", -1200.0),
        ("-1,200.50", -1200.5),
        ("( 450.00 )", -450.0),
        (" - 1200 ", -1200.0),
        ("(0)", 0.0),
        ("(0.00)", 0.0),
        ("0", 0.0),
        ("1,200.00", 1200.0),
        (None, None),
        ("", None),
    ]
    fix1_pass = True
    for input_val, expected in fix1_tests:
        actual = extractor._clean_number(input_val)
        if actual != expected:
            msg = f"FAIL _clean_number('{input_val}'): expected {expected}, got {actual}"
            print(f"  [FAIL] {msg}")
            failures.append(msg)
            fix1_pass = False
        else:
            print(f"  [OK] _clean_number('{input_val}') -> {actual}")

    # Full extraction text with loss figures
    loss_text = """
    XYZ LIMITED - FINANCIAL PERFORMANCE
    (Rs in Crores)

    Revenue: 2,500.00
    Operating EBITDA: (450.00)
    PAT: (1,200.00)
    Capex Spent: 150.0
    """
    gt_loss = extractor.extract_metrics_from_text(loss_text, symbol="XYZ", quarter="Q3 FY26")
    if (gt_loss.revenue_cr != 2500.0 or gt_loss.ebitda_cr != -450.0 or 
        gt_loss.pat_cr != -1200.0 or gt_loss.capex_cr != 150.0):
        msg = f"FAIL extract_metrics_from_text loss_text: got rev={gt_loss.revenue_cr}, ebitda={gt_loss.ebitda_cr}, pat={gt_loss.pat_cr}, capex={gt_loss.capex_cr}"
        print(f"  [FAIL] {msg}")
        failures.append(msg)
        fix1_pass = False
    else:
        print(f"  [OK] Loss text extraction: rev={gt_loss.revenue_cr}, ebitda={gt_loss.ebitda_cr}, pat={gt_loss.pat_cr}, capex={gt_loss.capex_cr}")

    results["Fix 1: Negative & Loss Figures"] = "PASS" if fix1_pass else "FAIL"

    # ------------------------------------------------------------------
    # FIX 2: Billions / Bn unit scale factor (100.0 Cr)
    # ------------------------------------------------------------------
    print("\n--- Testing Fix 2: Billions / Bn unit scale factor (100.0 Cr) ---")
    fix2_scale_tests = [
        ("Financial Results (in Billions)", 100.0),
        ("Figures in Rs. Bn", 100.0),
        ("Amounts in INR Billion", 100.0),
        ("Statement in billions", 100.0),
        ("in bn", 100.0),
        ("rs. in billions", 100.0),
        ("in Billion", 100.0),
    ]
    fix2_pass = True
    for text_sample, expected_scale in fix2_scale_tests:
        scale = extractor.detect_unit_scale(text_sample)
        if scale != expected_scale:
            msg = f"FAIL detect_unit_scale('{text_sample}'): expected {expected_scale}, got {scale}"
            print(f"  [FAIL] {msg}")
            failures.append(msg)
            fix2_pass = False
        else:
            print(f"  [OK] detect_unit_scale('{text_sample}') -> {scale}")

    # Test UNIT_SCALES dict map & normalize_unit
    norm_bn_tests = [
        (1.0, "billion", 100.0),
        (12.5, "billions", 1250.0),
        (0.5, "bn", 50.0),
    ]
    for val, u, exp in norm_bn_tests:
        res = extractor.normalize_unit(val, u)
        if res != exp:
            msg = f"FAIL normalize_unit({val}, '{u}'): expected {exp}, got {res}"
            print(f"  [FAIL] {msg}")
            failures.append(msg)
            fix2_pass = False
        else:
            print(f"  [OK] normalize_unit({val}, '{u}') -> {res}")

    # Full text extraction in Billions
    bn_text = """
    GLOBAL ENTERPRISES - FINANCIAL PERFORMANCE
    (in Billions)

    Total Revenue: 12.5
    Operating EBITDA: 3.2
    Net Profit: 1.8
    """
    gt_bn = extractor.extract_metrics_from_text(bn_text, symbol="GLOBAL", quarter="Q4 FY25")
    if gt_bn.revenue_cr != 1250.0 or gt_bn.ebitda_cr != 320.0 or gt_bn.pat_cr != 180.0:
        msg = f"FAIL extract_metrics_from_text bn_text: got rev={gt_bn.revenue_cr}, ebitda={gt_bn.ebitda_cr}, pat={gt_bn.pat_cr}"
        print(f"  [FAIL] {msg}")
        failures.append(msg)
        fix2_pass = False
    else:
        print(f"  [OK] Billions text extraction: rev={gt_bn.revenue_cr}, ebitda={gt_bn.ebitda_cr}, pat={gt_bn.pat_cr}")

    results["Fix 2: Billions Unit Scale"] = "PASS" if fix2_pass else "FAIL"

    # ------------------------------------------------------------------
    # FIX 3: Thousands unit scale factor (0.0001 Cr)
    # ------------------------------------------------------------------
    print("\n--- Testing Fix 3: Thousands unit scale factor (0.0001 Cr) ---")
    fix3_scale_tests = [
        ("Figures in Rs. Thousands", 0.0001),
        ("INR in Th", 0.0001),
        ("in thousand", 0.0001),
        ("in thousands", 0.0001),
        ("Rs. in thousands", 0.0001),
    ]
    fix3_pass = True
    for text_sample, expected_scale in fix3_scale_tests:
        scale = extractor.detect_unit_scale(text_sample)
        if scale != expected_scale:
            msg = f"FAIL detect_unit_scale('{text_sample}'): expected {expected_scale}, got {scale}"
            print(f"  [FAIL] {msg}")
            failures.append(msg)
            fix3_pass = False
        else:
            print(f"  [OK] detect_unit_scale('{text_sample}') -> {scale}")

    norm_th_tests = [
        (10000.0, "thousand", 1.0),
        (50000.0, "thousands", 5.0),
        (1000.0, "th", 0.1),
    ]
    for val, u, exp in norm_th_tests:
        res = extractor.normalize_unit(val, u)
        if res != exp:
            msg = f"FAIL normalize_unit({val}, '{u}'): expected {exp}, got {res}"
            print(f"  [FAIL] {msg}")
            failures.append(msg)
            fix3_pass = False
        else:
            print(f"  [OK] normalize_unit({val}, '{u}') -> {res}")

    th_text = """
    SMALL CAP LIMITED
    (Figures in Rs. Thousands)

    Total Revenue: 50,00,000
    Operating EBITDA: 20,00,000
    PAT: 10,00,000
    """
    gt_th = extractor.extract_metrics_from_text(th_text, symbol="SMALL", quarter="Q1 FY26")
    if gt_th.revenue_cr != 500.0 or gt_th.ebitda_cr != 200.0 or gt_th.pat_cr != 100.0:
        msg = f"FAIL extract_metrics_from_text th_text: got rev={gt_th.revenue_cr}, ebitda={gt_th.ebitda_cr}, pat={gt_th.pat_cr}"
        print(f"  [FAIL] {msg}")
        failures.append(msg)
        fix3_pass = False
    else:
        print(f"  [OK] Thousands text extraction: rev={gt_th.revenue_cr}, ebitda={gt_th.ebitda_cr}, pat={gt_th.pat_cr}")

    results["Fix 3: Thousands Unit Scale"] = "PASS" if fix3_pass else "FAIL"

    # ------------------------------------------------------------------
    # FIX 4: 15,000-character unit scale detection window
    # ------------------------------------------------------------------
    print("\n--- Testing Fix 4: 15,000-character unit scale detection window ---")
    fix4_pass = True
    padding_5k = "A" * 5000 + "\nFinancial Results (in Lakhs)\n"
    scale_5k = extractor.detect_unit_scale(padding_5k)
    if scale_5k != 0.01:
        msg = f"FAIL detect_unit_scale at 5,000 chars: expected 0.01, got {scale_5k}"
        print(f"  [FAIL] {msg}")
        failures.append(msg)
        fix4_pass = False
    else:
        print(f"  [OK] Unit detected at 5,000 chars -> {scale_5k}")

    padding_12k = "B" * 12000 + "\nStatement (in Billions)\n"
    scale_12k = extractor.detect_unit_scale(padding_12k)
    if scale_12k != 100.0:
        msg = f"FAIL detect_unit_scale at 12,000 chars: expected 100.0, got {scale_12k}"
        print(f"  [FAIL] {msg}")
        failures.append(msg)
        fix4_pass = False
    else:
        print(f"  [OK] Unit detected at 12,000 chars -> {scale_12k}")

    padding_14k = "C" * 14500 + "\nFigures in Rs. Thousands\n"
    scale_14k = extractor.detect_unit_scale(padding_14k)
    if scale_14k != 0.0001:
        msg = f"FAIL detect_unit_scale at 14,500 chars: expected 0.0001, got {scale_14k}"
        print(f"  [FAIL] {msg}")
        failures.append(msg)
        fix4_pass = False
    else:
        print(f"  [OK] Unit detected at 14,500 chars -> {scale_14k}")

    # Beyond 15k window: unit should be ignored and return default 1.0
    padding_16k = "D" * 16000 + "\nFinancial Results (in Lakhs)\n"
    scale_16k = extractor.detect_unit_scale(padding_16k)
    if scale_16k != 1.0:
        msg = f"FAIL detect_unit_scale at 16,000 chars: expected 1.0 (fallback), got {scale_16k}"
        print(f"  [FAIL] {msg}")
        failures.append(msg)
        fix4_pass = False
    else:
        print(f"  [OK] Unit beyond 15,000 chars correctly falls back to default 1.0 -> {scale_16k}")

    results["Fix 4: 15k Char Window"] = "PASS" if fix4_pass else "FAIL"

    # ------------------------------------------------------------------
    # FIX 5: NUL byte typo fix (operating profit)
    # ------------------------------------------------------------------
    print("\n--- Testing Fix 5: NUL byte typo fix and operating profit parsing ---")
    fix5_pass = True

    # Check file content for NUL bytes directly
    file_path = PROJECT_ROOT / "providers" / "pdf_extraction_provider.py"
    file_bytes = file_path.read_bytes()
    if b"\x00" in file_bytes:
        msg = "FAIL NUL byte found in pdf_extraction_provider.py binary content!"
        print(f"  [FAIL] {msg}")
        failures.append(msg)
        fix5_pass = False
    else:
        print("  [OK] No NUL bytes found in pdf_extraction_provider.py source code.")

    op_text = """
    ABC MOTORS - PERFORMANCE
    Revenue from Operations: 1,000.0 Cr
    Operating Profit: 250.0 Cr
    PAT: 150.0 Cr
    """
    gt_op = extractor.extract_metrics_from_text(op_text, symbol="ABC", quarter="Q1 FY26")
    if gt_op.ebitda_cr != 250.0:
        msg = f"FAIL extract_metrics_from_text for Operating Profit: expected 250.0, got {gt_op.ebitda_cr}"
        print(f"  [FAIL] {msg}")
        failures.append(msg)
        fix5_pass = False
    else:
        print(f"  [OK] Operating Profit extraction -> {gt_op.ebitda_cr}")

    op_narrative_text = "Operating Profit reached 520.5 Crores."
    gt_op_narr = extractor.extract_metrics_from_text(op_narrative_text, symbol="ABC", quarter="Q1 FY26")
    if gt_op_narr.ebitda_cr != 520.5:
        msg = f"FAIL extract_metrics_from_text for Operating Profit narrative: expected 520.5, got {gt_op_narr.ebitda_cr}"
        print(f"  [FAIL] {msg}")
        failures.append(msg)
        fix5_pass = False
    else:
        print(f"  [OK] Operating Profit narrative extraction -> {gt_op_narr.ebitda_cr}")

    results["Fix 5: NUL Byte & Operating Profit"] = "PASS" if fix5_pass else "FAIL"

    # ------------------------------------------------------------------
    # FIX 6: Verbal narrative phrasing patterns (stood at / reached / recorded at / came in at)
    # ------------------------------------------------------------------
    print("\n--- Testing Fix 6: Verbal narrative phrasing patterns ---")
    fix6_pass = True
    narrative_cases = [
        # Revenue
        ("Revenue from operations stood at Rs 3,400 Cr for the quarter.", "revenue_cr", 3400.0),
        ("Total revenue reached 4,200 Crores.", "revenue_cr", 4200.0),
        ("Net sales recorded at 1,500 Cr.", "revenue_cr", 1500.0),
        ("Income from operations came in at 2,800 Cr.", "revenue_cr", 2800.0),
        ("Sales was 1,100 Cr.", "revenue_cr", 1100.0),
        ("Total Income reported at 3,000 Cr.", "revenue_cr", 3000.0),
        # EBITDA
        ("Operating Profit reached 520.5 Crores.", "ebitda_cr", 520.5),
        ("EBITDA stood at 650 Cr.", "ebitda_cr", 650.0),
        ("Operating EBITDA recorded at 400 Cr.", "ebitda_cr", 400.0),
        ("EBITDA came in at 320 Cr.", "ebitda_cr", 320.0),
        ("EBITDA was 600 Cr.", "ebitda_cr", 600.0),
        ("Operating Profit reported at 350 Cr.", "ebitda_cr", 350.0),
        # PAT
        ("PAT came in at (180) Cr.", "pat_cr", -180.0),
        ("Profit after tax stood at 250 Cr.", "pat_cr", 250.0),
        ("Net profit reached 450 Crores.", "pat_cr", 450.0),
        ("PAT recorded at 350 Cr.", "pat_cr", 350.0),
        ("Profit after tax reported at 500 Cr.", "pat_cr", 500.0),
        # Capex
        ("Capex spent stood at 150 Cr.", "capex_cr", 150.0),
        ("Capital expenditure reached 200 Crores.", "capex_cr", 200.0),
        ("Capex incurred recorded at 80 Cr.", "capex_cr", 80.0),
        ("Capex came in at 95 Cr.", "capex_cr", 95.0),
    ]

    for narrative_text, field, expected in narrative_cases:
        gt = extractor.extract_metrics_from_text(narrative_text, symbol="TEST", quarter="Q1 FY26")
        actual = getattr(gt, field)
        if actual != expected:
            msg = f"FAIL Narrative '{narrative_text}' field '{field}': expected {expected}, got {actual}"
            print(f"  [FAIL] {msg}")
            failures.append(msg)
            fix6_pass = False
        else:
            print(f"  [OK] Narrative '{narrative_text[:40]}...' -> {field}={actual}")

    results["Fix 6: Verbal Narrative Phrasing"] = "PASS" if fix6_pass else "FAIL"

    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------
    print("\n============================================================")
    print("VERIFICATION SUMMARY RESULTS")
    print("============================================================")
    all_passed = True
    for name, status in results.items():
        symbol_status = "[PASS]" if status == "PASS" else "[FAIL]"
        print(f"{name:35s}: {symbol_status}")
        if status != "PASS":
            all_passed = False

    if failures:
        print("\nFailures Detail:")
        for f in failures:
            print(f" - {f}")

    final_verdict = "PASS" if all_passed else "FAIL"
    print(f"\nFINAL VERDICT: {final_verdict}")
    print("============================================================")
    return final_verdict, results, failures


if __name__ == "__main__":
    verdict, res, fail = run_empirical_tests()
    sys.exit(0 if verdict == "PASS" else 1)
