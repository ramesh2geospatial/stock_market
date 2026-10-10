# Soft Handoff Report: Milestone 1 Concall Engine Upgrade Analysis

**From**: Explorer 2 (`.agents/explorer_m1_2/`)  
**To**: Parent Agent (`01fab84e-001f-475f-9d21-54ab97c77436`) / Implementer  
**Date**: 2026-07-24  
**Handoff Type**: Soft  

---

## 1. Observation

Direct observations from codebase inspection across target files:

1. **`analyzers/gemini_analyzer.py`**:
   - Lines 25–46: `GeminiAnalyzer` inherits from `BaseSentimentAnalyzer`, initializes `genai.Client(api_key=api_key)`, and falls back to `LexiconAnalyzer` if API is missing or quota fails.
   - Lines 59–110: `analyze_concall()` preprocesses text via `preprocess_transcript()`, builds prompt, calls Gemini Flash model, parses JSON response, and handles rate limiting / 429 quota errors.
   - Lines 135–218: Prompt requests structured JSON including `revenue_absolute_cr`, `ebitda_absolute_cr`, `pat_absolute_cr`, `revenue_growth_pct`, `ebitda_margin_pct`, `pat_growth_pct`, `segment_data`, `net_debt_cr`, `debt_equity_ratio`, `capex_actual_cr`, `order_book_cr`, `guidance_numbers`, and `prior_guidance_assessment`. Line 158 contains explicit instructions for Q4 quarter vs FY isolation.
   - Lines 225–335: `_parse_response()` cleans JSON, handles `prior_guidance_assessment` (`ACHIEVED`, `PARTIALLY MET`, `MISSED`), and returns Pydantic `SentimentResult`.

2. **`stock_analyzer.py`**:
   - Lines 192–308: `analyze_concalls()` fetches documents via `ScreenerProvider.fetch_documents()`, sorts transcripts chronologically (`_sort_transcripts_chronologically`), checks URL cache in SQLite, passes `prior_guidance` and `prior_targets` for promise tracking, executes `CrossValidator.validate_and_correct()`, and caches the result via `db.save_analysis()`.

3. **`storage/sqlite_store.py`**:
   - Lines 47–57: `concall_analysis` table schema:
     ```sql
     CREATE TABLE IF NOT EXISTS concall_analysis (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         symbol TEXT,
         quarter TEXT,
         transcript_url TEXT,
         sentiment_json TEXT,
         analyzer_type TEXT DEFAULT 'lexicon',
         analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         UNIQUE(symbol, quarter, analyzer_type)
     )
     ```
   - Lines 236–305: CRUD methods `save_analysis`, `get_analysis`, `get_all_analyses`, and `get_analysis_by_url`.

4. **`analyzers/cross_validator.py`**:
   - Lines 25–93: `CrossValidator.validate_and_correct()` compares Gemini's `revenue_absolute`, `pat_absolute`, and `ebitda_margin_pct` against Screener's web-scraped `QuarterlyResult`.
   - Line 18: `_CORRECTION_THRESHOLD = 0.15` (15%) for relative numeric divergence and >3 pp for margin %. Automatically corrects divergent numbers and sets `data_confidence` (`"high"`, `"medium"`, `"low"`).

5. **`models/analysis.py`**:
   - Lines 60–63: `SentimentResult` already includes fields `data_confidence: Literal["high", "medium", "low"]` and `corrections: list[dict]`.

---

## 2. Logic Chain

1. **Premise**: Concall transcript extraction can suffer from LLM hallucinations, transcript formatting quirks, or Q4/FY metric confusion.
2. **Step 1**: Current concall analysis pipeline in `stock_analyzer.py` extracts detailed financials via Gemini 2.5 Flash (`gemini_analyzer.py`) and persists `SentimentResult` as JSON in SQLite (`sqlite_store.py`).
3. **Step 2**: Existing validation in `cross_validator.py` compares numbers against Screener web data. However, web-scraped data lacks segment breakdowns, balance sheet debt details, and official slide guidance.
4. **Step 3**: Regulatory filings (BSE Result PDFs) and Investor Presentation PDFs represent Tier-1 and Tier-2 authoritative ground-truth sources.
5. **Step 4**: By introducing a PDF extraction provider (`providers/pdf_extraction_provider.py`), storing ground-truth metrics in SQLite (`ground_truth_financials` table), and updating `CrossValidator` to perform tiered validation against ground-truth PDFs, any divergence >15% will be auto-corrected, and `data_confidence` badges (`high`, `medium`, `low`) will accurately reflect data integrity.

---

## 3. Caveats

- **Raster Image PDFs**: Scraped investor presentations that consist entirely of scanned image slides will require OCR or Gemini Multimodal vision input.
- **Varying PDF Formats**: Companies present segment data in different formats (e.g. standalone vs consolidated, gross vs net revenue). Ground-truth models must account for key normalization rules.

---

## 4. Conclusion

The existing concall analysis and SQLite storage architecture is robust and modular. Integrating ground-truth PDF extraction (Investor Presentations & BSE Result PDFs) into `stock_analyzer.py` and upgrading `cross_validator.py` with tiered divergence math (>15% auto-correction) will eliminate hallucination risks, ensure ground-truth accuracy, and provide clear UI confidence badges (`🟢 High`, `🟡 Medium`, `🔴 Low`).

---

## 5. Verification Method

1. **File Inspection**:
   - Inspect `.agents/explorer_m1_2/analysis.md` for full architectural plan and database schemas.
   - Inspect `analyzers/gemini_analyzer.py` (lines 135–218, lines 225–335).
   - Inspect `stock_analyzer.py` (lines 192–308).
   - Inspect `storage/sqlite_store.py` (lines 47–57, lines 236–305).
   - Inspect `analyzers/cross_validator.py` (lines 25–93).
2. **Python Syntax / Model Verification**:
   - Run python check on `models/analysis.py` to confirm Pydantic models compile without error:
     ```powershell
     python -c "from models.analysis import SentimentResult; print(SentimentResult.model_fields.keys())"
     ```

---

## 6. Remaining Work (For Implementer)

1. **Create `models/ground_truth.py`**: Define `GroundTruthFinancials` Pydantic model for ground-truth PDF extractions.
2. **Extend SQLite Storage**: Add `ground_truth_financials` table and helper methods (`save_ground_truth`, `get_ground_truth`) in `storage/sqlite_store.py`.
3. **Build `providers/pdf_extraction_provider.py`**: Implement PDF download and Gemini Flash table extraction for Investor Presentations and BSE Result PDFs.
4. **Upgrade `analyzers/cross_validator.py`**: Add ground-truth PDF validation methods, segment cross-checking, >15% auto-correction logic, and severity tagging.
5. **Wire Orchestrator & Streamlit UI**: Connect PDF extraction and cross-validation inside `stock_analyzer.py` and render confidence badges (`🟢 High`, `🟡 Medium`, `🔴 Low`) in `app.py`.
