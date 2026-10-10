# Concall Engine Upgrade Plan

## Overview
Upgrade the Indian Stock Market Research Platform's concall analysis engine with multi-source document fetching, ground-truth PDF extraction, cross-validation with auto-correction & confidence badges, and comprehensive test coverage.

## Milestones

### Milestone 1: Exploration & Architecture Mapping
- **Goal**: Map existing codebase structure (`providers/`, `analyzers/`, `storage/`, `app.py`, `tests/`), examine existing test suite (83+ tests), identify integration points for multi-source ingestion, PDF extraction, cross-validation, and UI badges.
- **Workers**: Spawn 3 Explorers (`teamwork_preview_explorer`).
- **Deliverables**: Comprehensive exploration report and refined `PROJECT.md`.

### Milestone 2: Multi-Source Document Ingestion Engine
- **Goal**: Build/upgrade ingestion provider supporting BSE India Corporate Announcements API -> Screener.in -> NSE India Filings fallback for concall transcripts, investor presentations, and quarterly financial result PDFs.
- **Workers**: Explorer -> Worker -> Reviewers -> Challengers -> Forensic Auditor.
- **Deliverables**: Verified provider module with 100% unit test coverage.

### Milestone 3: Ground-Truth PDF Metric Extraction Engine
- **Goal**: Build PDF parser/extractor to parse financial metrics (Revenue, EBITDA, Net Profit, Segment Results, Capex, Guidance) from Investor Presentation PDFs and BSE/NSE Quarterly Result Announcement PDFs.
- **Workers**: Explorer -> Worker -> Reviewers -> Challengers -> Forensic Auditor.
- **Deliverables**: Verified PDF extraction analyzer with 100% unit test coverage.

### Milestone 4: Cross-Validation & Hallucination Defense Engine
- **Goal**: Build cross-validation engine comparing concall AI extractions vs presentation/BSE PDF ground truth, calculating percentage divergence, auto-correcting when divergence > 15%, and updating SQLite persistence/caching.
- **Workers**: Explorer -> Worker -> Reviewers -> Challengers -> Forensic Auditor.
- **Deliverables**: Verified cross-validation engine with 100% unit test coverage.

### Milestone 5: Streamlit UI Integration & Visual Badging
- **Goal**: Integrate cross-validation results into `app.py` Streamlit UI, rendering clear confidence badges (🟢 high, 🟡 medium, 🔴 low) and auto-corrected ground truth values.
- **Workers**: Explorer -> Worker -> Reviewers -> Challengers -> Forensic Auditor.
- **Deliverables**: Updated `app.py` with UI badges, divergence details, and unit tests for UI rendering helper functions.

### Milestone 6: E2E Test Suite Verification & Quality Hardening
- **Goal**: Verify all 83+ existing unit tests pass cleanly, 100% coverage on all new modules, full platform sanity check.
- **Workers**: Reviewers -> Challengers -> Forensic Auditor.
- **Deliverables**: Final verification report confirming 100% passing tests and zero regressions.
