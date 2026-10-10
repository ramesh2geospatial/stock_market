"""
DEPRECATED: This module is kept for backward compatibility.
All functionality has been moved to:
  - providers/  (data fetching)
  - analyzers/  (sentiment analysis)
  - storage/    (SQLite, Parquet, cache)
  - stock_analyzer.py  (orchestrator)

Use StockAnalyzer from stock_analyzer.py for new code.
"""
from stock_analyzer import StockAnalyzer

# Provide a backward-compatible static interface
_analyzer = StockAnalyzer()


class DataManager:
    """Thin wrapper delegating to the new modular StockAnalyzer."""

    @staticmethod
    def resolve_ticker(query):
        return _analyzer.resolve_ticker(query)

    @staticmethod
    def load_historical_data(ticker):
        return _analyzer.fetch_historical(ticker)

    @staticmethod
    def fetch_financials(ticker):
        return _analyzer.fetch_financials(ticker)

    @staticmethod
    def fetch_corporate_actions(ticker):
        return _analyzer.fetch_corporate_actions(ticker)

    @staticmethod
    def fetch_screener_documents(ticker):
        return _analyzer.fetch_documents(ticker)

    @staticmethod
    def fetch_quarterly_results_full(ticker):
        return _analyzer.fetch_quarterly_results_df(ticker)

    @staticmethod
    def analyze_concalls(ticker):
        results = _analyzer.analyze_concalls(ticker, max_transcripts=2)
        return [r.model_dump() for r in results]

    @staticmethod
    def analyze_sentiment(text):
        r = _analyzer.sentiment_analyzer.analyze_text(text)
        return {"score": r.sentiment_score, "label": r.sentiment_label}

    @staticmethod
    def fetch_news(ticker, company_name):
        return _analyzer.fetch_news(ticker, company_name)

    @staticmethod
    def add_to_watchlist(symbol, name):
        return _analyzer.add_to_watchlist(symbol, name)

    @staticmethod
    def remove_from_watchlist(symbol):
        return _analyzer.remove_from_watchlist(symbol)

    @staticmethod
    def get_watchlist():
        return _analyzer.get_watchlist()

    @staticmethod
    def add_note(symbol, note):
        return _analyzer.add_note(symbol, note)

    @staticmethod
    def get_notes(symbol):
        return _analyzer.get_notes(symbol)
