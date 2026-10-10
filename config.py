"""
Centralized configuration for the Stock Market Analysis Platform.
All settings, API keys, and constants live here.
"""
import os
from pathlib import Path

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Paths ---
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
HISTORICAL_DIR = DATA_DIR / "historical"
DB_PATH = DATA_DIR / "portfolio.db"

# Ensure directories exist
CACHE_DIR.mkdir(parents=True, exist_ok=True)
HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)

# --- API Keys ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# --- Agentic Coding AI Models ---
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FLASH_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
CLAUDE_OPUS_MODEL = os.getenv("CLAUDE_OPUS_MODEL", "claude-3-7-sonnet-20250219")  # Opus / High reasoning tier

# --- Supabase Configuration (Stock Market Research Persistence) ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://nbyzclczjoxaemcckxne.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
SUPABASE_PROJECT_ID = os.getenv("SUPABASE_PROJECT_ID", "nbyzclczjoxaemcckxne")
STOCK_DOCUMENTS_BUCKET = "stock_documents"
STOCK_BACKUPS_BUCKET = "stock_backups"



# --- Analysis Settings ---
MAX_QUARTERS = 10           # Number of quarters for spider analysis
MAX_TRANSCRIPT_PAGES = 20   # Max PDF pages to extract per transcript
MAX_TRANSCRIPT_CHARS = 80000  # Max characters per transcript text

# --- Cache TTL (seconds) ---
CACHE_TTL = {
    "quote": 300,            # 5 minutes
    "historical": 3600,      # 1 hour
    "financials": 3600,      # 1 hour
    "documents": 86400,      # 24 hours
    "quarterly": 86400,      # 24 hours
    "news": 900,             # 15 minutes
    "analysis": 604800,      # 7 days
}

# --- MF Holdings Tracker Settings ---
MF_SYNC_BATCH_SIZE = int(os.getenv("MF_SYNC_BATCH_SIZE", "500"))  # Rows per Supabase fetch batch
MF_SYNC_TIMEOUT = int(os.getenv("MF_SYNC_TIMEOUT", "30"))         # HTTP timeout for MF data fetch
MF_CACHE_TTL = int(os.getenv("MF_CACHE_TTL", "86400"))            # 24 hours local cache validity
MF_DEFAULT_TOP_N = int(os.getenv("MF_DEFAULT_TOP_N", "20"))       # Default top N stocks to show


# --- External URLs (easy to update if endpoints change) ---
SCREENER_BASE_URL = "https://www.screener.in"
SCREENER_COMPANY_URL = SCREENER_BASE_URL + "/company/{symbol}/"
SCREENER_CHART_API_URL = SCREENER_BASE_URL + "/api/company/{symbol}/chart/"

YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"

# --- HTTP Headers ---
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# --- Spider Chart Dimensions ---
SPIDER_DIMENSIONS = [
    "Revenue Growth",
    "Profitability",
    "EBITDA Trend",
    "Debt Management",
    "EPS Growth",
    "Operational Efficiency",
]
