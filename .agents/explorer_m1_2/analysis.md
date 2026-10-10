# Concall Engine Milestone 1 Analysis: Ground-Truth Extraction & Cross-Validation Architecture

**Author**: Explorer 2 (Milestone 1 - Concall Engine Upgrade)  
**Date**: July 24, 2026  
**Status**: Completed Analysis  
**Working Directory**: `d:\GeoNagrik\Dev\git\stock_market\.agents\explorer_m1_2\`  

---

## 1. Executive Summary

This report provides a comprehensive architectural examination of concall transcript analysis, structured financial metric extraction, and SQLite storage persistence within the Indian Stock Market Research Platform. Additionally, it formulates an integration plan to incorporate ground-truth PDF extraction (Investor Presentations & BSE Result PDFs) and tiered cross-validation (divergence calculation, >15% auto-correction, and confidence badging) into the platform.

### Key Discoveries:
1. **Gemini Extraction (`analyzers/gemini_analyzer.py`)**: Uses Gemini 2.5 Flash to extract absolute metrics (`revenue_absolute_cr`, `ebitda_absolute_cr`, `pat_absolute_cr`), growth percentages, segment data, leverage, capex, guidance numbers, and promise tracking assessments (`prior_guidance_met`, `prior_guidance_missed`). Includes explicit Q4 quarter-vs-FY prompt guardrails.
2. **Orchestration & Incremental Caching (`stock_analyzer.py`)**: Manages transcript fetching via Screener Provider, sorts transcripts chronologically for guidance chaining, executes per-URL cache lookup, performs cross-validation against `QuarterlyResult`, and persists results.
3. **SQLite Storage (`storage/sqlite_store.py`)**: `concall_analysis` table stores full JSON-serialized Pydantic `SentimentResult` models indexed by `(symbol, quarter, analyzer_type)` and `(symbol, transcript_url, analyzer_type)`.
4. **Current Validation Engine (`analyzers/cross_validator.py`)**: Already implements initial validation of `revenue_absolute`, `pat_absolute`, and `ebitda_margin_pct` against Screener web-scraped `QuarterlyResult` with a 15% divergence threshold.
5. **Ground-Truth Integration Gap**: Screener scraped data lacks multi-segment detail verification, balance sheet ground-truth (net debt, capex), and presentation guidance tables. Incorporating direct PDF extractions (Investor Presentations & BSE Filings) provides an authoritative Tier-1/Tier-2 ground-truth layer.

---

## 2. Deep-Dive Codebase Tracing

### 2.1 Concall Transcript Analysis & Extraction (`analyzers/gemini_analyzer.py`)

- **Class Structure**: `GeminiAnalyzer` inherits from `BaseSentimentAnalyzer` (line 25).
- **Initialization & Fallback**:
  - Initializes `genai.Client(api_key=api_key)` (line 42).
  - Falls back gracefully to `LexiconAnalyzer` if `google-genai` is uninstalled, API key is missing, or quota is exceeded (429/ResourceExhausted errors, lines 101–110).
  - Rate limiting is enforced at 4.0 seconds interval (~15 RPM, line 37, lines 48–53).
- **Core Method (`analyze_concall`, lines 59–110)**:
  1. Accepts `text` (raw transcript), `quarter` (label like `"Q1 FY25"`), `prior_guidance` (dict), and `prior_targets` (list).
  2. Preprocesses text using `preprocess_transcript(text, max_chars=200000)` (line 81) to strip disclaimers, participant rosters, operator lines, and irrelevant text.
  3. Builds prompt via `_build_prompt()` (lines 112–223) incorporating `prior_context` if prior quarter guidance/targets exist.
  4. Calls `client.models.generate_content(model=GEMINI_MODEL, contents=prompt)` (lines 91–94).
  5. Parses response via `_parse_response()` (lines 225–335).

#### Detailed JSON Schema Requested from Gemini (lines 160–218):
```json
{
  "sentiment_score": <float -1.0 to 1.0>,
  "sentiment_label": "<Positive|Negative|Neutral>",
  "management_tone": "<Confident|Optimistic|Measured|Cautious|Concerned|Defensive>",

  "revenue_absolute_cr": <float or null>,
  "ebitda_absolute_cr": <float or null>,
  "pat_absolute_cr": <float or null>,
  "revenue_growth_pct": <float or null>,
  "ebitda_margin_pct": <float or null>,
  "pat_growth_pct": <float or null>,

  "segment_data": [
    {
      "name": "<segment name>",
      "revenue_cr": <float or null>,
      "growth_pct": <float or null>,
      "margin_pct": <float or null>
    }
  ],

  "net_debt_cr": <float or null>,
  "debt_equity_ratio": <float or null>,
  "capex_actual_cr": <float or null>,
  "order_book_cr": <float or null>,

  "key_highlights": ["<top 5 positive highlights with metrics>"],
  "concerns": ["<top 5 risks/challenges with metrics>"],
  "milestones_achieved": ["<completed items>"],
  "future_targets": ["<forward targets with timeline>"],
  "management_quotes": ["<1-2 verbatim quotes>"],
  "analyst_concerns": ["<top 2-3 analyst pushbacks>"],
  "guidance_numbers": {
    "revenue_guidance": "<string or null>",
    "margin_guidance": "<string or null>",
    "capex_guidance": "<string or null>",
    "other_guidance": "<string or null>"
  },
  "prior_guidance_assessment": [
    {
      "target": "<previous target>",
      "result": "<ACHIEVED|MISSED|PARTIALLY MET|NOT YET DUE>",
      "actual": "<delivered value>"
    }
  ]
}
```

#### Key Extraction Prompt Rules:
- **Q4 vs Full-Year Rule (lines 158)**: Explicit instruction forcing Gemini to extract ONLY individual Q4 quarterly numbers for `revenue_absolute_cr`, `ebitda_absolute_cr`, and `pat_absolute_cr`, setting to `null` if only full-year (FY) values are present.
- **Promise Tracking Chaining (lines 118–133)**: Injects prior quarter's `guidance_numbers` and `future_targets` into the prompt, instructing Gemini to evaluate fulfillment.
- **Parsing Robustness (`_parse_response`, lines 225–335)**:
  - Regex cleanup strips markdown code blocks (` ```json `).
  - Finds opening `{` and closing `}` positions (lines 235–238).
  - Safely converts floats (`_safe_float`, lines 254–260).
  - Categorizes `prior_guidance_assessment`: `ACHIEVED` and `PARTIALLY MET` are mapped to `prior_guidance_met`, while `MISSED` maps to `prior_guidance_missed` (lines 292–306).
  - Constructs and returns Pydantic `SentimentResult` instance.

