"""
Parquet-based historical price storage with DuckDB query engine.
"""
import os
import pandas as pd
import duckdb

from config import HISTORICAL_DIR


class ParquetStore:
    """Read/write historical OHLC data as compressed Parquet files, queried via DuckDB."""

    def __init__(self, data_dir=HISTORICAL_DIR):
        self.data_dir = str(data_dir)
        os.makedirs(self.data_dir, exist_ok=True)

    def _path(self, symbol: str) -> str:
        return os.path.join(self.data_dir, f"{symbol}.parquet")

    def exists(self, symbol: str) -> bool:
        return os.path.exists(self._path(symbol))

    def save(self, symbol: str, df: pd.DataFrame):
        """Save a DataFrame as a compressed Parquet file."""
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index() if "Date" not in df.columns else df
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)

        df.to_parquet(self._path(symbol), index=False)

    def load(self, symbol: str) -> pd.DataFrame:
        """Load historical data using DuckDB for fast analytical queries."""
        path = self._path(symbol)
        if not os.path.exists(path):
            return pd.DataFrame()

        query = f"SELECT * FROM '{path}' ORDER BY Date ASC"
        return duckdb.query(query).to_df()

    def delete(self, symbol: str):
        """Remove a cached parquet file."""
        path = self._path(symbol)
        if os.path.exists(path):
            os.remove(path)
