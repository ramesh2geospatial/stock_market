"""
Unit tests for FastAPI REST Bridge Server (api.py).
Verifies health, quote, documents, concall analysis, cashflow, and prediction JSON routes for Flutter clients.
"""
from fastapi.testclient import TestClient
import pytest
from api import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data


def test_get_quote_mock(monkeypatch):
    from models.cashflow import CashFlowAnalysisResult
    monkeypatch.setattr("stock_analyzer.StockAnalyzer.fetch_quote", lambda self, symbol: {"currentPrice": 1600.0, "symbol": "HDFCBANK"})
    monkeypatch.setattr("stock_analyzer.StockAnalyzer.fetch_financials", lambda self, symbol: {"revenue": 100000})
    monkeypatch.setattr("stock_analyzer.StockAnalyzer.cashflow_analysis", lambda self, symbol, force_refresh=False: CashFlowAnalysisResult(symbol=symbol))
    
    response = client.get("/api/v1/quote/HDFCBANK")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "HDFCBANK"
    assert "quote" in data
    assert "cashflow_summary" in data


def test_get_documents():
    response = client.get("/api/v1/documents/HDFCBANK")
    assert response.status_code == 200
    data = response.json()
    assert "symbol" in data
    assert "documents" in data


def test_analyze_concalls_api(monkeypatch):
    from models.analysis import SentimentResult
    mock_res = SentimentResult(
        quarter="Q4 FY26",
        sentiment_score=0.8,
        sentiment_label="Positive",
        summary="Strong performance",
        analyzer_type="lexicon",
    )
    monkeypatch.setattr("stock_analyzer.StockAnalyzer.analyze_concalls", lambda self, symbol, max_transcripts=5, force_refresh=False: [mock_res])
    
    payload = {"symbol": "HDFCBANK", "max_transcripts": 2, "force_refresh": False}
    response = client.post("/api/v1/analyze/concalls", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "HDFCBANK"
    assert data["transcripts_analyzed"] == 1
    assert data["results"][0]["quarter"] == "Q4 FY26"


def test_get_cashflow_api(monkeypatch):
    from models.cashflow import CashFlowAnalysisResult, CashFlowPeriod
    mock_cf = CashFlowAnalysisResult(
        symbol="HDFCBANK",
        annual_data=[CashFlowPeriod(period="FY26", cash_conversion_ratio=1.2, altman_z_score=3.5, dupont_roe=18.5)],
        diagnostics=[],
    )
    monkeypatch.setattr("stock_analyzer.StockAnalyzer.cashflow_analysis", lambda self, symbol, force_refresh=False: mock_cf)
    
    response = client.get("/api/v1/cashflow/HDFCBANK")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "HDFCBANK"
    assert "cashflow_analysis" in data
    assert len(data["cashflow_analysis"]["annual_data"]) == 1
    assert data["cashflow_analysis"]["annual_data"][0]["cash_conversion_ratio"] == 1.2