---

### 2.2 System Orchestration & Concall Lifecycle (`stock_analyzer.py`)

The concall analysis lifecycle in `StockAnalyzer.analyze_concalls()` (lines 192–308) operates as follows:

```
[User Request / Analysis Pipeline]
                 │
                 ▼
     StockAnalyzer.analyze_concalls(symbol)
                 │
                 ├── 1. Fetch Document Links via ScreenerProvider.fetch_documents(symbol)
                 │      Filter for category == "transcript"
                 │
                 ├── 2. Chronological Sorting via _sort_transcripts_chronologically()
                 │      (Oldest quarter first -> Q1 -> Q2 -> Q3 -> Q4 for guidance chain)
                 │
                 ├── 3. Pre-fetch Screener Quarterly Results via fetch_quarterly_results(symbol)
                 │
                 ├── 4. Per-Transcript URL Cache Check via SQLiteStore.get_analysis_by_url()
                 │      ├─ If cached: Hydrate SentimentResult, update prior_guidance & prior_targets chain
                 │      └─ If NOT cached: Continue to download & analyze
                 │
                 ├── 5. Download Transcript Text via ScreenerProvider.download_transcript_text(url)
                 │
                 ├── 6. Gemini Concall Analysis:
                 │      GeminiAnalyzer.analyze_concall(text, quarter_label, prior_guidance, prior_targets)
                 │
                 ├── 7. Cross-Validation Engine:
                 │      CrossValidator.validate_and_correct(analysis, quarterly_results)
                 │      (Checks revenue_absolute, pat_absolute, ebitda_margin_pct vs Screener)
                 │
                 ├── 8. SQLite Persistence:
                 │      SQLiteStore.save_analysis(symbol, quarter, url, sentiment_dict, analyzer_type)
                 │
                 └── 9. Return Chronologically Sorted list[SentimentResult]
```

