# Comprehensive Analysis Report: Multi-Source Document Fetcher Architecture (Milestone 1)

**Agent**: Explorer 1  
**Milestone**: Milestone 1 - Concall Engine Upgrade  
**Working Directory**: `d:\GeoNagrik\Dev\git\stock_market\.agents\explorer_m1_1\`  
**Project Root**: `d:\GeoNagrik\Dev\git\stock_market\`  
**Date**: 2026-07-24  

---

## 1. Executive Summary

This report delivers a thorough architectural investigation of the stock market platform's existing document and transcript fetching capabilities, evaluating `providers/screener_provider.py`, `stock_analyzer.py`, `storage/cache.py`, and `storage/sqlite_store.py`. 

Currently, the platform relies exclusively on scraping **Screener.in** as a single point of failure (SPoF) for fetching company documents (concall transcripts, investor presentations, annual reports). While functional for basic transcript retrieval, this architecture presents significant vulnerabilities:
1. **Scraping Fragility**: Direct dependence on Screener.in DOM layout (`section#documents`, `h3` tags, `div` containers).
2. **Missing Exchange Metadata**: Absence of official BSE/NSE filing timestamps, SEBI Regulation 30 submission categorizations, and exchange attachment tokens.
3. **Limited Document Coverage**: Heavy bias towards concall transcripts, while investor presentations (PPTs) and quarterly result PDFs are not systematically fetched, parsed, or integrated into financial analysis engines.
4. **Single-Source Risk**: Any rate limiting (HTTP 429/403) or DOM updates by Screener.in halts the concall analysis engine completely.

To solve these deficiencies, this report outlines the specification and requirements for a **Robust Multi-Source Document Fetcher** implementing a 3-tier fallback architecture:
$$\text{BSE India Announcements API (Tier 1)} \longrightarrow \text{Screener.in Aggregator (Tier 2)} \longrightarrow \text{NSE India Filings API (Tier 3)}$$

---

## 2. Audit of Existing Data Providers & Document Code

### 2.1 ScreenerProvider (`providers/screener_provider.py`)
`ScreenerProvider` implements the `DocumentProvider` abstract class (from `providers/base.py`). Key capabilities and line ranges:

- **Document Link Scraping (`fetch_documents`, Lines 28–138)**:
  - Constructs URL: `https://www.screener.in/company/{symbol}/` (stipping `.NS`/`.BO` suffixes via `_strip_suffix`).
  - Scrapes the HTML using `BeautifulSoup(r.text, "lxml")`.
  - Targets `#documents` section and parses sub-containers with `h3` headings.
  - Heading categories mapped: `"transcript"`, `"presentation"`, `"credit_rating"`, `"annual_report"`, `"other"`.
  - For transcripts, parses `li` elements and extracts text from child `div`s as a date hint (e.g., `"Jul 2025"`).
  - Returns a list of `DocumentLink` objects (`title`, `url`, `category`, `date_hint`).

- **Transcript Text Extraction (`download_transcript_text`, Lines 283–457)**:
  - Fetches target URL using `requests.get` with standard `DEFAULT_HEADERS`.
  - Checks HTTP `Content-Type` header:
    - **PDF Extraction (`_extract_pdf_transcript`, Lines 314–394)**: Uses `pypdf.PdfReader` to extract text page by page up to `MAX_TRANSCRIPT_PAGES` (20 pages). Applies regex pattern filtering to strip operator boilerplate ("listen-only mode", "press star", "chorus call", etc.). Truncates to `MAX_TRANSCRIPT_CHARS` (80,000 chars).
    - **HTML Extraction (`_extract_html_transcript`, Lines 396–457)**: Strips non-content HTML tags (`script`, `style`, `nav`, `footer`, `aside`, ads) and extracts paragraphs/divs.

- **Quarterly Financial Table Scraping (`fetch_quarterly_results`, Lines 140–239)**:
  - **Strategy 1**: Queries Screener Chart API `https://www.screener.in/api/company/{symbol}/chart/?q=Quarterly+Results&consolidated=true`. Header includes `X-Requested-With: XMLHttpRequest`. Returns JSON dataset arrays (Sales, Expenses, OPM %, Net Profit, EPS).
  - **Strategy 2**: Scrapes `#quarters` HTML table using `pandas.read_html`.

### 2.2 Orchestrator Integration (`stock_analyzer.py`)
- **Document Routing (`fetch_documents`, Lines 133–166)**:
  - Calls `doc_provider.fetch_documents(symbol)`.
  - Categorizes into `transcripts`, `presentations`, `credit_ratings`, `annual_reports`.
  - Caches categorized dictionary in `FileCache` under namespace `"documents"` with 24-hour TTL (`CACHE_TTL["documents"] = 86400`).
