"""
Unit tests for PredictionEngine, DuPont ROE, Z-Score, M-Score, and Kelly Position Sizing.
"""
from analyzers.prediction_engine import PredictionEngine


def test_prediction_engine_du_pont_and_solvency():
    engine = PredictionEngine()

    # 1. Test DuPont ROE
    dupont = engine.calculate_dupont_roe(net_income=120.0, revenue=1000.0, total_assets=1500.0, equity=800.0)
    assert dupont["profit_margin_pct"] == 12.0
    assert dupont["asset_turnover"] == 0.67
    assert dupont["roe_pct"] == 15.0

    # 2. Test Altman Z-Score
    z = engine.calculate_altman_z_score(120.0, 450.0, 380.0, 2500.0, 500.0, 4200.0, 1500.0)
    assert z > 2.99  # Safe zone

    # 3. Test Kelly Position Sizing
    kelly = engine.calculate_kelly_position_size(win_prob=0.75, win_loss_ratio=2.0)
    assert 0.0 < kelly <= 7.5

    # 4. Test Stock Prediction Trajectory
    quant_metrics = {"revenue_growth_yoy": 15.0, "cfo_pat_ratio": 1.1, "ebitda_margin_pct": 14.5}
    concall_intel = {"promise_delivery_rate": 88.0}

    pred = engine.predict_stock_trajectory("TVSMOTOR.NS", current_price=2400.0, quant_metrics=quant_metrics, concall_intelligence=concall_intel)
    assert pred["trajectory_score"] >= 70.0
    assert pred["stance"] in ["Bullish / Strong Outperform", "Neutral / Market Perform"]
    assert pred["scenarios"]["bull_case"]["target_price"] > 2400.0