#### Relevant Code Traces in `stock_analyzer.py`:
- **Document Fetching & Categorization**: Lines 203–204 fetch documents. Transcripts are sorted oldest-to-newest at line 219 (`_sort_transcripts_chronologically`).
- **Guidance & Target Propagation**: Lines 246–248 and lines 291–292 pass and update `prior_guidance` and `prior_targets` sequentially across quarter iterations.
- **Cross-Validation Call**: Lines 279–282:
  ```python
  if analysis.analyzer_type == "gemini" and quarterly_results:
      analysis = self.cross_validator.validate_and_correct(
          analysis, quarterly_results
      )
  ```
- **Persistence Call**: Lines 296–302:
  ```python
  self.db.save_analysis(
      symbol=symbol,
      quarter=quarter_label,
      transcript_url=url,
      sentiment_dict=analysis.model_dump(),
      analyzer_type=self.analyzer_type,
  )
  ```

---

### 2.3 SQLite Storage Schema & Persistence (`storage/sqlite_store.py`)

SQLite operations are encapsulated in `SQLiteStore`. The database schema for concall analysis and related intelligence is initialized in `_init_db()` (lines 23–183).

#### Relevant Table Schemas:

1. **`concall_analysis` Table (lines 47–57)**:
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
   );
   ```

2. **`milestone_tracks` Table (lines 61–72)**:
   ```sql
   CREATE TABLE IF NOT EXISTS milestone_tracks (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       symbol TEXT,
       milestone_name TEXT,
       status TEXT,
       start_quarter TEXT,
       last_updated_quarter TEXT,
       description_json TEXT,
       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       UNIQUE(symbol, milestone_name)
   );
   ```

3. **`financial_statements` Table (lines 122–130)**:
   ```sql
   CREATE TABLE IF NOT EXISTS financial_statements (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       symbol TEXT,
       quarter TEXT,
       statement_json TEXT,
       fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       UNIQUE(symbol, quarter)
   );
   ```

#### Concall Analysis CRUD Operations (`storage/sqlite_store.py`):
- `save_analysis(symbol, quarter, transcript_url, sentiment_dict, analyzer_type)` (lines 236–255): Deletes existing record matching `(symbol, transcript_url, analyzer_type)` and inserts new record storing `sentiment_dict` as JSON.
- `get_analysis(symbol, quarter, analyzer_type)` (lines 257–268): Returns deserialized JSON for a specific quarter and analyzer.
- `get_all_analyses(symbol, analyzer_type)` (lines 270–293): Returns all cached analyses for a symbol ordered by `analyzed_at ASC`.
- `get_analysis_by_url(symbol, url, analyzer_type)` (lines 294–305): Enables URL-level incremental cache lookups.
- `delete_analysis(symbol, quarter, analyzer_type)` (lines 344–356): Public method to delete a specific quarter analysis.

---

## 3. Financial Metric Extraction Data Flow

The table below traces every financial metric extracted by Gemini from concall transcripts to Pydantic model serialization and SQLite persistence.

| Metric Name | Gemini Prompt Key | Pydantic Field (`SentimentResult`) | Cross-Validated? | SQLite Storage Target |
| :--- | :--- | :--- | :--- | :--- |
| **Quarterly Revenue (Rs Cr)** | `revenue_absolute_cr` | `revenue_absolute: Optional[float]` | Yes (vs Screener/PDF) | `concall_analysis.sentiment_json` |
| **Quarterly EBITDA (Rs Cr)** | `ebitda_absolute_cr` | `ebitda_absolute: Optional[float]` | Yes (vs PDF ground-truth) | `concall_analysis.sentiment_json` |
| **Quarterly PAT (Rs Cr)** | `pat_absolute_cr` | `pat_absolute: Optional[float]` | Yes (vs Screener/PDF) | `concall_analysis.sentiment_json` |
| **Revenue YoY Growth %** | `revenue_growth_pct` | `revenue_growth_pct: Optional[float]` | Derived check | `concall_analysis.sentiment_json` |
| **EBITDA Margin %** | `ebitda_margin_pct` | `ebitda_margin_pct: Optional[float]` | Yes (vs Screener/PDF) | `concall_analysis.sentiment_json` |
| **PAT YoY Growth %** | `pat_growth_pct` | `pat_growth_pct: Optional[float]` | Derived check | `concall_analysis.sentiment_json` |
| **Segment Performance** | `segment_data` | `segment_data: list[dict]` | Yes (vs PDF ground-truth) | `concall_analysis.sentiment_json` |
| **Net Debt (Rs Cr)** | `net_debt_cr` | `net_debt_cr: Optional[float]` | Yes (vs PDF ground-truth) | `concall_analysis.sentiment_json` |
| **Debt / Equity Ratio** | `debt_equity_ratio` | `debt_equity_ratio: Optional[float]` | Yes (vs PDF ground-truth) | `concall_analysis.sentiment_json` |
| **Capex Spent (Rs Cr)** | `capex_actual_cr` | `capex_actual_cr: Optional[float]` | Yes (vs PDF ground-truth) | `concall_analysis.sentiment_json` |
| **Order Book Value (Rs Cr)**| `order_book_cr` | `order_book_cr: Optional[float]` | Qualitative check | `concall_analysis.sentiment_json` |
| **Promise Tracking Met** | `prior_guidance_assessment` | `prior_guidance_met: list[dict]` | Internal chain | `concall_analysis.sentiment_json` |
| **Promise Tracking Missed** | `prior_guidance_assessment` | `prior_guidance_missed: list[dict]` | Internal chain | `concall_analysis.sentiment_json` |
| **Data Confidence Badge** | N/A (Generated) | `data_confidence: Literal` | Validation output | `concall_analysis.sentiment_json` |
| **Corrections Log** | N/A (Generated) | `corrections: list[dict]` | Validation output | `concall_analysis.sentiment_json` |

---

## 4. Ground-Truth PDF Extraction & Cross-Validation Architecture Plan

To ensure maximum fidelity and eliminate LLM hallucinations, we introduce a **Ground-Truth PDF Extraction Engine** and a **Tiered Cross-Validation System**.

### 4.1 Ground-Truth Sources

1. **BSE Result Filings / Financial Outcomes (Tier 1 Ground-Truth)**:
   - Official regulatory disclosure filed with BSE/NSE.
   - Contains primary audited/reviewed financial statements, segment reporting (AS 17 / Ind AS 108), and notes to accounts.
2. **Investor Presentation PDFs (Tier 2 Ground-Truth)**:
   - Published concurrently with quarterly results.
   - Contains slide-based segment breakdowns, debt metrics, capex updates, order book size, and quantitative guidance tables.
3. **Screener.in Scraped Data (Tier 3 Baseline)**:
   - Existing web-scraped table data used as fallback when PDF files are unavailable.

---

### 4.2 PDF Extractor Component (`providers/pdf_extraction_provider.py`)

A specialized provider component will extract structured metrics from Investor Presentations and BSE Result PDFs.

#### Data Model (`models/ground_truth.py`):
```python
from pydantic import BaseModel
from typing import Optional, Literal

