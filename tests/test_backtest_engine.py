"""
Unit tests for BacktestEngine.
"""
from analyzers.backtest_engine import BacktestEngine


def test_backtest_engine_run():
    engine = BacktestEngine()
    res = engine.run_4q_backtest("TVSMOTOR.NS")
    
    assert res["symbol"] == "TVSMOTOR.NS"
    assert res["backtest_quarters"] == 4
    assert res["hit_rate_pct"] >= 75.0
    assert len(res["quarterly_breakdown"]) == 4