- **Concall Analysis Pipeline (`analyze_concalls`, Lines 192–308)**:
  - Retrieves transcript list from `fetch_documents`.
  - Chronologically sorts transcripts using `_sort_transcripts_chronologically`.
  - Performs **incremental URL-level caching**: queries `SQLiteStore.get_analysis_by_url(symbol, url, analyzer_type)`. If cached, skips re-downloading and re-analyzing.
  - Downloads transcript text via `doc_provider.download_transcript_text(url)` and runs Gemini/Lexicon analyzer.

### 2.3 Storage & Caching Layer
- **`storage/cache.py` (`FileCache`)**:
  - MD5 hash key generated from namespace + query parameters.
  - Stores JSON payloads with `timestamp` and `ttl` in `data/cache/*.json`.
- **`storage/sqlite_store.py` (`SQLiteStore`)**:
  - `concall_analysis` table: Stores `(symbol, quarter, transcript_url, sentiment_json, analyzer_type, analyzed_at)`.
  - Table lacks index for individual document metadata, attachment checksums, local file paths, or multi-source tracking.

---

## 3. Gaps, Limitations & Fragilities Identified

| Gap / Vulnerability | Current State | Risk Level | Architectural Impact |
| :--- | :--- | :--- | :--- |
| **Single Point of Failure (Screener.in Dependency)** | Only scrapes `screener.in/company/{symbol}/` HTML. No fallback sources. | **CRITICAL** | IP blocks, CAPTCHA triggers, or DOM class name changes completely break document discovery. |
| **No Exchange API Integration** | Zero interaction with BSE India or NSE India corporate filing portals. | **HIGH** | Misses exact SEBI filing timestamps, official announcements, and raw Exchange PDF attachments. |
| **Incomplete Document Types** | Presentations (`presentations`) are listed but ignored during analysis. Quarterly Result PDFs are not downloaded. | **HIGH** | Loses key quantitative management guidance, graphical charts, and segment disclosures present only in investor PPTs. |
| **Coarse Date/Quarter Resolution** | Relies on parsing date string hints (e.g. "Jul 2025") from HTML. | **MEDIUM** | Off-cycle calls (e.g. Mar 2026) cause quarter mapping ambiguity (`Q4 FY26 (Mar)`). Lacks official FY/Quarter filing tags. |
| **Rudimentary PDF Text Extraction** | Single-pass `pypdf` extraction. No OCR or multi-column layout reconstruction. | **MEDIUM** | Text extraction fails or produces garbled text on multi-column concall PDFs or scanned investor presentations. |
| **No Local PDF Persistence** | Downloads PDF bytes to memory, extracts text, and discards PDF file. | **MEDIUM** | Requires re-downloading raw files if PDF extraction algorithms improve or if image/chart analysis is added later. |

---

## 4. Multi-Source Fetcher Architecture & Technical Requirements

To achieve institutional-grade document acquisition, the platform requires a **Multi-Source Document Fetcher** (`MultiSourceDocFetcher`) utilizing a Tiered Provider pattern with cross-source deduplication.

```
                      +------------------------------------------+
                      |   StockAnalyzer / Document Manager       |
                      +------------------------------------------+
                                           |
                                           v
                      +------------------------------------------+
                      |       MultiSourceDocFetcher Router       |
                      +------------------------------------------+
                                           |
         +---------------------------------+---------------------------------+
         | (Tier 1 Primary)                | (Tier 2 Fallback)               | (Tier 3 Secondary Fallback)
         v                                 v                                 v
+------------------+              +------------------+              +------------------+
| BSE India API    |              | Screener Provider|              | NSE India API    |
| Corporate Submission|            | Scraping & Chart |              | Announcements    |
+------------------+              +------------------+              +------------------+
         |                                 |                                 |
         +---------------------------------+---------------------------------+
                                           |
                                           v
                      +------------------------------------------+
                      |   Deduplication & Resolution Engine      |
                      |   - Match by Quarter, Type & Date Window |
                      +------------------------------------------+
                                           |
                                           v
                      +------------------------------------------+
                      | SQLite Document Index & PDF File Store   |
                      | (data/documents/{symbol}/{quarter}/...)  |
                      +------------------------------------------+
```

### 4.1 Exchange API Specifications