class SegmentGroundTruth(BaseModel):
    name: str
    revenue_cr: Optional[float] = None
    margin_pct: Optional[float] = None
    growth_pct: Optional[float] = None

class GroundTruthFinancials(BaseModel):
    symbol: str
    quarter: str  # e.g., "Q1 FY25"
    doc_type: Literal["bse_results", "presentation", "screener_web"]
    source_url: str
    
    # Financial Core (Rs Cr)
    revenue_cr: Optional[float] = None
    ebitda_cr: Optional[float] = None
    pat_cr: Optional[float] = None
    ebitda_margin_pct: Optional[float] = None
    eps: Optional[float] = None

    # Balance Sheet & Capex
    net_debt_cr: Optional[float] = None
    debt_equity_ratio: Optional[float] = None
    capex_cr: Optional[float] = None
    order_book_cr: Optional[float] = None

    # Segment Breakdown
    segments: list[SegmentGroundTruth] = []
    
    extracted_at: str = ""
```

#### Extraction Mechanism:
- Uses `pypdf` / `pdfplumber` to extract tables and raw text from PDF documents.
- Passes PDF text/tables to Gemini Flash with a targeted extraction prompt focused exclusively on quantitative table numbers (Revenue, EBITDA, PAT, Segments, Net Debt).

---

### 4.3 Database Schema Extension (`storage/sqlite_store.py`)

Add a new table `ground_truth_financials` to store extracted ground-truth PDF metrics:

```sql
CREATE TABLE IF NOT EXISTS ground_truth_financials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    quarter TEXT NOT NULL,
    doc_type TEXT NOT NULL, -- 'bse_results', 'presentation', or 'screener_web'
    source_url TEXT,
    ground_truth_json TEXT NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, quarter, doc_type)
);
```

#### SQLite Store Interface Additions:
```python
def save_ground_truth(self, symbol: str, quarter: str, doc_type: str, source_url: str, ground_truth_dict: dict):
    """Save or update ground-truth financial extraction."""
    conn = self._conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO ground_truth_financials
               (symbol, quarter, doc_type, source_url, ground_truth_json, fetched_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (symbol, quarter, doc_type, source_url, json.dumps(ground_truth_dict, ensure_ascii=False))
        )
        conn.commit()
    finally:
        conn.close()

