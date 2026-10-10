"""
Central orchestrator — wires providers, analyzers, storage, and visualizers.
Single entry point for all analysis operations on any Indian stock.
"""
import json
import re
import datetime
from pathlib import Path
from typing import Optional


from config import GEMINI_API_KEY, GEMINI_MODEL, MAX_QUARTERS
from models.stock import QuarterlyResult
from models.analysis import SentimentResult, QuarterSpiderData, MilestoneTrack
from models.cashflow import CashFlowAnalysisResult
from models.intelligence import CrossQuarterIntelligence

from providers.yfinance_provider import YFinanceProvider
from providers.screener_provider import ScreenerProvider
from providers.multi_source_doc_fetcher import MultiSourceDocFetcher
from providers.news_provider import GoogleYFinanceNewsProvider
from providers.vahan_provider import VahanProvider
from providers.local_llm_provider import LocalLLMProvider
from providers.calendar_provider import CalendarProvider
from providers.insider_data_provider import InsiderDataProvider
from providers.pdf_extraction_provider import PDFGroundTruthExtractor
from providers.mf_holdings_provider import MFHoldingsProvider
from models.ground_truth import GroundTruthFinancials


from analyzers.lexicon_analyzer import LexiconAnalyzer
from analyzers.gemini_analyzer import GeminiAnalyzer
from analyzers.financial_scorer import FinancialScorer
from analyzers.decision_analyzer import DecisionAnalyzer
from analyzers.cashflow_analyzer import CashflowAnalyzer
from analyzers.quarterly_cashflow_engine import QuarterlyCashflowEngine
from analyzers.multi_quarter_divergence import MultiQuarterDivergenceAnalyzer
from analyzers.intelligence_engine import IntelligenceEngine
from analyzers.consensus_analyzer import ConsensusAnalyzer
from analyzers.backtest_engine import BacktestEngine
from analyzers.prediction_engine import PredictionEngine
from analyzers.cross_validator import CrossValidator

from services.notifier import NotifierService

from storage.cache import FileCache
from storage.sqlite_store import SQLiteStore
from storage.parquet_store import ParquetStore


