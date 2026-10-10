# Original User Request

## 2026-07-24T20:53:29Z

Audit and upgrade the concall analysis engine in the Indian stock market analysis platform to reliably fetch the latest quarterly concall transcripts, investor presentations, and quarterly financial result PDFs using a multi-source fallback strategy (BSE India Corporate Announcements → Screener.in → NSE India Filings). Use investor presentations and official exchange PDF filings as ground-truth sources to cross-validate extracted concall numbers and summaries.

Working directory: d:\GeoNagrik\Dev\git\stock_market
Integrity mode: development

## Requirements

### R1. Multi-Source Document Ingestion (BSE → Screener → NSE)
Implement a resilient multi-source fetcher for concall transcripts, investor presentations, and quarterly result filings:
1. Query BSE India Announcements API / Corporate Filings first for latest quarterly disclosures.
2. Fall back to Screener.in document links if BSE link parsing fails or is missing.
3. Fall back to NSE India Corporate Filings as a tertiary source.
Ensure new quarterly results and concall transcripts are discovered automatically without missing recent releases.

### R2. Ground Truth Extraction from Presentations & BSE PDFs
Extract financial metrics (Revenue, EBITDA, Net Profit, Segment Results, Capex, Guidance) from:
- Investor Presentation PDFs (`PPT` / `Presentation` links)
- Official BSE/NSE Quarterly Result Announcement PDFs
Establish these extracted numbers as ground-truth baselines.

### R3. Cross-Validation & Hallucination Defense Engine
Compare concall AI extraction results against the presentation/BSE PDF ground truth:
- Calculate percentage divergence for key financial metrics.
- Flag discrepancies in the UI with clear confidence badges (🟢 high, 🟡 medium, 🔴 low).
- Auto-correct divergent concall numbers using verified BSE filing / Presentation ground truth.

### R4. Test Coverage & Quality Verification
Ensure 100% of new modules (fetching, PDF parsing, cross-validation, UI rendering) have comprehensive unit tests in `tests/`. Verify that all existing 83+ unit tests continue to pass with zero regressions.

## Acceptance Criteria

### Document Retrieval & Source Fallback
- [ ] Successfully fetches latest concall transcripts, investor presentations, and quarterly result PDFs for Indian tickers (e.g. HDFCBANK, RELIANCE, INFYS) using BSE → Screener → NSE fallback.
- [ ] Correctly parses PDF links from BSE India Announcements even when headers or content types vary.

### Ground Truth Extraction & Cross-Validation
- [ ] Extracts structured financial metrics from investor presentations and BSE quarterly result PDFs.
- [ ] Cross-validates concall AI extracted numbers against ground truth metrics and flags discrepancies with confidence badges in `app.py`.
- [ ] Auto-corrects concall numbers when divergence exceeds 15% threshold using verified ground truth.

### Integrity & Automated Verification
- [ ] All unit tests in `tests/` pass cleanly via `python -m pytest tests/`.
- [ ] Existing platform features (Streamlit UI tabs, SQLite caching, cross-quarter intelligence) remain fully operational.