#### 1. Tier 1: BSE India Corporate Announcements API
- **Endpoint**: `https://api.bseindia.com/BseIndiaAPI/api/CorporateSubmission/w`
- **Parameters**:
  - `scripcode`: BSE 6-digit scrip code (e.g., `500180` for HDFC Bank, `500325` for Reliance).
  - `strCat`: Category filter (e.g., `"Result"`, `"Company Update"`, `"Board Meeting"`).
  - `strType`: Sub-category filter (`"D"` for disclosures).
  - `strPrevDate`, `strToDate`: Date range in `YYYYMMDD` format.
- **Headers Required**:
  ```python
  {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
      "Referer": "https://www.bseindia.com/",
      "Accept": "application/json, text/plain, */*",
      "Origin": "https://www.bseindia.com"
  }
  ```
- **Response Fields**:
  - `SCRIP_CD`: BSE Scrip Code
  - `SLONGNAME`: Company Name
  - `NEWSSUB`: Submission Category / Headline
  - `HEADLINE`: Full announcement title
  - `CATEGORYNAME`: e.g. `"Company Update"`, `"Financial Results"`
  - `NEWS_DT`: Filing timestamp (e.g., `2025-07-19T17:30:00`)
  - `ATTACHMENTNAME`: Filename on BSE server.
  - **Constructed PDF URL**: `https://www.bseindia.com/xml-data/corpfiling/AttachLive/{ATTACHMENTNAME}`

#### 2. Tier 2: Screener.in Provider (Existing Enhanced)
- Serves as curated aggregator fallback. Excellent for historical concall transcripts where BSE attachment links might point to audio MP3 files or third-party web pages.

#### 3. Tier 3: NSE India Filings API
- **Endpoint**: `https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={SYMBOL}`
- **Session Requirement**: Must establish a session cookie by requesting `https://www.nseindia.com` first, carrying cookies (`nsit`, `nseappid`) on subsequent API calls.
- **Constructed PDF URL**: `https://nselive.nseindia.com/content/corporate/anndecl/{attachment_file}`

---

### 4.2 Ticker & Security Identifier Mapping Matrix
To query BSE APIs, the engine requires mapping NSE tickers to BSE Scrip Codes.

```python
# Identifier Mapping Table Schema
SECURITY_MAPPING = {
    "HDFCBANK": {"bse_code": "500180", "isin": "INE040A01034", "screener_symbol": "HDFCBANK"},
    "RELIANCE": {"bse_code": "500325", "isin": "INE002A01018", "screener_symbol": "RELIANCE"},
    "TCS":      {"bse_code": "532540", "isin": "INE467B01029", "screener_symbol": "TCS"},
    "INFY":     {"bse_code": "500209", "isin": "INE009A01021", "screener_symbol": "INFY"},
    "TVSMOTOR": {"bse_code": "532343", "isin": "INE494B01023", "screener_symbol": "TVSMOTOR"},
}
```

---

### 4.3 Unified Document Schema (`UnifiedDocument`)

A modernized document model to replace `DocumentLink` and support multi-source tracking:

```python
class UnifiedDocument(BaseModel):
    """Institutional unified document object covering transcripts, PPTs, and result PDFs."""
    doc_id: str                          # Deterministic MD5 hash of (source + url/attachment_name)
    symbol: str                          # NSE Ticker Symbol (e.g. "HDFCBANK")
    bse_scrip_code: Optional[str] = None # BSE Scrip Code (e.g. "500180")
    source: Literal["BSE", "SCREENER", "NSE"]
    category: Literal[
        "transcript", "presentation", "quarterly_result_pdf", 
        "annual_report", "credit_rating", "other"
    ]
    quarter_label: str                   # Normalized quarter (e.g., "Q1 FY26")
    financial_year: int                  # e.g., 2026
    filing_timestamp: Optional[str] = None # ISO format filing date/time from Exchange
    title: str                           # Title or headline
    url: str                             # Original remote download URL
    local_pdf_path: Optional[str] = None # Absolute local path to saved PDF
    local_txt_path: Optional[str] = None # Absolute local path to extracted text
    checksum_md5: Optional[str] = None   # MD5 checksum of downloaded file
    file_size_bytes: int = 0
    extraction_status: Literal["pending", "success", "failed"] = "pending"
```

---

### 4.4 Deduplication & Resolution Rules

