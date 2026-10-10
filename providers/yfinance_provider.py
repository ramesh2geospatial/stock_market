"""
yfinance-based provider for stock quotes, historical data, and financials.
"""
import urllib.parse
import requests
import yfinance as yf
import pandas as pd

from providers.base import QuoteProvider
from models.stock import StockQuote
from config import YAHOO_SEARCH_URL, DEFAULT_HEADERS


class YFinanceProvider(QuoteProvider):
    """Concrete provider using the yfinance library and Yahoo Finance APIs."""

    def resolve_ticker(self, query: str) -> dict:
        """
        Resolve a company name into an Indian market ticker.
        Checks .NS/.BO suffix first, then searches Yahoo Finance API.
        """
        query = query.strip()

        # Direct validation if already suffixed
        if query.upper().endswith((".NS", ".BO")):
            symbol = query.upper()
            try:
                info = yf.Ticker(symbol).info
                return {"symbol": symbol, "name": info.get("longName", symbol)}
            except Exception:
                pass

        # Search Yahoo Finance API
        try:
            params = {"q": query, "newsCount": 0}
            r = requests.get(
                YAHOO_SEARCH_URL, params=params,
                headers=DEFAULT_HEADERS, timeout=10,
            )
            if r.status_code == 200:
                quotes = r.json().get("quotes", [])
                # Prefer Indian exchange, excluding mutual funds (starting with 0P)
                indian = [q for q in quotes
                          if q.get("symbol", "").endswith((".NS", ".BO"))
                          and not q.get("symbol", "").startswith("0P")]
                
                # Smart retry if no valid Indian stock found
                if not indian:
                    query_lower = query.lower()
                    if "kotak" in query_lower and "mahindra" not in query_lower:
                        return self.resolve_ticker(query_lower.replace("kotak", "kotak mahindra"))
                    if "sbi" in query_lower and "state" not in query_lower:
                        return self.resolve_ticker("state bank of india")
                
                best = (indian or quotes or [None])[0]
                if best:
                    return {
                        "symbol": best["symbol"],
                        "name": best.get("longName")
                               or best.get("shortname")
                               or best["symbol"],
                    }
        except Exception as e:
            print(f"[YFinanceProvider] Ticker search error: {e}")

        # Fallback: append .NS
        return {"symbol": f"{query.upper()}.NS", "name": query}

    def fetch_quote(self, symbol: str) -> StockQuote:
        """Fetch current stock quote and key valuation metrics."""
        try:
            info = yf.Ticker(symbol).info or {}
        except Exception:
            info = {}
        return StockQuote(
            symbol=symbol,
            name=info.get("longName", symbol),
            current_price=info.get("currentPrice") or info.get("regularMarketPrice", 0),
            previous_close=info.get("regularMarketPreviousClose", 0),
            market_cap=info.get("marketCap", 0),
            pe_ratio=info.get("trailingPE"),
            pb_ratio=info.get("priceToBook"),
            dividend_yield=info.get("dividendYield"),
            fifty_two_week_high=info.get("fiftyTwoWeekHigh", 0),
            fifty_two_week_low=info.get("fiftyTwoWeekLow", 0),
            beta=info.get("beta"),
            enterprise_value=info.get("enterpriseValue"),
            ev_to_ebitda=info.get("enterpriseToEbitda"),
            forward_pe=info.get("forwardPE"),
            peg_ratio=info.get("pegRatio"),
            book_value=info.get("bookValue"),
            business_summary=info.get("longBusinessSummary", ""),
            sector=info.get("sector", ""),
            industry=info.get("industry", ""),
        )

    def fetch_historical(self, symbol: str, period: str = "5y") -> pd.DataFrame:
        """Download OHLCV history from yfinance."""
        df = yf.Ticker(symbol).history(period=period)
        if df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
        return df

    def fetch_financials(self, symbol: str) -> dict:
        """Retrieve annual financial statements from yfinance."""
        ticker = yf.Ticker(symbol)

        def fmt(df):
            if df is None or df.empty:
                return pd.DataFrame()
            df.columns = [
                col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
                for col in df.columns
            ]
            return df.reset_index()

        return {
            "income_statement": fmt(ticker.income_stmt),
            "balance_sheet": fmt(ticker.balance_sheet),
            "cash_flow": fmt(ticker.cashflow),
            "quarterly_balance_sheet": fmt(ticker.quarterly_balance_sheet),
            "quarterly_cash_flow": fmt(ticker.quarterly_cashflow),
            "info": ticker.info,
        }

    def fetch_corporate_actions(self, symbol: str) -> pd.DataFrame:
        """Retrieve dividend and stock split history."""
        df = yf.Ticker(symbol).actions
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
        return df.sort_values(by="Date", ascending=False)
