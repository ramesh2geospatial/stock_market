"""
FastAPI REST Bridge Server for Indian Stock Market Research Platform.
Exposes JSON REST endpoints for cross-platform Flutter (Android / iOS) mobile clients.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from stock_analyzer import StockAnalyzer
from analyzers.prediction_engine import PredictionEngine
from providers.vahan_provider import VahanProvider

app = FastAPI(
    title="Indian Stock Market Research Platform API",
    description="REST backend providing 10-signal stock predictions, concall intelligence, DuPont ROE, and cashflow analytics to Flutter mobile apps.",
    version="1.0.0",
)

# Enable CORS for Flutter mobile / web development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Analyzer and Prediction Engine
analyzer = StockAnalyzer()
prediction_engine = PredictionEngine()
vahan_provider = VahanProvider()


class ConcallAnalysisRequest(BaseModel):
    symbol: str
    max_transcripts: int = 5
    force_refresh: bool = False


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "app": "Indian Stock Market Research API", "version": "1.0.0"}


@app.get("/api/v1/quote/{symbol}")
def get_quote(symbol: str):
    """Fetch real-time quote, valuation metrics, and DuPont breakdown."""
    try:
        quote = analyzer.fetch_quote(symbol)
        financials = analyzer.fetch_financials(symbol)
        cashflow = analyzer.cashflow_analysis(symbol)
        
        annual = getattr(cashflow, "annual_data", []) or []
        latest_p = annual[-1] if annual else None
        
        return {
            "symbol": symbol,
            "quote": quote,
            "financials": financials,
            "cashflow_summary": {
                "cfo_pat_ratio": getattr(latest_p, "cash_conversion_ratio", None) if latest_p else getattr(cashflow, "cfo_pat_ratio", None),
                "altman_z_score": getattr(latest_p, "altman_z_score", None) if latest_p else getattr(cashflow, "altman_z_score", None),
                "dupont_roe": getattr(latest_p, "dupont_roe", None) if latest_p else getattr(cashflow, "dupont_roe", None),
                "cash_quality_score": getattr(cashflow, "cash_quality_score", 0.0),
                "forensic_flags": [d.model_dump() for d in getattr(cashflow, "diagnostics", [])],
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/documents/{symbol}")
def get_documents(symbol: str, force_refresh: bool = False):
    """Fetch multi-source document catalog (transcripts, presentations, financial results)."""
    try:
        docs = analyzer.fetch_documents(symbol, force_refresh=force_refresh)
        return {"symbol": symbol, "documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze/concalls")
def analyze_concalls(req: ConcallAnalysisRequest):
    """Analyze concall transcripts for a ticker using Gemini AI / Lexicon fallback."""
    try:
        results = analyzer.analyze_concalls(
            symbol=req.symbol,
            max_transcripts=req.max_transcripts,
            force_refresh=req.force_refresh,
        )
        return {
            "symbol": req.symbol,
            "transcripts_analyzed": len(results),
            "results": [r.model_dump() for r in results],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/intelligence/{symbol}")
def get_intelligence(symbol: str, max_transcripts: int = 7):
    """Generate cross-quarter synthesis, management promise tracking, and credibility score."""
    try:
        analyses = analyzer.analyze_concalls(symbol, max_transcripts=max_transcripts)
        intel = analyzer.generate_cross_quarter_intelligence(symbol, analyses)
        return {
            "symbol": symbol,
            "intelligence": intel.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/cashflow/{symbol}")
def get_cashflow(symbol: str, force_refresh: bool = False):
    """Deep cashflow statement audit, DuPont ROE, Altman Z-Score, and forensic checks."""
    try:
        res = analyzer.cashflow_analysis(symbol, force_refresh=force_refresh)
        return {
            "symbol": symbol,
            "cashflow_analysis": res.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/prediction/{symbol}")
def get_prediction(symbol: str, force_refresh: bool = False):
    """Institutional 10-Signal Matrix prediction trajectory score and target price bands."""
    try:
        pred = prediction_engine.predict_trajectory(symbol, force_refresh=force_refresh)
        return {
            "symbol": symbol,
            "prediction": pred.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/vahan")
def get_vahan_ev_data():
    """Fetch MoRTH Vahan Electric 2-Wheeler registration data."""
    try:
        df = vahan_provider.fetch_vahan_ev_data()
        records = df.to_dict(orient="records") if not df.empty else []
        return {
            "vahan_ev_registrations": records,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stocks/search")
def search_stocks(q: Optional[str] = Query(default="", alias="q"), tier: Optional[str] = None, limit: int = 30):
    """Search stocks by symbol, company name, or SEBI market cap tier across NSE/BSE index universe."""
    try:
        results = analyzer.search_stocks(query=q, tier=tier, limit=limit)
        return {
            "query": q,
            "tier_filter": tier,
            "total_results": len(results),
            "stocks": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/mf/stock-ownership/{symbol}")
def get_mf_stock_ownership(symbol: str):
    """Fetch mutual fund holdings breakdown, scheme count, and MoM buy/sell diffs for a stock."""
    try:
        data = analyzer.get_stock_mf_ownership(symbol)
        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stocks/market-cap-tier/{tier}")
def get_stocks_by_tier(tier: str):
    """Fetch index stocks belonging to Large Cap, Mid Cap, Small Cap, or Micro Cap tier."""
    try:
        results = analyzer.get_market_cap_tier_stocks(tier)
        return {
            "tier": tier.upper(),
            "total_count": len(results),
            "stocks": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

