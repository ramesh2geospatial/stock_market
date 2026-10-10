## 2026-07-24T15:53:46Z
<USER_REQUEST>
You are an Explorer for Milestone 4 (Cross-Validation & Hallucination Defense Engine).

Your working directory is: d:\GeoNagrik\Dev\git\stock_market\.agents\explorer_m4\
Project root: d:\GeoNagrik\Dev\git\stock_market\

Tasks:
1. Examine `analyzers/cross_validator.py` (if existing) or analyze how to design/upgrade it.
2. Examine how concall AI extractions are represented (`analyzers/gemini_analyzer.py`, `SentimentResult` or dict representation).
3. Examine how ground-truth metrics are represented (`providers/pdf_extraction_provider.py` or `analyzers/pdf_ground_truth_extractor.py`, `GroundTruthFinancials` or dict representation).
4. Examine `storage/sqlite_store.py` to check how concall analysis, ground-truth financials, and cross-validation results are currently stored or should be stored.
5. Check existing tests in `tests/` (e.g. `test_cross_validator.py` if any, or `test_sqlite_store.py`, `test_gemini_analyzer.py`).
6. Produce a clear, concrete implementation plan for:
   - Tiered divergence calculation:
     - Relative numeric divergence ($\frac{|\text{Concall} - \text{GroundTruth}|}{\text{GroundTruth}}$) for revenue, ebitda, net_profit, capex.
     - Margin divergence in percentage points ($|\text{Concall Margin} - \text{GroundTruth Margin}|$).
   - Auto-correction threshold (>15% divergence for relative metrics or >3 percentage points for margins) using ground-truth baseline.
   - Hallucination alerts (>50% divergence).
   - Confidence badge mapping:
     - 🟢 High Confidence: divergence <= 5% (and margin <= 1 pp)
     - 🟡 Medium Confidence: 5% < divergence <= 15% (or 1 pp < margin <= 3 pp)
     - 🔴 Low Confidence: divergence > 15% (or margin > 3 pp, or auto-corrected)
   - SQLite store methods (`save_cross_validation_result`, `get_cross_validation_result`, or updating `save_concall_analysis`).
   - `tests/test_cross_validator.py` unit test specifications.

Write your findings to `d:\GeoNagrik\Dev\git\stock_market\.agents\explorer_m4\analysis.md` and send a message back to parent with your summary.
</USER_REQUEST>