class StockAnalyzer:
    """
    One-stop orchestrator for comprehensive Indian stock analysis.
    Usage:
        analyzer = StockAnalyzer(gemini_api_key="...")
        result = analyzer.full_analysis("RELIANCE")
    """

    def __init__(self, gemini_api_key: str = None):
        # Storage (initialized first for providers dependency)
        self.cache = FileCache()
        self.db = SQLiteStore()
        self.parquet = ParquetStore()

        # Providers
        self.quote_provider = YFinanceProvider()
        self.doc_provider = ScreenerProvider()
        self.doc_fetcher = MultiSourceDocFetcher(db_store=self.db, cache=self.cache)
        self.news_provider = GoogleYFinanceNewsProvider()
        self.vahan_provider = VahanProvider()
        self.local_llm = LocalLLMProvider()
        self.calendar_provider = CalendarProvider()
        self.insider_provider = InsiderDataProvider()
        self.pdf_extractor = PDFGroundTruthExtractor(db_store=self.db)
        self.mf_holdings_provider = MFHoldingsProvider(db_path=self.db.db_path)


        # Analyzers
        api_key = gemini_api_key or GEMINI_API_KEY
        if api_key:
            self.sentiment_analyzer = GeminiAnalyzer(api_key)
            self.analyzer_type = "gemini"
        else:
            self.sentiment_analyzer = LexiconAnalyzer()
            self.analyzer_type = "lexicon"

        self.financial_scorer = FinancialScorer()
        self.decision_analyzer = DecisionAnalyzer()
        self.cashflow_analyzer = CashflowAnalyzer()
        self.quarterly_cashflow_engine = QuarterlyCashflowEngine()
        self.multi_quarter_divergence = MultiQuarterDivergenceAnalyzer()
        self.consensus_analyzer = ConsensusAnalyzer()
        self.backtest_engine = BacktestEngine()
        self.prediction_engine = PredictionEngine()
        self.cross_validator = CrossValidator()

        # Services
        self.notifier = NotifierService()

    def set_analyzer(self, analyzer_type: str, api_key: str = None):
        """Switch between 'gemini' and 'lexicon' analyzer at runtime."""
        if analyzer_type == "gemini" and api_key:
            self.sentiment_analyzer = GeminiAnalyzer(api_key)
            self.analyzer_type = "gemini"
        else:
            self.sentiment_analyzer = LexiconAnalyzer()
            self.analyzer_type = "lexicon"

    # -----------------------------------------------------------------
    # Core: Ticker Resolution
    # -----------------------------------------------------------------
    def resolve_ticker(self, query: str) -> dict:
        """Resolve company name → {symbol, name}."""
        cached = self.cache.get("ticker", {"q": query})
        if cached:
            return cached
        result = self.quote_provider.resolve_ticker(query)
        self.cache.set("ticker", {"q": query}, result, ttl=86400)
        return result

    # -----------------------------------------------------------------
    # Core: Stock Quote & Fundamentals
    # -----------------------------------------------------------------
    def fetch_quote(self, symbol: str):
        """Fetch current price and valuation metrics."""
        return self.quote_provider.fetch_quote(symbol)

    def fetch_historical(self, symbol: str, period: str = "5y"):
        """Load historical OHLCV — uses Parquet cache, downloads if missing."""
        if not self.parquet.exists(symbol):
            df = self.quote_provider.fetch_historical(symbol, period)
            if not df.empty:
                self.parquet.save(symbol, df)
            return df
        return self.parquet.load(symbol)

    def fetch_financials(self, symbol: str) -> dict:
        """Fetch annual financial statements."""
        return self.quote_provider.fetch_financials(symbol)

    def fetch_corporate_actions(self, symbol: str):
        """Fetch dividend/split history."""
        return self.quote_provider.fetch_corporate_actions(symbol)

    # -----------------------------------------------------------------
    # Core: Documents
    # -----------------------------------------------------------------
    @staticmethod
    def _clean_symbol(symbol: str) -> str:
        s = symbol.strip().upper()
        if s.endswith(".NS") or s.endswith(".BO"):
            return s[:-3]
        return s

    def fetch_documents(self, symbol: str, force_refresh: bool = False) -> dict:
        """
        Fetch all document links categorized by type using MultiSourceDocFetcher.
        Also extracts and caches Ground-Truth financial metrics from presentations & financial result PDFs.
        Returns: {transcripts: [...], presentations: [...], financial_results: [...], credit_ratings: [...], annual_reports: [...]}
        """
        symbol = self._clean_symbol(symbol)
        cached = self.cache.get("documents", {"symbol": symbol}) if not force_refresh else None
        if cached:
            # Auto-migration: if transcripts do not have date_hint, invalidate and refetch
            has_old_format = any(t.get("date_hint") is None for t in cached.get("transcripts", []))
            if not has_old_format:
                result = cached
            else:
                self.cache.invalidate("documents", {"symbol": symbol})
                result = self.doc_fetcher.fetch_quarterly_documents(symbol, force_refresh=True)
                self.cache.set("documents", {"symbol": symbol}, result)
        else:
            result = self.doc_fetcher.fetch_quarterly_documents(symbol, force_refresh=force_refresh)
            self.cache.set("documents", {"symbol": symbol}, result)

        # Connect PDFGroundTruthExtractor for presentation and financial result PDFs
        self.extract_ground_truth_from_documents(symbol, result)

        return result

    def extract_ground_truth_from_documents(
        self, symbol: str, docs: dict, force_refresh: bool = False
    ) -> list[GroundTruthFinancials]:
        """
        Extract ground-truth financial metrics from fetched presentation and financial result PDFs.
        Saves results into SQLite store.
        """
        extracted = []
        if not docs:
            return extracted

        categories = [
            ("presentations", "presentation"),
            ("financial_results", "financial_results"),
        ]

        for cat_key, doc_type in categories:
            doc_list = docs.get(cat_key, [])
            for item in doc_list:
                url = item.get("url") or item.get("source_url") or ""
                local_path = item.get("local_path") or ""
                quarter = item.get("quarter") or item.get("date_hint") or "Unknown"

                pdf_input = local_path if (local_path and Path(local_path).exists()) else url
                if not pdf_input:
                    continue

                if not force_refresh:
                    existing = self.db.get_ground_truth(symbol, quarter, doc_type)
                    if existing:
                        extracted.append(existing)
                        continue

                gt = self.pdf_extractor.extract_from_pdf(
                    pdf_input=pdf_input,
                    symbol=symbol,
                    quarter=quarter,
                    doc_type=doc_type,
                    source_pdf_url=url,
                    source_local_path=local_path,
                )
                if gt:
                    extracted.append(gt)

        return extracted


    def fetch_quarterly_results_df(self, symbol: str):
        """Fetch raw quarterly results table as DataFrame for display."""
        return self.doc_provider.fetch_quarterly_results_df(symbol)

    def fetch_quarterly_results(self, symbol: str) -> list[QuarterlyResult]:
        """Fetch structured quarterly results for analysis modules."""
        return self.doc_provider.fetch_quarterly_results(symbol)

    def verify_latest_quarter_freshness(self, symbol: str) -> dict:
        """
        Verify if the latest available quarter matches current calendar date context.
        Returns freshness status, release recency, and UI badge.
        """
        symbol = self._clean_symbol(symbol)
        quarterly_results = self.fetch_quarterly_results(symbol)
        docs = self.fetch_documents(symbol)
        transcripts = docs.get("transcripts", [])

        current_date = datetime.date.today()
        latest_q_label = "Unknown"

        if quarterly_results:
            latest_q_label = getattr(quarterly_results[-1], "quarter", "Unknown")
        elif transcripts:
            sorted_t = self._sort_transcripts_chronologically(transcripts)
            latest_q_label = sorted_t[-1].get("date_hint") or sorted_t[-1].get("title", "Unknown")

        days_elapsed = 999
        if latest_q_label and latest_q_label != "Unknown":
            q_date = self._parse_quarter_to_date(latest_q_label)
            if q_date:
                days_elapsed = max(0, (current_date - q_date).days)

        is_fresh = True if days_elapsed <= 150 else False

        if days_elapsed <= 100:
            badge = f"🟢 Fresh Data ({latest_q_label})"
        elif days_elapsed <= 150:
            badge = f"🟡 Recent Data ({latest_q_label})"
        else:
            badge = f"🔴 Stale Data ({latest_q_label})"

        return {
            "symbol": symbol,
            "latest_quarter": latest_q_label,
            "current_date": current_date.strftime("%Y-%m-%d"),
            "days_elapsed": days_elapsed,
            "is_fresh": is_fresh,
            "badge": badge
        }

    def analyze_quarterly_cashflow_trajectory(self, symbol: str, num_quarters: int = 5, sector: str = "") -> dict:
        """Analyze quarterly cash flow trajectory across N quarters (default 5)."""
        symbol = self._clean_symbol(symbol)
        results = self.fetch_quarterly_results(symbol)
        return self.quarterly_cashflow_engine.analyze_quarterly_cashflow(results, num_quarters=num_quarters, sector=sector)

    def analyze_quarterly_divergence(self, symbol: str, num_quarters: int = 5) -> dict:
        """Analyze QoQ and YoY financial divergence matrices across N quarters (default 5)."""
        symbol = self._clean_symbol(symbol)
        results = self.fetch_quarterly_results(symbol)
        return self.multi_quarter_divergence.compute_divergence(results, num_quarters=num_quarters)

    # -----------------------------------------------------------------
    # Core: News
    # -----------------------------------------------------------------
    def fetch_news(self, symbol: str, company_name: str) -> list[dict]:
        """Fetch aggregated news with sentiment scoring."""
        items = self.news_provider.fetch_news(symbol, company_name)
        # Add sentiment to each news item
        for item in items:
            s = self.sentiment_analyzer.analyze_text(item.get("title", ""))
            item["sentiment_score"] = s.sentiment_score
            item["sentiment_label"] = s.sentiment_label
        return items

    # -----------------------------------------------------------------
    # Deep Analysis: 10-Quarter Concall Analysis
    # -----------------------------------------------------------------
    def analyze_concalls(
        self, symbol: str, max_transcripts: int = MAX_QUARTERS,
        force_refresh: bool = False,
    ) -> list[SentimentResult]:
        """
        Download and analyze up to N concall transcripts.
        Supports incremental re-analysis: only downloads/analyzes uncached transcripts.
        Cross-validates Gemini output against Screener quarterly results.
        Overlays Screener data for lexicon fallback enrichment.
        """
        # --- Fetch transcript links ---
        symbol = self._clean_symbol(symbol)
        docs = self.fetch_documents(symbol, force_refresh=force_refresh)
        all_transcripts = docs.get("transcripts", [])

        if not all_transcripts:
            # Fallback to DB if network/screener is unavailable
            cached = self.db.get_all_analyses(symbol, self.analyzer_type)
            if cached:
                valid_fields = set(SentimentResult.model_fields.keys())
                results = [
                    SentimentResult(**{k: v for k, v in c.items() if k in valid_fields})
                    for c in cached
                ]
                sorted_cached = sorted(results, key=lambda a: self._parse_quarter_to_date(a.quarter))
                return sorted_cached[-max_transcripts:] if max_transcripts else sorted_cached
            return []

        # Sort ALL transcripts chronologically (oldest first)
        sorted_transcripts = self._sort_transcripts_chronologically(all_transcripts)

        # Select the latest N transcripts (so max_transcripts=5 fetches the 5 most recent quarters up to Q1 FY26)
        transcripts = sorted_transcripts[-max_transcripts:] if max_transcripts else sorted_transcripts

        # Pre-fetch quarterly results for cross-validation & lexicon enrichment
        quarterly_results = self.fetch_quarterly_results(symbol)

        # --- Incremental analysis: check per-URL cache ---
        results = []
        newly_analyzed = 0
        prior_guidance = None
        prior_targets = None

        for idx, t in enumerate(transcripts):
            url = t["url"]
            title = t.get("title", f"Transcript {idx + 1}")
            quarter_source = t.get("date_hint") or self._extract_quarter(title, idx)
            quarter_label, transcript_date = self.resolve_quarter_and_date(quarter_source)
            if not quarter_label:
                quarter_label = self._extract_quarter(title, idx)

            # Check if this specific transcript URL is already cached
            if not force_refresh:
                cached_analysis = self.db.get_analysis_by_url(symbol, url, self.analyzer_type)
                if cached_analysis:
                    valid_fields = set(SentimentResult.model_fields.keys())
                    hydrated = {k: v for k, v in cached_analysis.items() if k in valid_fields}
                    result = SentimentResult(**hydrated)
                    results.append(result)
                    # Update prior guidance chain from cached result
                    prior_guidance = result.guidance_numbers if result.guidance_numbers else None
                    prior_targets = result.future_targets if result.future_targets else None
                    continue

            safe_title = title.encode('ascii', errors='replace').decode('ascii')
            print(f"  [{idx + 1}/{len(transcripts)}] Analyzing: {safe_title}")

            # Download and extract text
            text = self.doc_provider.download_transcript_text(url)
            if not text or len(text.strip()) < 100:
                print(f"    [Skipped] Insufficient text")
                continue

            # Run analysis — pass prior quarter's guidance for promise tracking
            analysis = self.sentiment_analyzer.analyze_concall(
                text, quarter_label,
                prior_guidance=prior_guidance,
                prior_targets=prior_targets,
            )
            analysis.transcript_url = url
            analysis.quarter = quarter_label
            analysis.transcript_date = transcript_date

            # Add prior_quarter reference to promise assessment entries
            if prior_guidance or prior_targets:
                prior_q = results[-1].quarter if results else "Prior Quarter"
                for entry in analysis.prior_guidance_met:
                    entry["prior_quarter"] = prior_q
                for entry in analysis.prior_guidance_missed:
                    entry["prior_quarter"] = prior_q

            # Cross-validate Gemini output against Screener data
            if analysis.analyzer_type == "gemini" and quarterly_results:
                analysis = self.cross_validator.validate_and_correct(
                    analysis, quarterly_results
                )

            # Enrich lexicon fallback with Screener data overlay
            if analysis.analyzer_type in ("lexicon", "lexicon_enhanced") and quarterly_results:
                analysis = self._overlay_screener_data(analysis, quarterly_results)

            results.append(analysis)
            newly_analyzed += 1

            # Store this quarter's guidance as context for next quarter
            prior_guidance = analysis.guidance_numbers if analysis.guidance_numbers else None
            prior_targets = analysis.future_targets if analysis.future_targets else None

            # Cache in SQLite
            self.db.save_analysis(
                symbol=symbol,
                quarter=quarter_label,
                transcript_url=url,
                sentiment_dict=analysis.model_dump(),
                analyzer_type=self.analyzer_type,
            )

        if newly_analyzed > 0:
            print(f"  [Incremental] Analyzed {newly_analyzed} new transcripts, "
                  f"{len(results) - newly_analyzed} from cache")

        return sorted(results, key=lambda a: self._parse_quarter_to_date(a.quarter))

    # -----------------------------------------------------------------
    # Spider Diagram: 10-Quarter Financial Scoring
    # -----------------------------------------------------------------
    def spider_analysis(self, symbol: str) -> list[QuarterSpiderData]:
        """
        Compute spider chart data from quarterly financials.
        Returns list of QuarterSpiderData (oldest first).
        """
        quarters = self.fetch_quarterly_results(symbol)
        if not quarters:
            return []
        return self.financial_scorer.compute_spider_data(quarters)

    def decision_snapshot(self, info: dict, hist_df=None, quarters=None) -> dict:
        """Build valuation, risk, and thesis snapshots from available data."""
        return self.decision_analyzer.build_research_snapshot(info, hist_df, quarters or [])

    # -----------------------------------------------------------------
    # Cashflow Analysis
    # -----------------------------------------------------------------
    def cashflow_analysis(
        self, symbol: str, force_refresh: bool = False
    ) -> CashFlowAnalysisResult:
        """
        Comprehensive cashflow analysis: CFO vs PAT, working capital,
        receivables/payables, credit-sales detection, FCF, diagnostics.
        Scrapes Screener.in for cash flow statement + balance sheet,
        combines with quarterly P&L and yfinance, caches in SQLite.
        """
        # Check cache
        if not force_refresh:
            cached = self.db.get_cashflow(symbol)
            if cached:
                return CashFlowAnalysisResult(**cached)

        # Fetch data from Screener
        print(f"[CashFlow] Fetching cash flow statement for {symbol}...")
        cashflow_df = self.doc_provider.fetch_cashflow_df(symbol)

        print(f"[CashFlow] Fetching balance sheet for {symbol}...")
        balance_sheet_df = self.doc_provider.fetch_balance_sheet_df(symbol)

        print(f"[CashFlow] Fetching profit & loss for {symbol}...")
        profit_loss_df = self.doc_provider.fetch_profit_loss_df(symbol)

        # Get quarterly P&L for revenue/profit context
        quarterly_results = self.fetch_quarterly_results(symbol)

        # Get yfinance financials for cross-validation & quarterly balance sheet items
        print(f"[CashFlow] Fetching yfinance financials for {symbol}...")
        try:
            yf_financials = self.fetch_financials(symbol)
        except Exception as e:
            print(f"[CashFlow] yfinance fetch failed: {e}")
            yf_financials = None

        # Run analysis
        result = self.cashflow_analyzer.analyze(
            cashflow_df=cashflow_df,
            balance_sheet_df=balance_sheet_df,
            profit_loss_df=profit_loss_df,
            quarterly_results=quarterly_results,
            symbol=symbol,
            yf_financials=yf_financials,
        )

        # Cache in SQLite
        self.db.save_cashflow(symbol, result.model_dump())

        return result

    # -----------------------------------------------------------------
    # Milestone Tracking
    # -----------------------------------------------------------------
    def extract_milestones(self, analyses: list[SentimentResult]) -> list[dict]:
        """
        Extract and deduplicate milestones from concall analyses.
        Groups similar milestones across quarters to track evolution.
        """
        all_milestones = []

        for a in analyses:
            for m in a.milestones_achieved:
                all_milestones.append({
                    "text": m,
                    "quarter": a.quarter,
                    "type": "Milestone Achieved",
                })
            for c in a.concerns:
                all_milestones.append({
                    "text": c,
                    "quarter": a.quarter,
                    "type": "Concern",
                })
            for t in a.future_targets:
                all_milestones.append({
                    "text": t,
                    "quarter": a.quarter,
                    "type": "Future Target",
                })

        return all_milestones

    def track_milestone_evolution(
        self, symbol: str, analyses: list[SentimentResult],
        force_refresh: bool = False,
    ) -> list[MilestoneTrack]:
        """
        Group and trace the quarter-by-quarter evolution of milestones, concerns, and targets.
        Saves results to sqlite_store and returns list of MilestoneTrack objects.
        """
        if not analyses:
            return []

        # 1. Check cache first
        if not force_refresh:
            cached = self.db.get_milestones(symbol)
            if cached:
                return [MilestoneTrack(**m) for m in cached]

        # 2. Extract raw items from analyses
        raw_items = []
        for a in analyses:
            display_quarter = self._format_quarter_date(a.quarter, a.transcript_date)
            for m in a.milestones_achieved:
                raw_items.append({
                    "quarter": a.quarter,
                    "display_quarter": display_quarter,
                    "transcript_date": a.transcript_date,
                    "text": m,
                    "type": "Milestone Achieved",
                })
            for c in a.concerns:
                raw_items.append({
                    "quarter": a.quarter,
                    "display_quarter": display_quarter,
                    "transcript_date": a.transcript_date,
                    "text": c,
                    "type": "Concern",
                })
            for t in a.future_targets:
                raw_items.append({
                    "quarter": a.quarter,
                    "display_quarter": display_quarter,
                    "transcript_date": a.transcript_date,
                    "text": t,
                    "type": "Future Target",
                })

        if not raw_items:
            return []

        # 3. If using Gemini and key is present, let the AI group them semantically
        if self.analyzer_type == "gemini" and self.sentiment_analyzer.client:
            try:
                self.sentiment_analyzer._rate_limit()
                
                # Format raw items chronologically for Gemini prompt
                sorted_raw = sorted(raw_items, key=lambda x: self._parse_quarter_to_date(x["quarter"]))
                formatted_items = ""
                for idx, item in enumerate(sorted_raw):
                    formatted_items += f"- [{item['display_quarter']}] ({item['type']}): {item['text']}\n"

                prompt = f"""You are a senior equity research analyst tracking corporate milestones.
Here is a list of management concerns, milestones achieved, and future targets/guidance extracted from earnings call transcripts of company {symbol} across multiple quarters:

{formatted_items}

Your task is to group similar items into a few key 'Business Evolution Tracks' (max 5 tracks). 
Each track represents a major business topic (e.g. "Store Expansion Plan", "Debt Reduction", "Profit Margin Pressures").

For each track, trace its quarter-by-quarter status history. 
For example, a track about "Debt Reduction" might show:
- Q1 FY24: Status="Future Target", Note="Targeting 50 Cr debt reduction"
- Q2 FY24: Status="In Progress", Note="Debt reduced by 20 Cr so far"
- Q3 FY24: Status="Resolved", Note="Reduced debt by 50 Cr total"

Status must be one of: "Concern", "In Progress", "Almost Resolved", "Resolved", "Milestone Achieved", "Future Target".

Return a valid JSON list of tracks (no markdown, no code fences, just raw JSON):
[
  {{
    "name": "<name of the track, e.g., Debt Reduction>",
    "status": "<overall current status: Resolved|In Progress|Concern|Future Target>",
    "start_quarter": "<earliest quarter this topic appeared>",
    "current_quarter": "<latest quarter this topic appeared>",
    "description": "<brief 1-2 sentence description summarizing the overall story/progress>",
    "quarterly_updates": [
      {{
        "quarter": "<quarter label>",
        "status": "<status in this quarter>",
        "note": "<brief details/update for this quarter>"
      }}
    ]
  }}
]
"""
                response = self.sentiment_analyzer.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                )
                
                clean = response.text.strip()
                clean = re.sub(r'^```(?:json)?\s*', '', clean)
                clean = re.sub(r'\s*```$', '', clean)
                
                data = json.loads(clean)
                tracks = []
                for t in data:
                    track = MilestoneTrack(
                        name=t.get("name", ""),
                        status=t.get("status", "In Progress"),
                        start_quarter=t.get("start_quarter", ""),
                        current_quarter=t.get("current_quarter", ""),
                        description=t.get("description", ""),
                        quarterly_updates=t.get("quarterly_updates", []),
                    )
                    tracks.append(track)
                    # Cache in DB
                    self.db.save_milestone(symbol, track.model_dump())
                
                if tracks:
                    return tracks
            except Exception as e:
                print(f"[StockAnalyzer] Gemini milestone grouping failed: {e}. Falling back to rule-based.")

        # 4. Fallback: Rule-based grouping
        tracks = self._rule_based_milestone_grouping(raw_items)
        for t in tracks:
            self.db.save_milestone(symbol, t.model_dump())
        return tracks

    def _rule_based_milestone_grouping(self, raw_items: list[dict]) -> list[MilestoneTrack]:
        """Simple rule-based grouping of milestones for fallback/lexicon mode."""
        groups = {
            "Profitability & Margin Management": [],
            "Store Network & Capital Expansion": [],
            "Debt Management & De-leveraging": [],
            "Raw Material Costs & Operating Expenses": [],
            "Strategic Initiatives & Partnerships": [],
        }

        keywords = {
            "Profitability & Margin Management": ["margin", "profit", "opm", "ebitda", "pat", "growth", "revenue", "sales"],
            "Store Network & Capital Expansion": ["store", "expansion", "outlet", "network", "open", "capacity", "capex", "new"],
            "Debt Management & De-leveraging": ["debt", "interest", "leverage", "borrow", "finance", "loan"],
            "Raw Material Costs & Operating Expenses": ["cost", "expense", "inflation", "price", "wage", "rent", "input"],
        }

        for item in raw_items:
            text_lower = item["text"].lower()
            matched = False
            for group_name, keys in keywords.items():
                if any(k in text_lower for k in keys):
                    groups[group_name].append(item)
                    matched = True
                    break
            if not matched:
                groups["Strategic Initiatives & Partnerships"].append(item)

        tracks = []
        for name, items in groups.items():
            if not items:
                continue

            # Sort items chronologically (oldest first) using date parsing
            sorted_items = sorted(items, key=lambda x: self._parse_quarter_to_date(x["quarter"]))
            
            quarter_map = {}
            status_rank = {
                "Concern": 5,
                "Future Target": 4,
                "In Progress": 3,
                "Almost Resolved": 2,
                "Milestone Achieved": 1,  # Issue #7: added missing statuses
                "Resolved": 1,
            }
            for item in sorted_items:
                q = item.get("display_quarter") or item["quarter"]

                status_map = {
                    "Milestone Achieved": "Resolved",
                    "Concern": "Concern",
                    "Future Target": "Future Target",
                }
                status = status_map.get(item["type"], "In Progress")

                if q not in quarter_map:
                    quarter_map[q] = {
                        "quarter": q,
                        "status": status,
                        "notes": [item["text"]],
                    }
                    continue

                quarter_map[q]["notes"].append(item["text"])
                if status_rank.get(status, 0) > status_rank.get(quarter_map[q]["status"], 0):
                    quarter_map[q]["status"] = status

            quarter_updates = sorted(
                [
                    {
                        "quarter": update["quarter"],
                        "status": update["status"],
                        "note": "; ".join(update["notes"]),
                    }
                    for update in quarter_map.values()
                ],
                key=lambda x: self._parse_quarter_to_date(x["quarter"]),  # Issue #8: ensure chronological order
            )

            if not quarter_updates:
                continue

            start_q = quarter_updates[0]["quarter"]
            curr_q = quarter_updates[-1]["quarter"]
            last_status = quarter_updates[-1]["status"]
            description = f"Tracking {name} developments from {start_q} to {curr_q}."

            tracks.append(MilestoneTrack(
                name=name,
                status=last_status,
                start_quarter=start_q,
                current_quarter=curr_q,
                description=description,
                quarterly_updates=quarter_updates,
            ))

        return tracks

    # -----------------------------------------------------------------
    # Watchlist & Notes (delegate to SQLite)
    # -----------------------------------------------------------------
    def add_to_watchlist(self, symbol: str, name: str):
        return self.db.add_to_watchlist(symbol, name)

    def remove_from_watchlist(self, symbol: str):
        return self.db.remove_from_watchlist(symbol)

    def get_watchlist(self):
        return self.db.get_watchlist()

    def add_note(self, symbol: str, note: str):
        return self.db.add_note(symbol, note)

    def get_notes(self, symbol: str):
        return self.db.get_notes(symbol)

    def clear_analysis_cache(self, symbol: str):
        """Force clear cached analyses for a stock."""
        self.db.clear_analyses(symbol)
        self.cache.invalidate("documents", {"symbol": symbol})

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    @staticmethod
    def _format_quarter_date(quarter: str, transcript_date: str = "") -> str:
        """Return a display label such as 'Q4 FY26 (May 2026)'."""
        if transcript_date and transcript_date not in quarter:
            return f"{quarter} ({transcript_date})"
        return quarter

    @classmethod
    def resolve_quarter_and_date(cls, quarter_str: str) -> tuple[str, str]:
        """
        Normalize Screener transcript dates to reporting quarters.
        Examples:
            May 2026 -> Q4 FY26, May 2026
            28 May 2026 -> Q4 FY26, May 2026
            Q4 FY26 -> Q4 FY26, ""
        """
        raw = (quarter_str or "").strip()
        if not raw:
            return "", ""

        raw = re.sub(r"\s+", " ", raw)
        paren_date = ""
        paren_match = re.search(r"\(([^)]+)\)", raw)
        if paren_match:
            paren_date = paren_match.group(1).strip()

        q_match = re.search(r"\bQ([1-4])\s*FY\s*(\d{2,4})\b", raw, re.I)
        if q_match:
            q = int(q_match.group(1))
            fy = int(q_match.group(2))
            if fy < 100:
                fy += 2000
            transcript_dt = cls._parse_text_date(paren_date)
            transcript_label = transcript_dt.strftime("%b %Y") if transcript_dt else ""
            return f"Q{q} FY{fy % 100:02d}", transcript_label

        transcript_dt = cls._parse_text_date(raw)
        if not transcript_dt:
            return raw, ""

        month = transcript_dt.month
        year = transcript_dt.year
        if month in (1, 2):
            quarter, fy, tag = 3, year, ""
        elif month == 3:
            quarter, fy, tag = 4, year, " (Mar)"
        elif month in (4, 5):
            quarter, fy, tag = 4, year, ""
        elif month == 6:
            quarter, fy, tag = 1, year + 1, " (Jun)"
        elif month in (7, 8):
            quarter, fy, tag = 1, year + 1, ""
        elif month == 9:
            quarter, fy, tag = 2, year + 1, " (Sep)"
        elif month in (10, 11):
            quarter, fy, tag = 2, year + 1, ""
        else:  # month == 12
            quarter, fy, tag = 3, year + 1, " (Dec)"

        return f"Q{quarter} FY{fy % 100:02d}{tag}", transcript_dt.strftime("%b %Y")

    @staticmethod
    def _parse_text_date(date_str: str):
        """Parse common Screener transcript date labels into a date."""
        text = (date_str or "").strip()
        if not text:
            return None

        text = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", text, flags=re.I)
        text = text.replace(",", " ")
        text = re.sub(r"\s+", " ", text).strip()

        for fmt in ("%d %b %Y", "%d %B %Y", "%b %Y", "%B %Y", "%Y-%m-%d"):
            try:
                parsed = datetime.datetime.strptime(text, fmt).date()
                return parsed.replace(day=1)
            except ValueError:
                continue

        return None

    @staticmethod
    def _extract_quarter(title: str, fallback_idx: int) -> str:
        """Try to extract a quarter label from a transcript title."""
        # Match patterns like "Q1 FY24", "Q3 FY2024", "Mar 2024", "Jun 2024"
        patterns = [
            r"(Q[1-4]\s*FY\s*\d{2,4})",
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{4})",
            r"(FY\s*\d{2,4})",
        ]
        for pat in patterns:
            m = re.search(pat, title, re.I)
            if m:
                return m.group(1).strip()
        return f"Transcript {fallback_idx + 1}"

    @staticmethod
    def _parse_quarter_to_date(quarter_str: str):
        """Parse various quarter labels (e.g. 'May 2026', 'Q1 FY24') into sortable date objects."""
        quarter_str = (quarter_str or "").strip()
        if not quarter_str:
            return datetime.date(2000, 1, 1)

        # Prefer the financial quarter if the label is combined:
        # "Q4 FY26 (May 2026)" should sort as Q4 FY26, not May 2026.
        m_fy = re.search(r"Q([1-4])\s*FY\s*(\d{2,4})", quarter_str, re.I)
        if m_fy:
            q = int(m_fy.group(1))
            y = int(m_fy.group(2))
            if y < 100:
                y += 2000
            fy_months = {
                1: (y - 1, 6),
                2: (y - 1, 9),
                3: (y - 1, 12),
                4: (y, 3),
            }
            year, month = fy_months[q]
            return datetime.date(year, month, 1)

        # Try month-year format: e.g. "May 2026"
        text_dt = StockAnalyzer._parse_text_date(quarter_str)
        if text_dt:
            resolved_quarter, _ = StockAnalyzer.resolve_quarter_and_date(quarter_str)
            if resolved_quarter and resolved_quarter != quarter_str:
                return StockAnalyzer._parse_quarter_to_date(resolved_quarter)
            return text_dt

        # Try FY-only format: e.g. "FY24" or "FY2024"
        m_yr = re.search(r"FY\s*(\d{2,4})", quarter_str, re.I)
        if m_yr:
            y = int(m_yr.group(1))
            if y < 100:
                y += 2000
            return datetime.date(y, 3, 1)

        # Fallback to older date
        return datetime.date(2000, 1, 1)

    # -----------------------------------------------------------------
    # Helpers: Transcript Sorting & Data Overlay
    # -----------------------------------------------------------------
    def _sort_transcripts_chronologically(self, transcripts: list[dict]) -> list[dict]:
        """Sort transcript dicts oldest-first using date_hint or title parsing."""
        def _sort_key(t):
            date_hint = t.get("date_hint", "")
            if date_hint:
                quarter, _ = self.resolve_quarter_and_date(date_hint)
                if quarter:
                    return self._parse_quarter_to_date(quarter)
            title = t.get("title", "")
            quarter = self._extract_quarter(title, 0)
            return self._parse_quarter_to_date(quarter)

        try:
            return sorted(transcripts, key=_sort_key)
        except Exception:
            return transcripts  # If sorting fails, preserve original order

    def _overlay_screener_data(
        self, analysis: SentimentResult, quarterly_results: list[QuarterlyResult]
    ) -> SentimentResult:
        """
        Overlay Screener quarterly data onto a lexicon analysis result.
        Fills in revenue_absolute, pat_absolute, ebitda_margin_pct from
        Screener data when Gemini wasn't available.
        """
        matched = self.cross_validator._match_quarter(analysis.quarter, quarterly_results)
        if not matched:
            return analysis

        corrected = analysis.model_copy(deep=True)

        if corrected.revenue_absolute is None and matched.revenue:
            corrected.revenue_absolute = matched.revenue
        if corrected.pat_absolute is None and matched.net_profit:
            corrected.pat_absolute = matched.net_profit
        if corrected.ebitda_margin_pct is None and matched.opm_percent:
            corrected.ebitda_margin_pct = matched.opm_percent
        if corrected.ebitda_absolute is None and matched.operating_profit:
            corrected.ebitda_absolute = matched.operating_profit

        corrected.data_confidence = "medium"
        return corrected

    # -----------------------------------------------------------------
    # Cross-Quarter Intelligence Synthesis
    # -----------------------------------------------------------------
    def generate_cross_quarter_intelligence(
        self,
        symbol: str,
        analyses: list[SentimentResult],
        force_refresh: bool = False,
    ) -> CrossQuarterIntelligence:
        """
        Produce a connected 10-quarter intelligence briefing.
        Uses Gemini to synthesize all per-quarter results into
        a narrative with promise tracking, concern evolution,
        and management credibility scoring.
        """
        # Check cache
        if not force_refresh:
            cached = self.db.get_intelligence(symbol)
            if cached and cached.get("_cached_quarters", 0) >= len(analyses):
                # Remove the internal cache key before parsing
                cached.pop("_cached_quarters", None)
                try:
                    return CrossQuarterIntelligence(**cached)
                except Exception:
                    pass  # Cache corrupted, regenerate

        # Determine which Gemini client to use
        gemini_client = None
        if self.analyzer_type == "gemini" and hasattr(self.sentiment_analyzer, 'client'):
            gemini_client = self.sentiment_analyzer.client

        # Rate limit before synthesis call
        if gemini_client and hasattr(self.sentiment_analyzer, '_rate_limit'):
            self.sentiment_analyzer._rate_limit()

        engine = IntelligenceEngine(
            gemini_client=gemini_client,
            rate_limiter=self.sentiment_analyzer._rate_limit if hasattr(self.sentiment_analyzer, '_rate_limit') else None,  # Issue #5/#20
        )
        result = engine.synthesize(analyses, symbol=symbol)

        # Cache the result
        self.db.save_intelligence(
            symbol=symbol,
            intelligence_dict=result.model_dump(),
            quarters=len(analyses),
        )

        return result

    # -----------------------------------------------------------------
    # AI Prediction Orchestration
    # -----------------------------------------------------------------
    def log_pipeline(self, msg: str):
        """Append a log message to the local pipeline.log file and print to console."""
        import os
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] {msg}"
        try:
            print(formatted)
        except UnicodeEncodeError:
            print(formatted.encode("ascii", errors="backslashreplace").decode("ascii"))

        # Ensure data folder exists
        os.makedirs("data", exist_ok=True)
        try:
            with open("data/pipeline.log", "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
        except Exception:
            pass

    def predict_stock(self, symbol: str, force_refresh: bool = False) -> dict:
        """
        Orchestrate 10-signal trajectory prediction for a single stock.
        Checks SQLite database cache first.
        """
        cleaned_symbol = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
        self.log_pipeline(f"Initiating 10-signal analysis for: {cleaned_symbol}")

        if not force_refresh:
            cached_pred = self.db.get_prediction(cleaned_symbol)
            if cached_pred:
                self.log_pipeline(f"Cache HIT for {cleaned_symbol}. Loaded saved prediction from SQLite.")
                return cached_pred

        # Fetch current price
        price = 150.0  # Safe default if network is offline
        try:
            self.log_pipeline(f"Fetching real-time market price for {cleaned_symbol} via yfinance...")
            quote = self.quote_provider.fetch_quote(symbol)
            if quote and hasattr(quote, 'current_price') and quote.current_price:
                price = float(quote.current_price)
                self.log_pipeline(f"Current price resolved: Rs {price:,.2f}")
        except Exception as e:
            self.log_pipeline(f"Market price fetch failed ({e}). Using default: Rs {price}")

        # Dynamic Financial statement & concall intelligence
        quant_metrics = {}
        concall_intel = {}
        try:
            cf_res = self.cashflow_analysis(cleaned_symbol)
            if cf_res and getattr(cf_res, "annual_data", []):
                latest_p = cf_res.annual_data[-1]
                quant_metrics = {
                    "revenue_growth_yoy": getattr(latest_p, "revenue_growth_pct", 10.0) or 10.0,
                    "cfo_pat_ratio": getattr(latest_p, "cash_conversion_ratio", 1.0) or 1.0,
                    "ebitda_margin_pct": getattr(latest_p, "ebitda_margin_pct", 15.0) or 15.0,
                    "pat_cr": getattr(latest_p, "net_profit", 100.0) or 100.0,
                    "rev_cr": getattr(latest_p, "revenue", 1000.0) or 1000.0
                }
        except Exception as e:
            self.log_pipeline(f"Financials fetch for prediction fallback: {e}")

        try:
            analyses = self.analyze_concalls(cleaned_symbol, max_transcripts=4)
            if analyses:
                intel = self.generate_cross_quarter_intelligence(cleaned_symbol, analyses)
                concall_intel = {
                    "promise_delivery_rate": getattr(intel, "credibility_index", 75.0) or 75.0
                }
        except Exception as e:
            self.log_pipeline(f"Concall intel for prediction fallback: {e}")

        if not quant_metrics:
            quant_metrics = {
                "revenue_growth_yoy": 10.0,
                "cfo_pat_ratio": 1.0,
                "ebitda_margin_pct": 15.0,
                "pat_cr": 100.0,
                "rev_cr": 1000.0
            }
        if not concall_intel:
            concall_intel = {
                "promise_delivery_rate": 75.0
            }

        # Generate trajectory prediction
        self.log_pipeline("Processing 10-Signal Matrix & DuPont ROE solvency checks...")
        prediction = self.prediction_engine.predict_stock_trajectory(
            symbol=cleaned_symbol,
            current_price=price,
            quant_metrics=quant_metrics,
            concall_intelligence=concall_intel
        )
        self.log_pipeline(f"Calculated Score: {prediction['trajectory_score']}/100 | Stance: {prediction['stance']}")
        self.log_pipeline(f"Kelly Criterion Allocation: {prediction['kelly_recommended_allocation_pct']}% portfolio cap")

        # Persist prediction to SQLite
        self.db.save_prediction(
            symbol=cleaned_symbol,
            score=prediction["trajectory_score"],
            stance=prediction["stance"],
            signal_dict=prediction["signal_breakdown"]
        )
        self.log_pipeline("Saved final prediction output to SQLite database cache.")

        # Notify if high-conviction Bullish/Bearish
        if prediction["trajectory_score"] >= 80.0:
            self.log_pipeline(f"High-conviction signal detected! Triggering Telegram notification Bot...")
            self.notifier.notify_high_conviction_signal(
                symbol=cleaned_symbol,
                stance=prediction["stance"],
                score=prediction["trajectory_score"],
                catalyst=prediction.get("scenarios", {}).get("bull_case", {}).get("catalyst", "Strong institutional accumulation and consensus surprise beat.")
            )

        return prediction

    # Backward compatibility alias
    predict_stock_trajectory = predict_stock


    def batch_predict_universe(self, symbol_list: list) -> dict:
        """
        Run batch predictions across a list of symbols with resumable state checkpoints.
        """
        pipeline_name = "nse_500_prediction_pipeline"
        self.log_pipeline(f"Starting batch prediction pipeline for {len(symbol_list)} tickers.")
        
        checkpoint = self.db.get_checkpoint(pipeline_name)
        completed_symbols = []

        if checkpoint:
            completed_symbols = checkpoint.get("completed_symbols", [])
            last_symbol = checkpoint.get("last_processed_symbol")
            stage = checkpoint.get("current_stage", 1)
            self.log_pipeline(f"Pipeline checkpoint found. Resuming stage {stage} from {last_symbol}. Total completed: {len(completed_symbols)}")

        # Filter symbols that are already completed
        pending_symbols = [s for s in symbol_list if s.replace(".NS", "").replace(".BO", "").strip().upper() not in completed_symbols]
        self.log_pipeline(f"Pending tickers to process: {len(pending_symbols)}")

        for i, sym in enumerate(pending_symbols):
            cleaned = sym.replace(".NS", "").replace(".BO", "").strip().upper()
            try:
                self.predict_stock(sym)
                completed_symbols.append(cleaned)

                # Save checkpoint every 10 tickers
                if len(completed_symbols) % 10 == 0 or i == len(pending_symbols) - 1:
                    self.db.save_checkpoint(
                        pipeline_name=pipeline_name,
                        current_stage=1,
                        stage_name="prediction_scoring",
                        last_processed_symbol=cleaned,
                        completed_symbols_list=completed_symbols
                    )
                    self.log_pipeline(f"Saved pipeline state checkpoint. Processed: {len(completed_symbols)} tickers.")
            except Exception as e:
                self.log_pipeline(f"ERROR: Failed prediction for {sym}: {e}")

        self.log_pipeline("Batch prediction pipeline run completed.")
        return {
            "status": "Completed" if len(pending_symbols) == 0 else "Paused/Checkpoint Saved",
            "total_processed": len(completed_symbols),
            "pending_count": len(symbol_list) - len(completed_symbols)
        }

    # Mutual Fund Holdings & Stock Search API
    def search_stocks(self, query: str = "", tier: Optional[str] = None, limit: int = 30):
        """Search stocks across NSE/BSE index universe with MF ownership stats."""
        return self.mf_holdings_provider.search_stocks(query=query, tier=tier, limit=limit)

    def get_stock_mf_ownership(self, symbol: str):
        """Fetch scheme breakdown and MoM buy/sell diffs for a stock."""
        return self.mf_holdings_provider.get_stock_mf_ownership(symbol)

    def get_market_cap_tier_stocks(self, tier: str):
        """Fetch index stocks categorized by SEBI market cap tier."""
        return self.mf_holdings_provider.get_market_cap_tier_stocks(tier)

