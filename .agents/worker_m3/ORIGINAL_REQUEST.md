## 2026-07-24T15:40:55Z
You are Worker 3 implementing Milestone 3: Ground-Truth PDF Metric Extraction Engine.

Working Directory: d:\GeoNagrik\Dev\git\stock_market\.agents\worker_m3\
Project Root: d:\GeoNagrik\Dev\git\stock_market\

Reference Architecture & Plan:
- Explorer 2 Report: d:\GeoNagrik\Dev\git\stock_market\.agents\explorer_m1_2\analysis.md
- PROJECT.md at project root

Task Requirements:
1. Create `models/ground_truth.py`:
   - Define `GroundTruthFinancials` Pydantic model containing `symbol`, `quarter`, `doc_type` ('presentation'|'financial_results'), `revenue_cr`, `ebitda_cr`, `pat_cr`, `revenue_growth_pct`, `ebitda_margin_pct`, `pat_growth_pct`, `segment_results`, `capex_cr`, `guidance_numbers`, `extraction_confidence`, `extracted_at`, `source_pdf_url`, `source_local_path`.
2. Implement `providers/pdf_extraction_provider.py`:
   - Implement `PDFGroundTruthExtractor` class.
   - Parse text/tables from Investor Presentation PDFs and BSE/NSE Quarterly Result Announcement PDFs (using PyPDF/pypdf or structured regex/table parser with fallback).
   - Extract Revenue, EBITDA, PAT, Segment Results, Capex, and Guidance numbers.
   - Handle financial unit normalization (e.g. converting ₹ Lakhs, ₹ Millions, or USD to ₹ Crores).
3. Update `storage/sqlite_store.py`:
   - Create `ground_truth_financials` table schema with UNIQUE(symbol, quarter, doc_type).
   - Implement `save_ground_truth()`, `get_ground_truth()`, `get_all_ground_truth_for_symbol()`.
4. Update `stock_analyzer.py`:
   - Connect `PDFGroundTruthExtractor` when documents are fetched for a stock.
5. Create Unit Tests:
   - Create `tests/test_pdf_ground_truth_extractor.py` with 100% test coverage.
   - Verify all existing pytest unit tests pass cleanly (`python -m pytest -o pythonpath=.`).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

When finished, write `changes.md` and `handoff.md` in your working directory and notify parent via send_message.
