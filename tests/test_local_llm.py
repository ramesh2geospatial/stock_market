"""
Unit tests for LocalLLMProvider.
"""
from providers.local_llm_provider import LocalLLMProvider


def test_local_llm_evaluation_fallback():
    provider = LocalLLMProvider(ollama_url="http://localhost:11434")
    
    # Construct sample fusion payload
    payload = {
        "quantitative_base": {
            "rev_growth_yoy": 18.5,
            "cfo_pat_ratio": 1.25
        },
        "governance_audit": {
            "promoter_pledging": 0.0
        }
    }
    
    res = provider.evaluate_stock_stance(payload)
    assert "trajectory_score" in res
    assert "stance" in res
    assert res["trajectory_score"] > 50.0
    assert "Bullish" in res["stance"]
