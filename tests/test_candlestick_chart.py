"""
Unit tests for TradingView-grade CandlestickChart visualizer.
"""
from datetime import datetime
import pandas as pd
import pytest
from visualizers.candlestick_chart import CandlestickChart


def test_candlestick_chart_empty_dataframe():
    empty_df = pd.DataFrame()
    fig = CandlestickChart.build(empty_df)
    assert fig is not None
    assert len(fig.data) == 0
    assert "No historical data" in fig.layout.annotations[0].text


def test_candlestick_chart_ohlc_with_volume_and_emas():
    now = datetime.now()
    dates = pd.date_range(end=now, periods=60)
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0 + i for i in range(60)],
        "High": [105.0 + i for i in range(60)],
        "Low": [95.0 + i for i in range(60)],
        "Close": [102.0 + i for i in range(60)],
        "Volume": [500000 + i * 10000 for i in range(60)],
    })

    fig = CandlestickChart.build(
        df,
        days=90,
        show_50_ema=True,
        show_200_ema=True,
        show_volume=True,
    )

    assert fig is not None
    # 4 traces: Candlestick (OHLC), 50 EMA, 200 EMA, Volume Bar
    trace_names = [t.name for t in fig.data]
    assert "OHLC" in trace_names
    assert "50 EMA" in trace_names
    assert "200 EMA" in trace_names
    assert "Volume" in trace_names


def test_candlestick_chart_without_volume():
    now = datetime.now()
    dates = pd.date_range(end=now, periods=30)
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0 + i for i in range(30)],
        "High": [105.0 + i for i in range(30)],
        "Low": [95.0 + i for i in range(30)],
        "Close": [102.0 + i for i in range(30)],
        "Volume": [100000 for _ in range(30)],
    })

    fig = CandlestickChart.build(
        df,
        days=30,
        show_50_ema=False,
        show_200_ema=False,
        show_volume=False,
    )

    assert fig is not None
    assert len(fig.data) == 1
    assert fig.data[0].name == "OHLC"