When fetching documents across BSE, Screener, and NSE for a target quarter (e.g., `Q1 FY26`):
1. **Canonical Quarter Assignment**: Use filing timestamp window to assign canonical Indian Financial Year quarter:
   - **Q1 (Apr–Jun quarter)**: Filed Jul 1 – Sep 15 -> `Q1 FYxx`
   - **Q2 (Jul–Sep quarter)**: Filed Oct 1 – Dec 15 -> `Q2 FYxx`
   - **Q3 (Oct–Dec quarter)**: Filed Jan 1 – Mar 15 -> `Q3 FYxx`
   - **Q4 (Jan–Mar quarter)**: Filed Apr 1 – Jun 15 -> `Q4 FYxx`
2. **Category Classification Rules**:
   - Title matches `transcript`, `concall`, `earnings call`, `audio recording transcript` -> `transcript`
   - Title matches `presentation`, `investor presentation`, `analyst presentation`, `factsheet`, `deck` -> `presentation`
   - Title matches `financial result`, `quarterly result`, `outcome of board meeting`, `audited results`, `unaudited results` -> `quarterly_result_pdf`
3. **Cross-Source Deduplication**:
   - Group candidates by `(category, quarter_label)`.
   - If both BSE and Screener present transcripts for `Q1 FY26`, prefer BSE for official attachment URL, but keep Screener as text fallback if BSE download is an audio/external link.

---

### 4.5 Persistence & Storage Schema Enhancements

To support multi-document caching and raw PDF retention, add a `documents_index` table to `storage/sqlite_store.py`:

```sql
CREATE TABLE IF NOT EXISTS documents_index (
    doc_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    bse_scrip_code TEXT,
    source TEXT NOT NULL,
    category TEXT NOT NULL,
    quarter_label TEXT NOT NULL,
    financial_year INTEGER,
    filing_timestamp TIMESTAMP,
    title TEXT NOT NULL,
    remote_url TEXT NOT NULL,
    local_pdf_path TEXT,
    local_txt_path TEXT,
    checksum_md5 TEXT,
    file_size_bytes INTEGER DEFAULT 0,
    extraction_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, quarter_label, category, source)
);
```

#### Directory Layout for Saved Documents:
```
data/
└── documents/
    ├── HDFCBANK/
    │   ├── Q1_FY26/
    │   │   ├── transcript_bse_a8f9d.pdf
    │   │   ├── transcript_bse_a8f9d.txt
    │   │   ├── presentation_bse_b7c2e.pdf
    │   │   └── result_q1fy26_c3d4e.pdf
    │   └── Q4_FY25/
    │       └── ...
```

---

## 5. Milestone 1 Implementation Roadmap & Interface Specifications

### Module Structure Proposed
- `providers/bse_provider.py`: Implements `BSEProvider` interfacing with BSE Corporate Announcements API and BSE Scrip Lookup.
- `providers/nse_provider.py`: Implements `NSEProvider` interfacing with NSE Corporate Announcements API with cookie management.
- `providers/multi_source_doc_fetcher.py`: Orchestrates multi-tier fetching (`BSE` -> `Screener` -> `NSE`), deduplication, quarter assignment, PDF downloading, local file storage, and SQLite indexing.

### Proposed Primary Interface in `multi_source_doc_fetcher.py`
```python
class MultiSourceDocFetcher:
    """Multi-source document acquisition router (BSE -> Screener -> NSE)."""
    
    def __init__(self, db_store: SQLiteStore = None, cache: FileCache = None):
        self.bse = BSEProvider()
        self.screener = ScreenerProvider()
        self.nse = NSEProvider()
        self.db = db_store or SQLiteStore()
        self.cache = cache or FileCache()

    def fetch_quarterly_documents(
        self, symbol: str, quarters: int = 10, categories: list[str] = None
    ) -> dict[str, list[UnifiedDocument]]:
        """
        Fetch, deduplicate, and catalog documents across transcripts, PPTs, and result PDFs.
        Returns: {"transcripts": [...], "presentations": [...], "results_pdf": [...]}
        """
        ...
```

---

## 6. Summary of Requirements & Next Steps

1. **Implement `BSEProvider` (`providers/bse_provider.py`)**:
   - Implement ticker-to-bse scrip resolution table.
   - Query BSE CorporateSubmission endpoint with category filtering.
2. **Implement `MultiSourceDocFetcher` (`providers/multi_source_doc_fetcher.py`)**:
   - Merge results from BSE, Screener, NSE.
   - Deduplicate documents per quarter.
   - Manage local PDF file downloads and text extraction pipeline.
3. **Update SQLite Store (`storage/sqlite_store.py`)**:
   - Add `documents_index` schema for tracking fetched PDFs and extraction status.
4. **Update `StockAnalyzer` (`stock_analyzer.py`)**:
   - Wire `MultiSourceDocFetcher` as default document provider.