def get_ground_truth(self, symbol: str, quarter: str, doc_type: Optional[str] = None) -> Optional[dict]:
    """Retrieve ground-truth extraction for a quarter, prioritizing Tier 1 (bse_results) > Tier 2 (presentation)."""
    conn = self._conn()
    try:
        if doc_type:
            row = conn.execute(
                "SELECT ground_truth_json FROM ground_truth_financials WHERE symbol=? AND quarter=? AND doc_type=?",
                (symbol, quarter, doc_type)
            ).fetchone()
        else:
            # Order by doc_type priority: bse_results > presentation > screener_web
            row = conn.execute(
                """SELECT ground_truth_json FROM ground_truth_financials 
                   WHERE symbol=? AND quarter=? 
                   ORDER BY CASE doc_type 
                       WHEN 'bse_results' THEN 1 
                       WHEN 'presentation' THEN 2 
                       ELSE 3 END ASC LIMIT 1""",
                (symbol, quarter)
            ).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()
```

---

### 4.4 Tiered Cross-Validation Logic & Divergence Math (`analyzers/cross_validator.py`)

#### Divergence Formulas:

1. **Absolute Financial Metrics (Revenue, EBITDA, PAT, Debt, Capex)**:
   $$\text{Divergence \%} = \frac{\left| \text{Value}_{\text{Gemini}} - \text{Value}_{\text{GroundTruth}} \right|}{\left| \text{Value}_{\text{GroundTruth}} \right|} \times 100\%$$

2. **Margin Percentages (EBITDA Margin %, Segment Margin %)**:
   $$\text{Divergence}_{\text{pp}} = \left| \text{Margin}_{\text{Gemini}} - \text{Margin}_{\text{GroundTruth}} \right| \quad (\text{percentage points})$$

#### Auto-Correction Rules & Decision Matrix:

| Divergence Condition | Action Taken | Severity Flag | Confidence Badge |
| :--- | :--- | :--- | :--- |
| $\text{Divergence \%} \le 15\%$ ($\le 3.0\text{ pp}$ margin) | Retain Gemini value (or sync exact decimals). | None | **High Confidence** (`"high"`) |
| $15\% < \text{Divergence \%} \le 50\%$ ($3.0 < \text{pp} \le 10.0$) | **Auto-correct** Gemini field to Ground-Truth value. Log correction. | `"correction"` | **Medium Confidence** (`"medium"`) |
| $\text{Divergence \%} > 50\%$ ($> 10.0\text{ pp}$ margin) | **Auto-correct** Gemini field to Ground-Truth value. Log severe warning. | `"hallucination"` | **Low Confidence** (`"low"`) |
| Metric missing in Gemini concall transcript | Populate from Ground-Truth PDF if available. | `"enriched"` | **High/Medium** |

#### CrossValidator Integration Code Structure:

```python
class CrossValidator:
    """Enhanced Cross-Validator supporting Tiered Ground-Truth PDF validation."""

    def validate_against_ground_truth(
        self,
        analysis: SentimentResult,
        ground_truth: GroundTruthFinancials,
        screener_results: Optional[list[QuarterlyResult]] = None,
    ) -> SentimentResult:
        corrected = analysis.model_copy(deep=True)
        corrections = []

        # Core Metrics to Validate
        metrics_map = [
            ("revenue_absolute", ground_truth.revenue_cr, False),
            ("ebitda_absolute", ground_truth.ebitda_cr, False),
            ("pat_absolute", ground_truth.pat_cr, False),
            ("ebitda_margin_pct", ground_truth.ebitda_margin_pct, True),
            ("net_debt_cr", ground_truth.net_debt_cr, False),
            ("capex_actual_cr", ground_truth.capex_cr, False),
        ]

        for field_name, gt_val, is_pct in metrics_map:
            gemini_val = getattr(corrected, field_name)
            if gemini_val is not None and gt_val is not None:
                corr = self._evaluate_divergence(field_name, gemini_val, gt_val, is_pct)
                if corr:
                    corrections.append(corr)
                    setattr(corrected, field_name, gt_val)  # Auto-correction

        # Segment-level cross-validation
        if ground_truth.segments and corrected.segment_data:
            segment_corrections = self._validate_segments(corrected.segment_data, ground_truth.segments)
            corrections.extend(segment_corrections)

        corrected.corrections = corrections

        # Determine Data Confidence Badge
        if not corrections:
            corrected.data_confidence = "high"
        elif any(c.get("severity") == "hallucination" for c in corrections):
            corrected.data_confidence = "low"
        else:
            corrected.data_confidence = "medium"

        return corrected
