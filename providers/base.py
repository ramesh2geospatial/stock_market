"""
Abstract Base Classes for all data providers.
Any new data source (paid API, alternate scraper) just implements these interfaces.
"""
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd

from models.stock import StockQuote, QuarterlyResult, DocumentLink


class QuoteProvider(ABC):
    """Interface for fetching stock quotes, history, and financials."""

    @abstractmethod
    def resolve_ticker(self, query: str) -> dict:
        """Resolve a company name/ticker string → {symbol, name}."""
        pass

    @abstractmethod
    def fetch_quote(self, symbol: str) -> StockQuote:
        """Get current price and key metrics."""
        pass

    @abstractmethod
    def fetch_historical(self, symbol: str, period: str = "5y") -> pd.DataFrame:
        """Download OHLCV history as a DataFrame with Date column."""
        pass

    @abstractmethod
    def fetch_financials(self, symbol: str) -> dict:
        """Return {income_statement, balance_sheet, cash_flow, info} DataFrames."""
        pass

    @abstractmethod
    def fetch_corporate_actions(self, symbol: str) -> pd.DataFrame:
        """Return dividend/split history."""
        pass


class DocumentProvider(ABC):
    """Interface for fetching company documents — transcripts, presentations, etc."""

    @abstractmethod
    def fetch_documents(self, symbol: str) -> list[DocumentLink]:
        """Return all available document links for a company."""
        pass

    @abstractmethod
    def fetch_quarterly_results(self, symbol: str) -> list[QuarterlyResult]:
        """Return structured quarterly results (last N quarters)."""
        pass

    @abstractmethod
    def fetch_quarterly_results_df(self, symbol: str) -> pd.DataFrame:
        """Return raw quarterly results table as DataFrame for display."""
        pass

    @abstractmethod
    def download_transcript_text(self, url: str, max_pages: int = 20) -> str:
        """Download a PDF transcript and extract its text."""
        pass


class NewsProvider(ABC):
    """Interface for fetching news articles."""

    @abstractmethod
    def fetch_news(self, symbol: str, company_name: str) -> list[dict]:
        """Return list of news items with title, url, source, pub_date."""
        pass