```

---

### 4.5 Streamlit UI Confidence Badging Integration Plan

In the dashboard UI (`app.py`), each analyzed quarter will feature a visual badge and an expandable audit trail:

1. **High Confidence (`data_confidence == "high"`)**:
   - Displays a **Green Badge**: `🟢 Verified Ground-Truth (100% Match)`.
2. **Medium Confidence (`data_confidence == "medium"`)**:
   - Displays a **Yellow Badge**: `🟡 Auto-Corrected (>15% Divergence)`.
   - Renders a warning callout detailing corrected metrics (e.g., *"Revenue corrected from Rs 2,400 Cr to Rs 2,800 Cr based on Investor Presentation"*).
3. **Low Confidence (`data_confidence == "low"`)**:
   - Displays a **Red Alert Badge**: `🔴 Hallucination Detected (>50% Divergence)`.
   - Renders an explicit warning card showing original LLM extraction vs Ground-Truth PDF values.

---

## 5. Potential Risks & Edge Case Mitigations

1. **Q4 vs Full-Year Metric Conflation**:
   - *Risk*: Fourth quarter (Q4) concalls heavily emphasize full-year (FY) cumulative performance, leading LLMs to extract FY revenue instead of Q4 revenue.
   - *Mitigation*: Prompt guardrails in `gemini_analyzer.py` explicitly instruct Q4 isolation. The cross-validator compares values against Q4 ground-truth numbers; if a >50% divergence occurs (e.g., FY revenue is ~4x Q4 revenue), auto-correction replaces it with Q4 ground-truth.
2. **Restated Financials & Prior Period Adjustments**:
   - *Risk*: Companies occasionally restate prior quarter numbers in subsequent filings.
   - *Mitigation*: Ground-truth extractions store filing timestamps and version tags.
3. **PDF Scanning / Image Slides**:
   - *Risk*: Investor presentations formatted as raster images fail text-based PDF parsing.
   - *Mitigation*: Fall back to Gemini Multimodal vision input for slide image pages or Screener web baseline.

---

## 6. Actionable Implementation Roadmap for Implementer

1. **Phase 1: Ground-Truth Data Models & Storage**
   - Create `models/ground_truth.py` containing `GroundTruthFinancials` Pydantic schema.
   - Add `ground_truth_financials` table to `storage/sqlite_store.py` with `save_ground_truth` and `get_ground_truth` methods.
2. **Phase 2: PDF Provider & Extractor**
   - Create `providers/pdf_extraction_provider.py` to handle presentation and BSE PDF downloading and structured extraction via Gemini Flash.
3. **Phase 3: CrossValidator Upgrade**
   - Update `analyzers/cross_validator.py` to support tiered ground-truth cross-validation (BSE PDF > Presentation PDF > Screener Web).
   - Implement segment-level divergence calculations and >15% auto-correction logic.
4. **Phase 4: Orchestrator Wiring**
   - Update `StockAnalyzer.analyze_concalls()` in `stock_analyzer.py` to fetch presentation/BSE PDFs, run ground-truth extraction, and trigger cross-validation before persisting to SQLite.
5. **Phase 5: UI Confidence Badges**
   - Add Streamlit confidence badges (`🟢 High`, `🟡 Medium`, `🔴 Low`) and correction callout cards in `app.py`.

---

*Report prepared by Explorer 2 for Milestone 1 of the Concall Engine Upgrade.*
