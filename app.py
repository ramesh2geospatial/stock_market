"""
Indian Stock Market Research Platform — Streamlit Dashboard
7-tab interactive dashboard with spider diagrams, AI concall analysis, and milestone tracking.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from stock_analyzer import StockAnalyzer
from visualizers.spider_chart import SpiderChart
from visualizers.milestone_chart import MilestoneChart
from visualizers.candlestick_chart import CandlestickChart
from visualizers.cashflow_chart import CashflowChart
from views.mf_holdings_tab import render_mf_holdings_tab

# ──────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Indian Stock Market Researcher",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# Premium CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp {
        background-color: #0e1117;
        color: #e2e8f0;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    section[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    h1, h2, h3 { color: #f0f6fc !important; font-weight: 700 !important; }
    div[data-testid="stMetricValue"] {
        font-size: 24px !important; font-weight: 700 !important; color: #58a6ff !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 14px !important; color: #8b949e !important;
    }
    button[data-baseweb="tab"] {
        font-size: 15px !important; font-weight: 600 !important; color: #8b949e !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #58a6ff !important; border-bottom-color: #58a6ff !important;
    }
    .premium-card {
        background: rgba(22, 27, 34, 0.6); border: 1px solid #30363d;
        border-radius: 8px; padding: 20px; margin-bottom: 15px;
    }
    .spider-header {
        background: linear-gradient(135deg, rgba(88,166,255,0.08), rgba(57,211,83,0.08));
        border: 1px solid #30363d; border-radius: 10px; padding: 18px 24px; margin-bottom: 18px;
    }
    .milestone-card {
        background: rgba(22, 27, 34, 0.7); border-left: 3px solid;
        border-radius: 0 8px 8px 0; padding: 14px 18px; margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Initialize Analyzer (singleton in session state)
# ──────────────────────────────────────────────
if "analyzer" not in st.session_state:
    st.session_state.analyzer = StockAnalyzer()
elif not hasattr(st.session_state.analyzer, "vahan_provider") or not hasattr(st.session_state.analyzer.vahan_provider, "get_daily_sales_df"):
    st.session_state.analyzer = StockAnalyzer()
if "current_ticker" not in st.session_state:
    st.session_state.current_ticker = "RELIANCE.NS"
if "current_name" not in st.session_state:
    st.session_state.current_name = "Reliance Industries Limited"

analyzer: StockAnalyzer = st.session_state.analyzer

# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────
st.sidebar.header("🔍 Stock Search")
search_query = st.sidebar.text_input(
    "Company Name or Ticker:", value="Reliance", key="search_input"
)

if st.sidebar.button("🔎 Analyze Stock", width="stretch"):
    with st.spinner("Resolving ticker..."):
        res = analyzer.resolve_ticker(search_query)
        st.session_state.current_ticker = res["symbol"]
        st.session_state.current_name = res["name"]

ticker_symbol = st.session_state.current_ticker
company_name = st.session_state.current_name

st.sidebar.markdown(f"**Analyzing:** `{ticker_symbol}`")
st.sidebar.markdown(f"**Company:** {company_name}")

# --- Gemini API Key ---
st.sidebar.markdown("---")
st.sidebar.subheader("🧠 AI Settings")

# Auto-load from .env / config if available
from config import GEMINI_API_KEY
_default_key = GEMINI_API_KEY or ""

gemini_key = st.sidebar.text_input(
    "Gemini API Key:", type="password", key="gemini_key",
    value=_default_key,
    help="Get free key from aistudio.google.com — auto-loaded from .env if present"
)
if gemini_key:
    analyzer.set_analyzer("gemini", gemini_key)
    st.sidebar.success("✅ Gemini AI active")
else:
    analyzer.set_analyzer("lexicon")
    st.sidebar.info("📝 Using lexicon analyzer (no API key)")

# --- Watchlist ---
st.sidebar.markdown("---")
st.sidebar.subheader("⭐ Watchlist")
watchlist_df = analyzer.get_watchlist()
in_watchlist = ticker_symbol in watchlist_df["symbol"].values if not watchlist_df.empty else False

if in_watchlist:
    if st.sidebar.button("Remove from Watchlist", width="stretch"):
        analyzer.remove_from_watchlist(ticker_symbol)
        st.toast("Removed from Watchlist")
        st.rerun()
else:
    if st.sidebar.button("➕ Add to Watchlist", width="stretch"):
        analyzer.add_to_watchlist(ticker_symbol, company_name)
        st.toast("Added to Watchlist")
        st.rerun()

if not watchlist_df.empty:
    for _, row in watchlist_df.iterrows():
        label = f"📌 {row['symbol']} — {row['company_name'][:22]}"
        if st.sidebar.button(label, key=f"wl_{row['symbol']}", width="stretch"):
            st.session_state.current_ticker = row["symbol"]
            st.session_state.current_name = row["company_name"]
            st.rerun()
else:
    st.sidebar.caption("Watchlist is empty")

# --- Cache controls ---
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Clear Cache & Re-analyze", width="stretch"):
    analyzer.clear_analysis_cache(ticker_symbol)
    st.cache_data.clear()
    st.toast("Cache cleared!")
    st.rerun()

# ──────────────────────────────────────────────
# Title
# ──────────────────────────────────────────────
st.title("📈 Indian Stock Market Research Platform")
st.markdown("---")

# ──────────────────────────────────────────────
# Data Loading (cached)
# ──────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Loading stock data...")
def load_stock_data(_analyzer, ticker):
    try:
        hist = _analyzer.fetch_historical(ticker)
        financials = _analyzer.fetch_financials(ticker)
        actions = _analyzer.fetch_corporate_actions(ticker)
        return hist, financials, actions, None
    except Exception as e:
        return None, None, None, str(e)

hist_df, financials_data, actions_df, error_msg = load_stock_data(analyzer, ticker_symbol)

if error_msg:
    st.error(f"Error fetching data for {ticker_symbol}: {error_msg}")
    st.stop()

info = financials_data["info"]

@st.cache_data(ttl=3600, show_spinner="Loading quarterly analysis data...")
def load_quarterly_results(_analyzer, ticker):
    try:
        return _analyzer.fetch_quarterly_results(ticker)
    except Exception:
        return []

# ──────────────────────────────────────────────
# Top Metrics Bar
# ──────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

current_price = info.get("currentPrice") or info.get("regularMarketPrice") or (
    hist_df["Close"].iloc[-1] if hist_df is not None and not hist_df.empty else 0.0
)
prev_close = info.get("regularMarketPreviousClose") or (
    hist_df["Close"].iloc[-2] if hist_df is not None and len(hist_df) > 1 else current_price
)
change = current_price - prev_close
change_pct = (change / prev_close) * 100 if prev_close else 0.0

col1.metric("Current Price", f"₹{current_price:,.2f}", delta=f"₹{change:,.2f} ({change_pct:+.2f}%)")
col2.metric("Market Cap", f"₹{info.get('marketCap', 0)/1e7:,.0f} Cr" if info.get("marketCap") else "N/A")
col3.metric("P/E Ratio", f"{info.get('trailingPE', 0):.2f}" if info.get("trailingPE") else "N/A")
col4.metric("P/B Ratio", f"{info.get('priceToBook', 0):.2f}" if info.get("priceToBook") else "N/A")
col5.metric("Div Yield", f"{info.get('dividendYield', 0)*100:.2f}%" if info.get("dividendYield") else "N/A")

# ──────────────────────────────────────────────
# 12 Tabs
# ──────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12 = st.tabs([
    "📊 Overview & Chart",
    "📑 Financials",
    "📢 Filings & Docs",
    "📰 News",
    "🕷️ Spider Evolution",
    "📊 Milestone Tracker",
    "🧭 Valuation & Thesis",
    "💰 Cashflow Analysis",
    "📝 Notes",
    "🛵 Vahan EV Sales",
    "🔮 AI Predictor & Screener",
    "🏛️ MF Stock Search & Holdings",
])

# ═══════════════════════════════════════════════
# TAB 1: OVERVIEW & CHART
# ═══════════════════════════════════════════════
with tab1:
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Interactive Price History")
        period_choice = st.radio(
            "Chart Period:", ["1M", "6M", "1Y", "5Y"],
            horizontal=True, index=2,
        )
        chart_days = {"1M": 30, "6M": 180, "1Y": 365, "5Y": 1825}

        ov_c1, ov_c2, ov_c3 = st.columns(3)
        show_50 = ov_c1.checkbox("50-Day EMA", value=False)
        show_200 = ov_c2.checkbox("200-Day EMA", value=False)
        show_vol = ov_c3.checkbox("Volume Panel", value=True)

        fig = CandlestickChart.build(
            hist_df, days=chart_days[period_choice],
            show_50_ema=show_50, show_200_ema=show_200,
            show_volume=show_vol,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Business Summary")
        st.write(info.get("longBusinessSummary", "No summary available."))
        st.markdown("---")
        st.subheader("Key Metrics")
        metrics_table = {
            "Metric": [
                "52W High", "52W Low", "Beta", "Enterprise Value",
                "EV/EBITDA", "Forward P/E", "PEG Ratio", "Book Value",
            ],
            "Value": [
                f"₹{info.get('fiftyTwoWeekHigh', 0):,.2f}",
                f"₹{info.get('fiftyTwoWeekLow', 0):,.2f}",
                f"{info.get('beta', 0):.2f}",
                f"₹{info.get('enterpriseValue', 0)/1e7:,.0f} Cr" if info.get("enterpriseValue") else "N/A",
                f"{info.get('enterpriseToEbitda', 0):.2f}" if info.get("enterpriseToEbitda") else "N/A",
                f"{info.get('forwardPE', 0):.2f}" if info.get("forwardPE") else "N/A",
                f"{info.get('pegRatio', 0):.2f}" if info.get("pegRatio") else "N/A",
                f"₹{info.get('bookValue', 0):.2f}" if info.get("bookValue") else "N/A",
            ],
        }
        st.table(pd.DataFrame(metrics_table))

# ═══════════════════════════════════════════════
# TAB 2: FINANCIALS
# ═══════════════════════════════════════════════
with tab2:
    st.subheader("Financial Tables (Last 10 Quarters / 4 Years)")

    stmt = st.selectbox("Select Statement:", [
        "Quarterly Results (Screener.in)",
        "Income Statement (Annual)",
        "Balance Sheet (Annual)",
        "Cash Flow (Annual)",
    ])

    if stmt == "Quarterly Results (Screener.in)":
        with st.spinner("Scraping last 10 quarters..."):
            df_show = analyzer.fetch_quarterly_results_df(ticker_symbol)
        suffix = "quarterly"
    else:
        key_map = {
            "Income Statement (Annual)": "income_statement",
            "Balance Sheet (Annual)": "balance_sheet",
            "Cash Flow (Annual)": "cash_flow",
        }
        df_show = financials_data[key_map[stmt]]
        suffix = key_map[stmt]

    if df_show is not None and not df_show.empty:
        st.dataframe(df_show, width="stretch")
        csv = df_show.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download CSV", data=csv,
            file_name=f"{ticker_symbol}_{suffix}.csv", mime="text/csv",
        )
    else:
        st.info("No financial data available for this selection.")

# ═══════════════════════════════════════════════
# TAB 3: FILINGS & DOCUMENTS
# ═══════════════════════════════════════════════
with tab3:
    col_act, col_doc = st.columns([1, 1])

    with col_act:
        st.subheader("Corporate Actions")
        if actions_df is not None and not actions_df.empty:
            st.dataframe(actions_df, width="stretch", height=400)
        else:
            st.info("No corporate actions found.")

    with col_doc:
        st.subheader("Research Documents")
        with st.spinner("Fetching documents..."):
            docs = analyzer.fetch_documents(ticker_symbol)

        has_docs = False
        for label, icon, key in [
            ("Conference Call Transcripts", "🎙️", "transcripts"),
            ("Investor Presentations", "📈", "presentations"),
            ("Credit Ratings", "⚠️", "credit_ratings"),
            ("Annual Reports", "📘", "annual_reports"),
        ]:
            items = docs.get(key, [])
            if items:
                has_docs = True
                st.markdown(f"{icon} **{label}:**")
                for d in items[:8]:
                    st.markdown(f"- [{d['title']}]({d['url']})")

        if not has_docs:
            st.info("No documents found. Verify ticker symbol.")

# ═══════════════════════════════════════════════
# TAB 4: NEWS & SENTIMENT
# ═══════════════════════════════════════════════
with tab4:
    st.subheader("Latest Market News")
    with st.spinner("Fetching news..."):
        news_items = analyzer.fetch_news(ticker_symbol, company_name)

    if news_items:
        scores = [n["sentiment_score"] for n in news_items if "sentiment_score" in n]
        avg = sum(scores) / len(scores) if scores else 0

        if avg > 0.15:
            lbl, clr, ico = "Positive", "#39d353", "📈"
        elif avg < -0.15:
            lbl, clr, ico = "Negative", "#f85149", "📉"
        else:
            lbl, clr, ico = "Neutral", "#8b949e", "⚖️"

        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:15px;
            margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;">
            <div>
                <span style="color:#8b949e;font-size:14px;font-weight:600;">Overall News Sentiment</span>
                <h2 style="margin:5px 0 0;color:{clr};">{lbl} ({avg:+.2f})</h2>
            </div>
            <div style="font-size:32px;">{ico}</div>
        </div>""", unsafe_allow_html=True)

        for item in news_items[:15]:
            date_str = item["pub_date"]
            if isinstance(date_str, (int, float)):
                date_str = datetime.fromtimestamp(date_str).strftime("%Y-%m-%d %H:%M")
            s_label = item.get("sentiment_label", "Neutral")
            s_score = item.get("sentiment_score", 0)
            s_clr = "#39d353" if s_label == "Positive" else "#f85149" if s_label == "Negative" else "#8b949e"

            st.markdown(f"#### [{item['title']}]({item['url']})")
            st.markdown(
                f"**Source:** `{item['source']}` | **Date:** `{date_str}` | "
                f"**Sentiment:** <span style='color:{s_clr};font-weight:bold;'>{s_label} ({s_score:+.2f})</span>",
                unsafe_allow_html=True,
            )
            st.markdown("---")
    else:
        st.info("No news available at this time.")

# ═══════════════════════════════════════════════
# TAB 5: 🕷️ SPIDER EVOLUTION (NEW)
# ═══════════════════════════════════════════════
with tab5:
    st.markdown("""
    <div class="spider-header">
        <h2 style="margin:0;">🕷️ 10-Quarter Spider Evolution</h2>
        <p style="color:#8b949e;margin:4px 0 0;">
            Track how the company's financial health evolves across 6 key dimensions over the last 10 quarters.
        </p>
    </div>""", unsafe_allow_html=True)

    spider_key = f"spider_{ticker_symbol}"

    if st.button("🔄 Generate Spider Analysis", width="stretch", key="spider_btn"):
        with st.spinner("Computing 10-quarter spider metrics from Screener.in..."):
            spider_data = analyzer.spider_analysis(ticker_symbol)
            st.session_state[spider_key] = spider_data

    if spider_key in st.session_state and st.session_state[spider_key]:
        spider_data = st.session_state[spider_key]

        # Score overview
        latest = spider_data[-1]
        oldest = spider_data[0]
        score_delta = latest.overall_score - oldest.overall_score

        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("Latest Quarter Score", f"{latest.overall_score:.0f}/100")
        sc2.metric("Oldest Quarter Score", f"{oldest.overall_score:.0f}/100")
        sc3.metric("Improvement", f"{score_delta:+.1f} pts",
                   delta=f"{'↑' if score_delta > 0 else '↓'} over {len(spider_data)} quarters")

        # Sub-tabs for different views
        sp_tab1, sp_tab2, sp_tab3 = st.tabs([
            "\U0001f504 Compare Quarters", "\u25b6 Animated Evolution", "\U0001f4c8 Score Trend"
        ])

        with sp_tab1:
            # Descending order (latest quarter first)
            available_quarters = list(reversed([d.quarter for d in spider_data]))
            defaults = [available_quarters[0]]  # Latest quarter by default
            if len(available_quarters) > 1:
                defaults.append(available_quarters[-1])  # Oldest quarter for comparison
            if len(available_quarters) > 4:
                defaults.insert(1, available_quarters[len(available_quarters) // 2])

            selected = st.multiselect(
                "Select quarters to compare (2-4 recommended):",
                available_quarters, default=defaults,
            )

            fig = SpiderChart.build_comparison(spider_data, selected_quarters=selected)
            st.plotly_chart(fig, use_container_width=True)

        with sp_tab2:
            st.markdown("Press **▶ Play Evolution** to see the spider expand/contract across quarters.")
            fig_anim = SpiderChart.build_animated(spider_data)
            st.plotly_chart(fig_anim, use_container_width=True)

        with sp_tab3:
            st.markdown("**Overall score trend** — click legend items to show individual dimensions.")
            fig_trend = SpiderChart.build_score_trend(spider_data)
            st.plotly_chart(fig_trend, use_container_width=True)

        # Detail table (descending order, latest quarter top)
        with st.expander("📋 Detailed Metric Table", expanded=False):
            rows = []
            for qd in reversed(spider_data):
                row = {"Quarter": qd.quarter, "Overall": qd.overall_score}
                for m in qd.metrics:
                    arrow = "↑" if m.trend == "up" else "↓" if m.trend == "down" else "→"
                    row[m.name] = f"{m.score:.0f} {arrow}"
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), width="stretch")
    else:
        st.info("Click **Generate Spider Analysis** to compute 10-quarter financial metrics.")

# ═══════════════════════════════════════════════
# TAB 6: 🧠 10-QUARTER INTELLIGENCE BRIEFING
# ═══════════════════════════════════════════════
with tab6:
    st.markdown("""
    <div class="spider-header">
        <h2 style="margin:0;">🧠 10-Quarter Intelligence Briefing</h2>
        <p style="color:#8b949e;margin:4px 0 0;">
            AI-powered connected analysis across quarters — track management promises,
            analyst concerns, segment trends, and business evolution.
        </p>
    </div>""", unsafe_allow_html=True)

    analysis_mode = "🧠 Gemini AI" if analyzer.analyzer_type == "gemini" else "📝 Lexicon"
    st.markdown(f"**Analysis Engine:** {analysis_mode}")

    concall_key = f"concall_{ticker_symbol}"
    intel_key = f"intel_{ticker_symbol}"

    # Auto-load cached analyses from SQLite if present and not in session state
    if concall_key not in st.session_state:
        try:
            cached_analyses = analyzer.db.get_all_analyses(ticker_symbol, analyzer.analyzer_type)
            if cached_analyses:
                analyses = analyzer.analyze_concalls(
                    ticker_symbol, max_transcripts=10, force_refresh=False,
                )
                if analyses:
                    st.session_state[concall_key] = analyses
                    cached_intel = analyzer.db.get_intelligence(ticker_symbol)
                    if cached_intel:
                        try:
                            cached_intel.pop("_cached_quarters", None)
                            from models.intelligence import CrossQuarterIntelligence
                            st.session_state[intel_key] = CrossQuarterIntelligence(**cached_intel)
                        except Exception as parse_err:
                            print(f"[UI] Cached intelligence parse error: {parse_err}")
        except Exception as db_err:
            print(f"[UI] DB loading error: {db_err}")

    col_run, col_clear, col_count = st.columns([2, 1, 1])
    with col_count:
        n_transcripts = st.slider("Transcripts to analyze:", 2, 10, 5)
    with col_clear:
        clear_btn = st.button("🗑️ Clear Cache", width="stretch", key="clear_concall_cache")
        if clear_btn:
            analyzer.db.clear_analyses(ticker_symbol)
            analyzer.db.clear_intelligence(ticker_symbol)
            analyzer.db.clear_documents(ticker_symbol)
            analyzer.cache.invalidate("documents", {"symbol": ticker_symbol})
            st.session_state.pop(concall_key, None)
            st.session_state.pop(intel_key, None)
            st.session_state.pop(f"tracks_{ticker_symbol}", None)
            st.rerun()
    with col_run:
        run_btn = st.button(
            f"🚀 Run {n_transcripts}-Quarter Intelligence Analysis",
            width="stretch", key="concall_btn",
        )

    if run_btn:
        with st.spinner(f"Phase 1/2: Downloading & analyzing {n_transcripts} transcripts..."):
            analyses = analyzer.analyze_concalls(
                ticker_symbol, max_transcripts=n_transcripts, force_refresh=True,
            )
            st.session_state[concall_key] = analyses
            # Clear tracks key to force recalculation on new analyses
            st.session_state.pop(f"tracks_{ticker_symbol}", None)

        if analyses and len(analyses) >= 2:
            with st.spinner("Phase 2/2: Synthesizing cross-quarter intelligence..."):
                intel = analyzer.generate_cross_quarter_intelligence(
                    ticker_symbol, analyses, force_refresh=True,
                )
                st.session_state[intel_key] = intel

    if concall_key in st.session_state and st.session_state[concall_key]:
        analyses = st.session_state[concall_key]
        intel = st.session_state.get(intel_key)

        st.success(f"Analyzed {len(analyses)} transcripts using {analyses[0].analyzer_type if analyses else 'N/A'} engine")

        # ── Intelligence Briefing Header ──
        if intel and intel.overall_narrative:
            # Top metrics row
            m1, m2, m3, m4 = st.columns(4)
            latest_q = analyses[-1].quarter if analyses else ""
            m1.metric("Quarters Analyzed", f"{intel.quarters_analyzed}")
            m2.metric("Analysis Period", intel.analysis_period or "N/A", help=f"Latest analyzed quarter: {latest_q}")
            m3.metric("Credibility Score", f"{intel.management_credibility_score:.0f}%")
            m4.metric("Credibility Trend", intel.credibility_trend or "N/A")

            # Story Arc
            st.markdown("---")
            st.markdown("### 📖 The Story Arc")
            st.markdown(f"""
            <div style="background:rgba(22,27,34,0.7);border-left:4px solid #bc8cff;
                        padding:16px 20px;border-radius:0 8px 8px 0;margin:8px 0 16px;">
                <p style="color:#e6edf3;font-size:15px;line-height:1.7;margin:0;">
                    {intel.overall_narrative}
                </p>
            </div>""", unsafe_allow_html=True)

            # ── ⚡ Latest Quarter Executive Snapshot ──
            latest_concall = analyses[-1] if analyses else None
            q_results = load_quarterly_results(analyzer, ticker_symbol)
            cf_res = (
                analyzer.quarterly_cashflow_engine.analyze_quarterly_cashflow(
                    q_results, num_quarters=5, sector=info.get("sector", "")
                )
                if q_results
                else {}
            )
            latest_cf_summary = cf_res.get("latest_quarter_summary", {})

            st.markdown("---")
            with st.container():
                st.markdown(
                    """
                <div style="background: linear-gradient(135deg, rgba(88,166,255,0.12), rgba(57,211,83,0.12));
                            border: 1px solid #30363d; border-radius: 10px; padding: 18px 24px; margin-bottom: 16px;">
                    <h3 style="margin:0; color:#f0f6fc;">⚡ Latest Quarter Executive Snapshot</h3>
                </div>""",
                    unsafe_allow_html=True,
                )

                snap_col1, snap_col2 = st.columns([1, 1])

                with snap_col1:
                    st.markdown("#### 💰 Cashflow & Quality Badges")
                    if latest_cf_summary:
                        q_lbl = latest_cf_summary.get("quarter", "Latest Quarter")
                        fcf_b = latest_cf_summary.get("fcf_badge", "N/A")
                        cfo_b = latest_cf_summary.get("cfo_pat_badge", "N/A")
                        fcf_val = latest_cf_summary.get("fcf", 0.0)
                        cfo_val = latest_cf_summary.get("cfo_pat_ratio", 0.0)

                        st.markdown(f"**Quarter:** `{q_lbl}`")
                        st.markdown(f"- **Free Cash Flow:** {fcf_b} `(₹{fcf_val:,.1f} Cr)`")
                        st.markdown(f"- **CFO / PAT Conversion:** {cfo_b} `({cfo_val:.2f}x)`")
                    else:
                        st.info("Cashflow data unavailable for latest quarter.")

                    if latest_concall and latest_concall.key_operational_metrics:
                        st.markdown("#### ⚙️ Operational Metrics")
                        for op_k, op_v in latest_concall.key_operational_metrics.items():
                            st.markdown(f"- **{op_k}:** `{op_v}`")

                with snap_col2:
                    st.markdown("#### 📌 Key Takeaways")
                    if latest_concall:
                        takeaways = latest_concall.key_takeaways or latest_concall.key_highlights
                        if takeaways:
                            for point in takeaways[:5]:
                                st.markdown(f"- {point}")
                        else:
                            st.info("No specific takeaways extracted for latest quarter.")
                    else:
                        st.info("No concall analysis available for latest quarter.")

            # ── Sub-tabs for intelligence sections ──
            intel_tab1, intel_tab2, intel_tab3, intel_tab4, intel_tab5, intel_tab6 = st.tabs([
                "📊 Financial Progression",
                "🤝 Promise Tracker",
                "🔍 Analyst Concerns",
                "📈 Risk Trajectory",
                "🎯 Milestone Evolution",
                "📋 Quarter Breakdown",
            ])

            # ── Tab: Financial Progression ──
            with intel_tab1:
                st.subheader("Financial Progression Across Quarters")
                fig_fin = MilestoneChart.build_financial_progression_chart(analyses)
                st.plotly_chart(fig_fin, use_container_width=True)

                # Credibility Gauge
                gauge_col, flags_col = st.columns([1, 2])
                with gauge_col:
                    fig_gauge = MilestoneChart.build_credibility_gauge(intel.management_credibility_score)
                    st.plotly_chart(fig_gauge, use_container_width=True)

                with flags_col:
                    fc1, fc2 = st.columns(2)
                    with fc1:
                        if intel.green_flags:
                            st.markdown("### 🟢 Green Flags")
                            for gf in intel.green_flags:
                                st.markdown(f"- ✅ {gf}")
                    with fc2:
                        if intel.red_flags:
                            st.markdown("### 🔴 Red Flags")
                            for rf in intel.red_flags:
                                st.markdown(f"- ⚠️ {rf}")

                # Inflection Points
                if intel.key_inflection_points:
                    st.markdown("### ⚡ Key Inflection Points")
                    for ip in intel.key_inflection_points:
                        st.markdown(f"""
                        <div style="background:rgba(188,140,255,0.1);border-left:3px solid #bc8cff;
                                    padding:10px 14px;border-radius:0 6px 6px 0;margin:6px 0;">
                            <strong style="color:#bc8cff;">{ip.quarter}</strong>
                            <span style="color:#e6edf3;"> — {ip.event}</span><br/>
                            <span style="color:#8b949e;font-size:13px;">Impact: {ip.impact}</span>
                        </div>""", unsafe_allow_html=True)

            # ── Tab: Promise Tracker ──
            with intel_tab2:
                st.subheader("🤝 Management Promise Tracker")
                st.markdown("*Tracking what management committed to and whether they delivered.*")

                if intel.promise_tracker:
                    # Build a dataframe for display
                    promise_rows = []
                    for p in intel.promise_tracker:
                        status_emoji = {
                            "Delivered": "✅",
                            "Missed": "❌",
                            "In Progress": "🔄",
                            "Delayed": "⏳",
                            "Abandoned": "🚫",
                            "Partially Met": "🟡",
                            "Not Yet Due": "⏰",
                        }.get(p.current_status, "❓")
                        promise_rows.append({
                            "Status": f"{status_emoji} {p.current_status}",
                            "Promise": p.promise[:80],
                            "Committed": p.committed_quarter,
                            "Target": p.target_quarter or "—",
                            "Delivered": p.delivery_quarter or "—",
                            "Evidence": p.evidence[:60] if p.evidence else "—",
                        })
                    st.dataframe(pd.DataFrame(promise_rows), width="stretch", hide_index=True)

                    # Detailed expanders
                    for p in intel.promise_tracker:
                        status_emoji = {"Delivered": "✅", "Missed": "❌", "In Progress": "🔄",
                                       "Delayed": "⏳", "Abandoned": "🚫", "Partially Met": "🟡",
                                       "Not Yet Due": "⏰"}.get(p.current_status, "❓")
                        with st.expander(f"{status_emoji} {p.promise[:70]}"):
                            st.markdown(f"**Committed:** {p.committed_quarter}")
                            st.markdown(f"**Target:** {p.target_quarter or 'Not specified'}")
                            st.markdown(f"**Status:** {p.current_status}")
                            if p.delivery_quarter:
                                st.markdown(f"**Delivered:** {p.delivery_quarter}")
                            if p.evidence:
                                st.markdown(f"**Evidence:** {p.evidence}")
                            if p.credibility_impact != 0:
                                impact_color = "#39d353" if p.credibility_impact > 0 else "#f85149"
                                st.markdown(f"**Credibility Impact:** "
                                          f"<span style='color:{impact_color}'>{p.credibility_impact:+.1f}</span>",
                                          unsafe_allow_html=True)
                else:
                    st.info("No promise tracking data available. Run with Gemini AI for promise tracking.")

            # ── Tab: Analyst Concerns ──
            with intel_tab3:
                st.subheader("🔍 Analyst Concern Evolution")
                st.markdown("*How recurring analyst concerns evolved across quarters.*")

                if intel.analyst_concern_evolution:
                    for concern in intel.analyst_concern_evolution:
                        severity_color = {"high": "#f85149", "medium": "#d29922", "low": "#8b949e"}.get(concern.severity, "#8b949e")
                        status_emoji = {
                            "Addressed": "✅", "Recurring": "🔄", "Escalating": "⬆️",
                            "Dismissed": "🚫", "Partially Addressed": "🟡",
                        }.get(concern.current_status, "❓")

                        with st.expander(f"{status_emoji} **{concern.concern}** — *{concern.current_status}*"):
                            st.markdown(f"**First Raised:** {concern.first_raised_quarter}")
                            st.markdown(f"**Severity:** <span style='color:{severity_color};font-weight:700'>"
                                      f"{concern.severity.upper()}</span>", unsafe_allow_html=True)
                            st.markdown(f"**Quarters Raised:** {', '.join(concern.quarters_raised)}")

                            if concern.management_responses:
                                st.markdown("**Management Responses:**")
                                for resp in concern.management_responses:
                                    q = resp.get("quarter", "?")
                                    r = resp.get("response", "")
                                    st.markdown(f"- **{q}:** {r}")
                else:
                    st.info("No analyst concern evolution data. Run with Gemini AI for full analysis.")

            # ── Tab: Risk Trajectory ──
            with intel_tab4:
                st.subheader("📈 Risk Trajectory")
                st.markdown("*How risks evolved across the analysis period.*")

                if intel.risk_trajectory:
                    fig_risk = MilestoneChart.build_risk_trajectory_chart(intel.risk_trajectory)
                    st.plotly_chart(fig_risk, use_container_width=True)

                    for risk in intel.risk_trajectory:
                        direction_emoji = {
                            "Escalating": "🔴", "Recurring": "🟠", "New": "🟣",
                            "Stable": "⚪", "Resolving": "🟢",
                        }.get(risk.direction, "⚪")
                        st.markdown(f"- {direction_emoji} **{risk.risk}** — *{risk.direction}* "
                                  f"({risk.first_quarter} → {risk.last_quarter}, {risk.quarters_mentioned}Q)")
                        if risk.detail:
                            st.caption(f"   {risk.detail}")
                else:
                    st.info("No risk trajectory data available.")

            # ── Tab: Milestone Evolution (existing, kept) ──
            with intel_tab5:
                # Sentiment Timeline Chart
                st.subheader("Sentiment Evolution Timeline")
                fig_timeline = MilestoneChart.build_timeline(analyses)
                st.plotly_chart(fig_timeline, use_container_width=True)

                # Cross-Quarter Milestone Evolution
                st.subheader("🎯 Cross-Quarter Milestone Evolution")
                st.markdown(
                    "Track how management targets, concerns, and strategic initiatives evolve across quarters."
                )

                tracks_key = f"tracks_{ticker_symbol}"
                if tracks_key not in st.session_state:
                    with st.spinner("Analyzing milestone evolution tracks..."):
                        st.session_state[tracks_key] = analyzer.track_milestone_evolution(ticker_symbol, analyses)
                tracks = st.session_state[tracks_key]

                if tracks:
                    for track in tracks:
                        status_emoji = {
                            "Resolved": "🟢", "Milestone Achieved": "🟢",
                            "In Progress": "🔵", "Concern": "🔴",
                            "Future Target": "🟣", "Almost Resolved": "🟡",
                        }.get(track.status, "⚪")

                        with st.expander(f"{status_emoji} **{track.name}** (Current: *{track.status}*)"):
                            st.markdown(f"*{track.description}*")
                            st.markdown("**Timeline Updates:**")
                            for update in track.quarterly_updates:
                                up_emoji = {
                                    "Resolved": "🟢", "Milestone Achieved": "🟢",
                                    "In Progress": "🔵", "Concern": "🔴",
                                    "Future Target": "🟣", "Almost Resolved": "🟡",
                                }.get(update.get("status"), "⚪")
                                st.markdown(f"- **{update.get('quarter')}** — {up_emoji} *{update.get('status')}*: {update.get('note')}")
                else:
                    st.info("No milestone evolution tracks found for this company.")

            # ── Tab: Quarter-by-Quarter Breakdown ──
            with intel_tab6:
                st.subheader("📋 Quarter-by-Quarter Breakdown")

                # Table of Contents Section Selector
                toc_selected = st.selectbox(
                    "📌 Table of Contents — Select Concall Section:",
                    options=[
                        "All Sections",
                        "Key Takeaways",
                        "Volume-Yield Flywheel",
                        "Productivity without Footprint Expansion",
                        "Margin Architecture",
                        "Customer Segmentation",
                        "Capital Allocation",
                        "Guidance & Commitments",
                        "Key Metrics",
                    ],
                    key=f"toc_sel_{ticker_symbol}",
                )

                cards = MilestoneChart.build_detail_cards(analyses)

                for card in cards:
                    border_color = card["tone_color"]
                    # Data confidence badge
                    confidence = card.get("data_confidence", "high")
                    conf_badge = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "")
                    st.markdown(f"""
                    <div class="milestone-card" style="border-left-color:{border_color};">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <h3 style="margin:0;color:#f0f6fc;">{card['quarter']} {conf_badge}</h3>
                            <span style="color:{border_color};font-weight:700;font-size:18px;">
                                {card['label']} ({card['score']:+.2f}) — {card['tone']}
                            </span>
                        </div>
                    </div>""", unsafe_allow_html=True)

                    # Data corrections display (Gemini vs Screener discrepancies)
                    corrections = card.get("corrections", [])
                    if corrections:
                        with st.expander("📊 Data Corrections (Gemini vs Screener)", expanded=False):
                            for corr in corrections:
                                severity_icon = "⚠️" if corr.get("severity") == "hallucination" else "🔧"
                                field_name = corr.get("field", "").replace("_", " ").title()
                                st.markdown(
                                    f"- {severity_icon} **{field_name}**: "
                                    f"Gemini: `{corr.get('gemini_value')}` → "
                                    f"Screener: `{corr.get('screener_value')}` "
                                    f"(divergence: {corr.get('divergence_pct')}%)"
                                )

                    # Financial snapshot row — absolute numbers + growth
                    rev_abs = card.get("revenue_absolute")
                    ebitda_abs = card.get("ebitda_absolute")
                    pat_abs = card.get("pat_absolute")
                    rev_g = card.get("revenue_growth_pct")
                    ebitda_m = card.get("ebitda_margin_pct")
                    pat_g = card.get("pat_growth_pct")
                    net_debt = card.get("net_debt_cr")
                    capex = card.get("capex_actual_cr")

                    has_metrics = any(v is not None for v in [rev_abs, rev_g, ebitda_m, pat_g, net_debt, capex])
                    if has_metrics:
                        cols = st.columns(6)
                        with cols[0]:
                            if rev_abs is not None:
                                delta = f"{rev_g:+.1f}%" if rev_g is not None else None
                                st.metric("Revenue", f"Rs {rev_abs:,.0f} Cr", delta=delta)
                            elif rev_g is not None:
                                st.metric("Revenue Growth", f"{rev_g:+.1f}%")
                        with cols[1]:
                            if ebitda_abs is not None:
                                st.metric("EBITDA", f"Rs {ebitda_abs:,.0f} Cr",
                                         delta=f"{ebitda_m:.1f}%" if ebitda_m else None)
                            elif ebitda_m is not None:
                                st.metric("EBITDA Margin", f"{ebitda_m:.1f}%")
                        with cols[2]:
                            if pat_abs is not None:
                                delta = f"{pat_g:+.1f}%" if pat_g is not None else None
                                st.metric("PAT", f"Rs {pat_abs:,.0f} Cr", delta=delta)
                            elif pat_g is not None:
                                st.metric("PAT Growth", f"{pat_g:+.1f}%")
                        with cols[3]:
                            if net_debt is not None:
                                st.metric("Net Debt", f"Rs {net_debt:,.0f} Cr")
                        with cols[4]:
                            if capex is not None:
                                st.metric("Capex", f"Rs {capex:,.0f} Cr")
                        with cols[5]:
                            pass  # spacing

                    # Promise tracking (guidance met/missed) — with prior quarter reference
                    met = card.get("prior_guidance_met", [])
                    missed = card.get("prior_guidance_missed", [])
                    if met or missed:
                        # Show which prior quarter the assessment refers to
                        prior_q = None
                        if met:
                            prior_q = met[0].get("prior_quarter")
                        elif missed:
                            prior_q = missed[0].get("prior_quarter")
                        header = "**📌 Prior Guidance Assessment"
                        if prior_q:
                            header += f" (vs {prior_q} guidance)"
                        header += ":**"
                        st.markdown(header)
                        for p in met:
                            st.markdown(f"- ✅ **ACHIEVED:** {p.get('target', '')} → {p.get('actual', '')}")
                        for p in missed:
                            st.markdown(f"- ❌ **MISSED:** {p.get('target', '')} → {p.get('actual', '')}")

                    # ── 8 Institutional Concall Analysis Sections ──
                    st.markdown("#### 🏛️ Institutional Concall Analysis")
                    show_all_sec = (toc_selected == "All Sections")

                    if show_all_sec or toc_selected == "Key Takeaways":
                        takeaways = card.get("key_takeaways") or card.get("highlights") or []
                        with st.expander("📌 **Key Takeaways**", expanded=True):
                            if takeaways:
                                for item in takeaways:
                                    st.markdown(f"- 💡 {item}")
                            else:
                                st.caption("No key takeaways extracted.")

                    if show_all_sec or toc_selected == "Volume-Yield Flywheel":
                        vol = card.get("volume_yield_flywheel") or []
                        with st.expander("🔄 **Volume-Yield Flywheel**", expanded=show_all_sec or toc_selected == "Volume-Yield Flywheel"):
                            if vol:
                                for item in vol:
                                    st.markdown(f"- ⚙️ {item}")
                            else:
                                st.caption("No volume-yield flywheel details available.")

                    if show_all_sec or toc_selected == "Productivity without Footprint Expansion":
                        prod = card.get("productivity_efficiency") or []
                        with st.expander("🏗️ **Productivity without Footprint Expansion**", expanded=show_all_sec or toc_selected == "Productivity without Footprint Expansion"):
                            if prod:
                                for item in prod:
                                    st.markdown(f"- 🏭 {item}")
                            else:
                                st.caption("No productivity/efficiency details available.")

                    if show_all_sec or toc_selected == "Margin Architecture":
                        margins = card.get("margin_architecture") or []
                        with st.expander("📐 **Margin Architecture**", expanded=show_all_sec or toc_selected == "Margin Architecture"):
                            if margins:
                                for item in margins:
                                    st.markdown(f"- 📊 {item}")
                            else:
                                st.caption("No margin architecture details available.")

                    if show_all_sec or toc_selected == "Customer Segmentation":
                        cust = card.get("customer_segmentation") or []
                        with st.expander("👥 **Customer Segmentation**", expanded=show_all_sec or toc_selected == "Customer Segmentation"):
                            if cust:
                                for item in cust:
                                    st.markdown(f"- 🎯 {item}")
                            else:
                                st.caption("No customer segmentation details available.")

                    if show_all_sec or toc_selected == "Capital Allocation":
                        cap = card.get("capital_allocation") or []
                        with st.expander("🏦 **Capital Allocation**", expanded=show_all_sec or toc_selected == "Capital Allocation"):
                            if cap:
                                for item in cap:
                                    st.markdown(f"- 💰 {item}")
                            else:
                                st.caption("No capital allocation details available.")

                    if show_all_sec or toc_selected == "Guidance & Commitments":
                        guidance_list = card.get("guidance_commitments") or card.get("targets") or []
                        guidance_dict = card.get("guidance_numbers") or {}
                        with st.expander("📜 **Guidance & Commitments**", expanded=show_all_sec or toc_selected == "Guidance & Commitments"):
                            if guidance_list:
                                for item in guidance_list:
                                    st.markdown(f"- 🎯 {item}")
                            if guidance_dict:
                                st.markdown("**Guidance Metrics:**")
                                for gk, gv in guidance_dict.items():
                                    st.markdown(f"  - **{gk.replace('_', ' ').title()}:** {gv}")
                            if not guidance_list and not guidance_dict:
                                st.caption("No guidance or commitments extracted.")

                    if show_all_sec or toc_selected == "Key Metrics":
                        op_metrics = card.get("key_operational_metrics") or {}
                        with st.expander("🔢 **Key Metrics**", expanded=show_all_sec or toc_selected == "Key Metrics"):
                            if op_metrics and isinstance(op_metrics, dict):
                                m_items = list(op_metrics.items())
                                m_cols = st.columns(min(4, max(1, len(m_items))))
                                for idx, (mk, mv) in enumerate(m_items):
                                    m_cols[idx % len(m_cols)].metric(mk.replace("_", " ").title(), str(mv))
                            else:
                                st.caption("No operational metrics recorded.")

                    # Segment Data
                    segments = card.get("segment_data", [])
                    if segments:
                        st.markdown("📊 **Segment Breakdown:**")
                        seg_rows = []
                        for s in segments:
                            rev_val = "—"
                            if s.get("revenue_cr") is not None:
                                try:
                                    rev_val = f"{float(s['revenue_cr']):,.0f}"
                                except (ValueError, TypeError):
                                    rev_val = str(s['revenue_cr'])

                            growth_val = "—"
                            if s.get("growth_pct") is not None:
                                try:
                                    growth_val = f"{float(s['growth_pct']):+.1f}%"
                                except (ValueError, TypeError):
                                    growth_val = f"{s['growth_pct']}%"

                            margin_val = "—"
                            if s.get("margin_pct") is not None:
                                try:
                                    margin_val = f"{float(s['margin_pct']):.1f}%"
                                except (ValueError, TypeError):
                                    margin_val = f"{s['margin_pct']}%"

                            seg_rows.append({
                                "Segment": s.get("name", "?"),
                                "Revenue (Rs Cr)": rev_val,
                                "Growth %": growth_val,
                                "Margin %": margin_val,
                            })
                        st.dataframe(pd.DataFrame(seg_rows), width="stretch", hide_index=True)

                    # Management Quotes
                    quotes = card.get("management_quotes", [])
                    if quotes:
                        st.markdown("🎙️ **Management Quotes:**")
                        for q in quotes:
                            st.markdown(f"> *\"{q}\"*")

                    # Analyst Pushback
                    analyst_qs = card.get("analyst_concerns", [])
                    if analyst_qs:
                        st.markdown("🔍 **Analyst Pushback:**")
                        for aq in analyst_qs:
                            st.markdown(f"- 💬 {aq}")

                    st.markdown("---")

        else:
            # No intelligence data — show basic view
            st.subheader("Sentiment Evolution Timeline")
            fig_timeline = MilestoneChart.build_timeline(analyses)
            st.plotly_chart(fig_timeline, use_container_width=True)

            st.subheader("📋 Quarter-by-Quarter Breakdown")
            toc_selected_basic = st.selectbox(
                "📌 Table of Contents — Select Concall Section:",
                options=[
                    "All Sections",
                    "Key Takeaways",
                    "Volume-Yield Flywheel",
                    "Productivity without Footprint Expansion",
                    "Margin Architecture",
                    "Customer Segmentation",
                    "Capital Allocation",
                    "Guidance & Commitments",
                    "Key Metrics",
                ],
                key=f"toc_sel_basic_{ticker_symbol}",
            )
            cards = MilestoneChart.build_detail_cards(analyses)
            for card in cards:
                border_color = card["tone_color"]
                st.markdown(f"""
                <div class="milestone-card" style="border-left-color:{border_color};">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <h3 style="margin:0;color:#f0f6fc;">{card['quarter']}</h3>
                        <span style="color:{border_color};font-weight:700;font-size:18px;">
                            {card['label']} ({card['score']:+.2f}) — {card['tone']}
                        </span>
                    </div>
                </div>""", unsafe_allow_html=True)

                # Render 8 Institutional Sections
                show_all_sec = (toc_selected_basic == "All Sections")

                if show_all_sec or toc_selected_basic == "Key Takeaways":
                    takeaways = card.get("key_takeaways") or card.get("highlights") or []
                    with st.expander("📌 **Key Takeaways**", expanded=True):
                        if takeaways:
                            for item in takeaways:
                                st.markdown(f"- 💡 {item}")
                        else:
                            st.caption("No key takeaways extracted.")

                if show_all_sec or toc_selected_basic == "Volume-Yield Flywheel":
                    vol = card.get("volume_yield_flywheel") or []
                    with st.expander("🔄 **Volume-Yield Flywheel**", expanded=show_all_sec or toc_selected_basic == "Volume-Yield Flywheel"):
                        if vol:
                            for item in vol:
                                st.markdown(f"- ⚙️ {item}")
                        else:
                            st.caption("No volume-yield flywheel details available.")

                if show_all_sec or toc_selected_basic == "Productivity without Footprint Expansion":
                    prod = card.get("productivity_efficiency") or []
                    with st.expander("🏗️ **Productivity without Footprint Expansion**", expanded=show_all_sec or toc_selected_basic == "Productivity without Footprint Expansion"):
                        if prod:
                            for item in prod:
                                st.markdown(f"- 🏭 {item}")
                        else:
                            st.caption("No productivity/efficiency details available.")

                if show_all_sec or toc_selected_basic == "Margin Architecture":
                    margins = card.get("margin_architecture") or []
                    with st.expander("📐 **Margin Architecture**", expanded=show_all_sec or toc_selected_basic == "Margin Architecture"):
                        if margins:
                            for item in margins:
                                st.markdown(f"- 📊 {item}")
                        else:
                            st.caption("No margin architecture details available.")

                if show_all_sec or toc_selected_basic == "Customer Segmentation":
                    cust = card.get("customer_segmentation") or []
                    with st.expander("👥 **Customer Segmentation**", expanded=show_all_sec or toc_selected_basic == "Customer Segmentation"):
                        if cust:
                            for item in cust:
                                st.markdown(f"- 🎯 {item}")
                        else:
                            st.caption("No customer segmentation details available.")

                if show_all_sec or toc_selected_basic == "Capital Allocation":
                    cap = card.get("capital_allocation") or []
                    with st.expander("🏦 **Capital Allocation**", expanded=show_all_sec or toc_selected_basic == "Capital Allocation"):
                        if cap:
                            for item in cap:
                                st.markdown(f"- 💰 {item}")
                        else:
                            st.caption("No capital allocation details available.")

                if show_all_sec or toc_selected_basic == "Guidance & Commitments":
                    guidance_list = card.get("guidance_commitments") or card.get("targets") or []
                    guidance_dict = card.get("guidance_numbers") or {}
                    with st.expander("📜 **Guidance & Commitments**", expanded=show_all_sec or toc_selected_basic == "Guidance & Commitments"):
                        if guidance_list:
                            for item in guidance_list:
                                st.markdown(f"- 🎯 {item}")
                        if guidance_dict:
                            st.markdown("**Guidance Metrics:**")
                            for gk, gv in guidance_dict.items():
                                st.markdown(f"  - **{gk.replace('_', ' ').title()}:** {gv}")
                        if not guidance_list and not guidance_dict:
                            st.caption("No guidance or commitments extracted.")

                if show_all_sec or toc_selected_basic == "Key Metrics":
                    op_metrics = card.get("key_operational_metrics") or {}
                    with st.expander("🔢 **Key Metrics**", expanded=show_all_sec or toc_selected_basic == "Key Metrics"):
                        if op_metrics and isinstance(op_metrics, dict):
                            m_items = list(op_metrics.items())
                            m_cols = st.columns(min(4, max(1, len(m_items))))
                            for idx, (mk, mv) in enumerate(m_items):
                                m_cols[idx % len(m_cols)].metric(mk.replace("_", " ").title(), str(mv))
                        else:
                            st.caption("No operational metrics recorded.")
                st.markdown("---")
    else:
        st.info("Click **Run Intelligence Analysis** to download and analyze transcripts.")

# ═══════════════════════════════════════════════
# TAB 7: VALUATION & THESIS
# ═══════════════════════════════════════════════
with tab7:
    st.markdown("""
    <div class="spider-header">
        <h2 style="margin:0;">🧭 Valuation & Thesis</h2>
        <p style="color:#8b949e;margin:4px 0 0;">
            Multiple-based fair value, deterministic risk flags, and a compact research stance.
        </p>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Building valuation and risk snapshot..."):
        quarterly_results = load_quarterly_results(analyzer, ticker_symbol)
        decision = analyzer.decision_snapshot(info, hist_df, quarterly_results)

    valuation = decision["valuation"]
    risks = decision["risks"]
    thesis = decision["thesis"]

    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Research Stance", thesis.stance, delta=f"{thesis.score}/100")
    v2.metric("Base Fair Value", f"₹{valuation.base_value:,.2f}" if valuation.base_value else "N/A")
    v3.metric("Margin of Safety", f"{valuation.margin_of_safety:+.1f}%")
    v4.metric("Valuation State", valuation.valuation_state)

    st.subheader("Fair Value Range")
    valuation_rows = [
        {"Scenario": "Bear", "Implied Multiple": f"{max(0, valuation.base_multiple * 0.7):.1f}x", "Fair Value": valuation.bear_value},
        {"Scenario": "Base", "Implied Multiple": f"{valuation.base_multiple:.1f}x", "Fair Value": valuation.base_value},
        {"Scenario": "Bull", "Implied Multiple": f"{valuation.base_multiple * 1.3:.1f}x", "Fair Value": valuation.bull_value},
    ]
    st.dataframe(pd.DataFrame(valuation_rows), width="stretch", hide_index=True)

    if valuation.notes:
        for note in valuation.notes:
            st.caption(note)

    st.markdown("---")
    r_col, t_col = st.columns([1, 1])

    with r_col:
        st.subheader("Risk Flags")
        risk_rows = [
            {
                "Severity": r.severity,
                "Category": r.category,
                "Flag": r.message,
                "Evidence": r.evidence,
            }
            for r in risks
        ]
        st.dataframe(pd.DataFrame(risk_rows), width="stretch", hide_index=True)

    with t_col:
        st.subheader("Thesis")
        st.markdown("**Bull Case**")
        for item in thesis.bull_case:
            st.markdown(f"- {item}")

        st.markdown("**Bear Case**")
        for item in thesis.bear_case:
            st.markdown(f"- {item}")

        st.markdown("**Watch Items**")
        for item in thesis.watch_items:
            st.markdown(f"- {item}")

# ═══════════════════════════════════════════════
# TAB 8: CASHFLOW ANALYSIS
# ═══════════════════════════════════════════════
with tab8:
    st.markdown("""
    <div class="spider-header">
        <h2 style="margin:0;">💰 Comprehensive Cashflow Analysis</h2>
        <p style="color:#8b949e;margin:4px 0 0;">
            Is this business generating real cash or just showing revenue on credit?
            CFO vs PAT, working capital cycle, receivables/payables, free cash flow.
        </p>
    </div>""", unsafe_allow_html=True)

    cf_key = f"cashflow_{ticker_symbol}"

    cf_col1, cf_col2 = st.columns([2, 1])
    with cf_col1:
        cf_run = st.button(
            "🚀 Run Cashflow Analysis",
            width="stretch", key="cashflow_btn",
        )
    with cf_col2:
        cf_refresh = st.checkbox("Force refresh (re-scrape)", key="cf_refresh")

    if cf_run:
        with st.spinner("Fetching cashflow data from Screener.in (cash flow + balance sheet)..."):
            cf_result = analyzer.cashflow_analysis(
                ticker_symbol, force_refresh=cf_refresh,
            )
            st.session_state[cf_key] = cf_result.model_dump()

    # Auto-load from cache if available
    if cf_key not in st.session_state:
        cached_cf = analyzer.db.get_cashflow(ticker_symbol)
        if cached_cf:
            st.session_state[cf_key] = cached_cf

    if cf_key in st.session_state and st.session_state[cf_key]:
        from models.cashflow import CashFlowAnalysisResult, CashFlowPeriod
        cf_data = CashFlowAnalysisResult(**st.session_state[cf_key])

        # --- Cash Quality Score ---
        score = cf_data.cash_quality_score
        score_color = "#39d353" if score >= 70 else "#d29922" if score >= 40 else "#f85149"
        score_label = "Strong" if score >= 70 else "Moderate" if score >= 40 else "Weak"

        sq1, sq2, sq3 = st.columns(3)
        sq1.metric("Cash Quality Score", f"{score:.0f}/100", delta=score_label)
        sq2.metric("Annual Periods", f"{len(cf_data.annual_data)} years")
        sq3.metric("Quarterly Periods", f"{len(cf_data.quarterly_bs_data)} quarters")

        st.markdown(f"""
        <div class="premium-card" style="border-left: 4px solid {score_color};">
            <p style="font-size:16px;margin:0;">{cf_data.summary}</p>
        </div>""", unsafe_allow_html=True)

        # --- Diagnostic Signals ---
        if cf_data.diagnostics:
            st.subheader("🔍 Diagnostic Signals")
            for diag in cf_data.diagnostics:
                emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(diag.severity, "⚪")
                st.markdown(f"{emoji} **{diag.category}** — {diag.message}")
            st.markdown("---")

        # --- Charts ---
        annual = [CashFlowPeriod(**d) if isinstance(d, dict) else d for d in cf_data.annual_data]

        if annual:
            st.subheader("📊 CFO vs Net Profit (Cash Conversion)")
            st.markdown("*Is accounting profit backed by real cash? CFO/PAT > 1.0x is ideal.*")
            fig_cfo = CashflowChart.build_cfo_vs_pat(annual)
            st.plotly_chart(fig_cfo, use_container_width=True, key=f"cf_cfo_pat_{ticker_symbol}")

            cf_chart_col1, cf_chart_col2 = st.columns(2)

            with cf_chart_col1:
                st.subheader("💸 Cash Flow Composition")
                st.markdown("*Operating / Investing / Financing breakdown*")
                fig_comp = CashflowChart.build_cashflow_composition(annual)
                st.plotly_chart(fig_comp, use_container_width=True, key=f"cf_comp_{ticker_symbol}")

            with cf_chart_col2:
                st.subheader("📈 Free Cash Flow Trend")
                st.markdown("*CFO minus capital expenditure (investing outflows)*")
                fig_fcf = CashflowChart.build_fcf_trend(annual)
                st.plotly_chart(fig_fcf, use_container_width=True, key=f"cf_fcf_{ticker_symbol}")

            st.markdown("---")

            st.subheader("🔄 Working Capital Cycle")
            st.markdown("*Receivable Days + Inventory Days - Payable Days = Cash tied up in operations*")
            fig_wc = CashflowChart.build_working_capital_chart(annual)
            st.plotly_chart(fig_wc, use_container_width=True, key=f"cf_wc_{ticker_symbol}")

            st.subheader("⚠️ Receivable vs Revenue Growth")
            st.markdown("*If receivables grow faster than revenue, revenue may be credit-driven*")
            fig_recv = CashflowChart.build_receivable_vs_revenue_growth(annual)
            st.plotly_chart(fig_recv, use_container_width=True, key=f"cf_recv_{ticker_symbol}")
            
            st.subheader("📊 Revenue vs CFO Growth")
            st.markdown("*Is operating cash generation keeping up with revenue expansion?*")
            fig_rev_cfo = CashflowChart.build_revenue_vs_cfo_growth(annual)
            st.plotly_chart(fig_rev_cfo, use_container_width=True, key=f"cf_rev_cfo_{ticker_symbol}")

            # --- Raw Data Table ---
            st.markdown("---")
            with st.expander("📋 Raw Annual Cashflow Data (Latest Period First)"):
                table_data = []
                for p in reversed(annual):
                    row = {
                        "Period": p.period,
                        "Revenue": f"Rs {p.revenue:,.0f}" if p.revenue else "-",
                        "PAT": f"Rs {p.net_profit:,.0f}" if p.net_profit else "-",
                        "CFO": f"Rs {p.cfo:,.0f}" if p.cfo else "-",
                        "CFI": f"Rs {p.cfi:,.0f}" if p.cfi else "-",
                        "CFF": f"Rs {p.cff:,.0f}" if p.cff else "-",
                        "FCF": f"Rs {p.free_cash_flow:,.0f}" if p.free_cash_flow else "-",
                        "CCR": f"{p.cash_conversion_ratio:.2f}x" if p.cash_conversion_ratio else "-",
                        "Recv Days": f"{p.receivable_days:.0f}" if p.receivable_days else "-",
                        "Pay Days": f"{p.payable_days:.0f}" if p.payable_days else "-",
                        "WC Days": f"{p.working_capital_days:.0f}" if p.working_capital_days else "-",
                        "Receivables": f"Rs {p.trade_receivables:,.0f}" if p.trade_receivables else "-",
                        "Payables": f"Rs {p.trade_payables:,.0f}" if p.trade_payables else "-",
                        "Borrowings": f"Rs {p.total_borrowings:,.0f}" if p.total_borrowings else "-",
                        "Z-Score": f"{p.altman_z_score:.2f}" if p.altman_z_score else "-",
                        "DuPont ROE": f"{p.dupont_roe:.2f}%" if p.dupont_roe else "-",
                        "FCF Margin": f"{p.fcf_margin:.2f}%" if p.fcf_margin else "-",
                    }
                    table_data.append(row)
                st.dataframe(pd.DataFrame(table_data), width="stretch", hide_index=True)
        else:
            st.warning("No annual cashflow data found. The company may not have cash flow data on Screener.in.")
    else:
        st.info("Click **Run Cashflow Analysis** to fetch and analyze cash flow data from Screener.in. Results are cached in the database.")

# ═══════════════════════════════════════════════
# TAB 9: NOTES
# ═══════════════════════════════════════════════
with tab9:
    st.subheader("📝 Research Journal")
    st.markdown("Document your analysis, investment thesis, and observations.")

    new_note = st.text_area("Add a note:", height=100)
    if st.button("💾 Save Note"):
        if new_note.strip():
            analyzer.add_note(ticker_symbol, new_note.strip())
            st.success("Note saved!")
            st.rerun()
        else:
            st.warning("Note cannot be empty.")

    st.markdown("---")
    st.subheader("Saved Notes")
    notes_df = analyzer.get_notes(ticker_symbol)

    if not notes_df.empty:
        for _, row in notes_df.iterrows():
            st.markdown(f"""
            <div class="premium-card">
                <small style="color:#8b949e;">{row['created_at']}</small>
                <p style="margin-top:10px;font-size:15px;line-height:1.6;">{row['note']}</p>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No saved notes for this company.")

# ═══════════════════════════════════════════════
# TAB 10: VAHAN EV SALES
# ═══════════════════════════════════════════════
with tab10:
    st.markdown("""
    <div class="spider-header">
        <h2 style="margin:0;">🛵 Vahan EV Sales Report</h2>
        <p style="color:#8b949e;margin:4px 0 0;">
            Electric 2-wheeler retail registration statistics sourced from Ministry of Road Transport &amp; Highways (MoRTH), GoI.
            <br><em>Cumulative MTD from Vahan portal → daily values interpolated.</em>
        </p>
    </div>""", unsafe_allow_html=True)

    from providers.vahan_provider import VahanProvider
    import datetime as _dt

    vahan = VahanProvider()
    maker_name = vahan.get_maker_by_symbol(ticker_symbol)
    _today = _dt.date.today()
    _current_month = _today.month
    _current_year = _today.year
    _current_month_name = vahan.MONTH_NAMES[_current_month - 1]
    _prev_y, _prev_m = vahan._get_prev_month(_current_year, _current_month)
    _prev_month_name = vahan.MONTH_NAMES[_prev_m - 1]

    if maker_name:
        st.success(f"🎯 **{company_name}** is a major EV 2W manufacturer. Showing Vahan registration statistics for **{maker_name}**.")
    else:
        st.info(f"ℹ️ **{company_name} ({ticker_symbol})** is not a primary EV 2W manufacturer. Showing overall electric 2-wheeler market leaders (TVS, Bajaj, Ola, Ather) for context.")

    vahan_view = st.radio(
        "Select View Mode:",
        ["📊 Monthly Trend Analysis", f"📅 Daily & MTD Tracker ({_current_month_name} {_current_year})"],
        horizontal=True, key="vahan_view_mode"
    )
    st.markdown("---")

    if vahan_view == "📊 Monthly Trend Analysis":
        year_col, info_col = st.columns([1, 3])
        with year_col:
            available_years = list(range(_current_year, 2023, -1))
            selected_year = st.selectbox("Select Calendar Year:", available_years, index=0)

        # Fetch data
        df_raw = vahan.get_monthly_sales_df()
        df_year = df_raw[df_raw["Year"] == selected_year]
        
        # Months ordering
        months_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        # Maker-wise pivot for chart
        df_pivot = vahan.get_comparison_data(selected_year)

        # --- YTD + All-Time Totals ---
        ytd_totals = vahan.get_ytd_totals(selected_year)
        alltime_totals = vahan.get_all_time_totals()

        if maker_name:
            ytd_col, alltime_col, share_col = st.columns(3)
            ytd_val = ytd_totals.get(maker_name, 0)
            alltime_val = alltime_totals.get(maker_name, 0)
            total_all_makers_ytd = sum(ytd_totals.values())
            ytd_share = (ytd_val / total_all_makers_ytd * 100) if total_all_makers_ytd > 0 else 0
            ytd_col.metric(f"YTD {selected_year} Registrations", f"{ytd_val:,}", help=f"Total registrations for {maker_name} in {selected_year}")
            alltime_col.metric("All-Time Total (Jan 2024 → Present)", f"{alltime_val:,}")
            share_col.metric(f"YTD Big-4 Market Share", f"{ytd_share:.1f}%")
        else:
            ytd_cols = st.columns(4)
            for i, m in enumerate(vahan.get_makers()):
                ytd_cols[i].metric(f"{m} YTD {selected_year}", f"{ytd_totals.get(m, 0):,}")

        st.markdown("---")
        
        # Show highlighted metrics for the selected company if applicable
        if maker_name:
            # Get data for the selected maker
            maker_df = df_year[df_year["Maker"] == maker_name]
            
            # Sort chronologically by converting Month to Categorical
            maker_df = maker_df.copy()
            maker_df["Month"] = pd.Categorical(maker_df["Month"], categories=months_order, ordered=True)
            maker_df = maker_df.sort_values("Month")
            
            if not maker_df.empty:
                latest_row = maker_df.iloc[-1]
                latest_month = latest_row["Month"]
                latest_sales = latest_row["Registrations"]
                
                # Calculate MoM growth
                mom_val = "N/A"
                if len(maker_df) > 1:
                    prev_sales = maker_df.iloc[-2]["Registrations"]
                    if prev_sales > 0:
                        mom_growth = ((latest_sales - prev_sales) / prev_sales) * 100
                        mom_val = f"{mom_growth:+.1f}%"
                
                # Calculate market share among big 4 in the latest month
                month_total_df = df_year[df_year["Month"] == latest_month]
                total_big_four = month_total_df["Registrations"].sum()
                market_share = (latest_sales / total_big_four * 100) if total_big_four > 0 else 0
                
                m_col1, m_col2, m_col3 = st.columns(3)
                m_col1.metric(f"Registrations ({latest_month} {selected_year})", f"{latest_sales:,.0f}", help=f"Actual retail registrations for {maker_name}")
                m_col2.metric("MoM Growth", mom_val)
                m_col3.metric("Big-4 Market Share", f"{market_share:.1f}%", help="Share among TVS, Bajaj, Ola, and Ather")
                
        # Charting: Registration comparison over the months
        import plotly.graph_objects as go
        
        fig = go.Figure()
        colors = {
            "Ola Electric": "#bc8cff",       # Purple
            "TVS Motor Company": "#39d353",   # Green
            "Bajaj Auto": "#58a6ff",          # Blue
            "Ather Energy": "#d29922",        # Yellow
        }
        
        for maker in vahan.get_makers():
            maker_monthly = df_year[df_year["Maker"] == maker].copy()
            maker_monthly["Month"] = pd.Categorical(maker_monthly["Month"], categories=months_order, ordered=True)
            maker_monthly = maker_monthly.sort_values("Month")
            
            # Highlight current company if it matches
            width = 4 if maker == maker_name else 2
            opacity = 1.0 if (maker == maker_name or not maker_name) else 0.5
            
            fig.add_trace(go.Scatter(
                x=maker_monthly["Month"],
                y=maker_monthly["Registrations"],
                name=maker,
                mode="lines+markers",
                line=dict(color=colors.get(maker, "#8b949e"), width=width),
                marker=dict(size=6, opacity=opacity),
                opacity=opacity,
                hovertemplate=f"<b>{maker}</b><br>Month: %{{x}}<br>Registrations: %{{y:,.0f}}<extra></extra>"
            ))
            
        fig.update_layout(
            title=f"Monthly EV 2W Registrations Comparison — {selected_year}",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Month", gridcolor="rgba(48,54,61,0.3)"),
            yaxis=dict(title="Registrations", gridcolor="rgba(48,54,61,0.3)"),
            height=450,
            margin=dict(l=40, r=40, t=50, b=40)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Display Maker-wise breakdown table & link
        col_table, col_info = st.columns([2, 1])
        
        with col_table:
            st.subheader("📋 Monthly Registrations Table")
            # Format columns for display
            df_display = df_pivot[df_pivot["Year"] == selected_year].copy()
            # Drop Year col as it is selected by filter
            df_display = df_display.drop(columns=["Year"])
            st.dataframe(df_display, width="stretch", hide_index=True)
            
        with col_info:
            st.subheader("🔗 Data Source Details")
            st.markdown(f"""
            - **Source:** Vahan Dashboard 4 ([Parivahan Portal](https://vahan.parivahan.gov.in/vahan4dashboard/vahan/view/reportview.xhtml))
            - **Category:** EV 2W High Speed Registrations
            - **Region:** All India (36 States/UTs)
            
            To audit this data on the Vahan portal:
            1. Open the [Vahan Dashboard Link](https://vahan.parivahan.gov.in/vahan4dashboard/vahan/view/reportview.xhtml)
            2. Set **Y-Axis** to **'Maker'** and **X-Axis** to **'Month Wise'**
            3. Filter **Fuel** to **'ELECTRIC'**
            4. Select Year type as **'Calendar Year'** and Year as **'{selected_year}'**
            5. Click **'Refresh'**
            """)

    else:
        # ═══════════════════════════════════════════════
        # DAILY & MTD TRACKER (current month)
        # ═══════════════════════════════════════════════
        st.subheader(f"📅 {_current_month_name} {_current_year} Daily EV 2W Registrations")
        st.markdown("*Cumulative MTD from Vahan portal. Daily values are interpolated estimates between snapshot dates.*")

        # --- Manual Vahan Cumulative Input Panel ---
        with st.expander("📥 Update Cumulative from Vahan Portal (paste actual numbers)", expanded=False):
            st.markdown("""
            Paste the **cumulative MTD** registrations from the Vahan portal for each OEM.
            This will replace estimated values and recalculate all daily breakdowns.
            """)

            snap_date_col, snap_btn_col = st.columns([2, 1])
            with snap_date_col:
                snap_date_input = st.date_input(
                    "Snapshot Date:",
                    value=_today,
                    max_value=_today,
                    key="vahan_snap_date"
                )

            input_cols = st.columns(4)
            makers_list = vahan.get_makers()
            snap_status = vahan.get_snapshot_status(_current_month, _current_year)

            manual_values = {}
            for i, m in enumerate(makers_list):
                current_val = snap_status.get(m, {}).get("cumulative_mtd", 0)
                source_tag = snap_status.get(m, {}).get("source", "none")
                source_emoji = "✅" if source_tag == "vahan_manual" else "📊"
                with input_cols[i]:
                    short_name = m.split()[0] if " " in m else m  # "TVS", "Bajaj", etc.
                    manual_values[m] = st.number_input(
                        f"{source_emoji} {short_name} MTD",
                        min_value=0,
                        value=current_val,
                        step=100,
                        key=f"vahan_manual_{m.replace(' ', '_')}"
                    )

            if st.button("💾 Save & Recalculate from Vahan Data", key="vahan_save_manual"):
                date_str = snap_date_input.strftime("%Y-%m-%d")
                for m, val in manual_values.items():
                    if val > 0:
                        vahan.save_manual_cumulative(m, date_str, val)
                st.success(f"✅ Saved Vahan cumulative for {date_str} and recalculated daily breakdown.")
                st.rerun()

        # --- Get data (triggers snapshot + interpolation on launch) ---
        df_daily = vahan.get_daily_sales_df()
        df_daily_pivot = vahan.get_daily_comparison_df()

        # Format Date column for display
        df_daily_pivot_display = df_daily_pivot.copy()
        if not df_daily_pivot_display.empty:
            df_daily_pivot_display["Date"] = df_daily_pivot_display["Date"].dt.strftime("%Y-%m-%d")

        # --- Data Source Status Bar ---
        snap_status = vahan.get_snapshot_status(_current_month, _current_year)
        status_cols = st.columns(4)
        for i, m in enumerate(makers_list):
            ss = snap_status.get(m, {})
            src = ss.get("source", "none")
            cum = ss.get("cumulative_mtd", 0)
            dt_str = ss.get("latest_date", "N/A")
            if src == "vahan_manual":
                status_cols[i].markdown(f"✅ **{m}**: {cum:,} (Verified — {dt_str})")
            elif src == "estimated":
                status_cols[i].markdown(f"📊 **{m}**: {cum:,} (Estimated — {dt_str})")
            else:
                status_cols[i].markdown(f"❓ **{m}**: No data")

        st.markdown("---")

        # --- Show OEM Highlight metrics ---
        if maker_name:
            maker_daily = df_daily[df_daily["Maker"] == maker_name].sort_values("Date")
            maker_current = maker_daily[maker_daily["Date"].dt.month == _current_month].sort_values("Date")
            if not maker_current.empty:
                # Latest day
                latest_day_row = maker_current.iloc[-1]
                latest_date_str = latest_day_row["Date"].strftime("%Y-%m-%d")
                latest_day_sales = latest_day_row["Registrations"]

                # Daily Growth Rate
                daily_growth_val = "N/A"
                prev_date_str = "previous day"
                if len(maker_current) > 1:
                    prev_day_row = maker_current.iloc[-2]
                    prev_day_sales = prev_day_row["Registrations"]
                    prev_date_str = prev_day_row["Date"].strftime("%Y-%m-%d")
                    if prev_day_sales > 0:
                        daily_growth = ((latest_day_sales - prev_day_sales) / prev_day_sales) * 100
                        daily_growth_val = f"{daily_growth:+.1f}%"

                # MTD cumulative for this maker
                mtd_total = maker_current["Registrations"].sum()

                # Velocity vs previous month
                prev_month_total = vahan._get_monthly_total(maker_name, _prev_y, _prev_m)
                if prev_month_total and prev_month_total > 0:
                    import calendar as _cal
                    days_in_prev = _cal.monthrange(_prev_y, _prev_m)[1]
                    prev_daily_avg = prev_month_total / days_in_prev
                    current_daily_avg = mtd_total / _today.day
                    velocity_vs_prev = ((current_daily_avg - prev_daily_avg) / prev_daily_avg) * 100
                    velocity_val = f"{velocity_vs_prev:+.1f}%"
                else:
                    velocity_val = "N/A"

                dm1, dm2, dm3, dm4 = st.columns(4)
                dm1.metric(f"Latest Day ({latest_date_str})", f"{latest_day_sales:,.0f}")
                dm2.metric(f"Daily Growth (vs {prev_date_str})", daily_growth_val)
                dm3.metric(f"MTD Cumulative ({_current_month_name})", f"{mtd_total:,}")
                dm4.metric(f"Velocity vs {_prev_month_name} Avg", velocity_val, help=f"Current daily average vs {_prev_month_name}'s daily average")

        # --- Cumulative MTD Leaderboard ---
        st.markdown("---")
        st.subheader(f"📊 {_current_month_name} MTD Cumulative Leaderboard")
        mc1, mc2, mc3, mc4 = st.columns(4)
        mtd_totals = {}
        for m in vahan.get_makers():
            mtd_totals[m] = df_daily[(df_daily["Maker"] == m) & (df_daily["Date"].dt.month == _current_month)]["Registrations"].sum()

        mc1.metric("TVS Motor MTD", f"{mtd_totals.get('TVS Motor Company', 0):,}")
        mc2.metric("Bajaj Auto MTD", f"{mtd_totals.get('Bajaj Auto', 0):,}")
        mc3.metric("Ather Energy MTD", f"{mtd_totals.get('Ather Energy', 0):,}")
        mc4.metric("Ola Electric MTD", f"{mtd_totals.get('Ola Electric', 0):,}")

        st.markdown("---")
        st.subheader("📈 Month-to-Date Registration Trends")
        chart_view = st.radio(
            "Chart View Mode:", 
            ["Daily registrations", "Cumulative registrations (Running Total)"], 
            horizontal=True, 
            key="vahan_daily_view_mode"
        )

        # Plotly Daily/Cumulative comparison chart
        import plotly.graph_objects as go
        fig_daily = go.Figure()
        colors = {
            "Ola Electric": "#bc8cff",
            "TVS Motor Company": "#39d353",
            "Bajaj Auto": "#58a6ff",
            "Ather Energy": "#d29922",
        }
        
        df_current_month_only = df_daily[df_daily["Date"].dt.month == _current_month].copy()
        
        for maker in vahan.get_makers():
            maker_daily = df_current_month_only[df_current_month_only["Maker"] == maker].sort_values("Date")
            
            if chart_view == "Cumulative registrations (Running Total)":
                y_values = maker_daily["Registrations"].cumsum()
                hovertemplate_str = f"<b>{maker}</b><br>Date: %{{x}}<br>Cumulative: %{{y:,.0f}}<extra></extra>"
            else:
                y_values = maker_daily["Registrations"]
                hovertemplate_str = f"<b>{maker}</b><br>Date: %{{x}}<br>Daily: %{{y:,.0f}}<extra></extra>"
                
            width = 4 if maker == maker_name else 2
            opacity = 1.0 if (maker == maker_name or not maker_name) else 0.6
            
            fig_daily.add_trace(go.Scatter(
                x=maker_daily["Date"].dt.strftime("%b %d"),
                y=y_values,
                name=maker,
                mode="lines+markers",
                line=dict(color=colors.get(maker, "#8b949e"), width=width),
                marker=dict(size=8, opacity=opacity),
                opacity=opacity,
                hovertemplate=hovertemplate_str
            ))
            
        title_text = f"Cumulative Registrations — {_current_month_name} {_current_year} (MTD)" if chart_view == "Cumulative registrations (Running Total)" else f"Daily Registrations — {_current_month_name} {_current_year} (MTD)"
        yaxis_title = "Cumulative Registrations" if chart_view == "Cumulative registrations (Running Total)" else "Daily Registrations"
        
        fig_daily.update_layout(
            title=title_text,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Date", gridcolor="rgba(48,54,61,0.3)"),
            yaxis=dict(title=yaxis_title, gridcolor="rgba(48,54,61,0.3)"),
            height=400,
            margin=dict(l=40, r=40, t=50, b=40)
        )
        st.plotly_chart(fig_daily, use_container_width=True)
        
        # --- Previous Month vs Current Month Velocity Comparison ---
        st.markdown("---")
        st.subheader(f"📈 Previous Month ({_prev_month_name}) vs Current Month ({_current_month_name}) Daily Velocity")
        st.markdown(f"*Compare day-by-day (Day 1 to 30) registration pace for the selected OEM.*")
        
        # OEM select box
        available_oems = vahan.get_makers()
        default_idx = available_oems.index(maker_name) if maker_name in available_oems else 0
        comp_oem = st.selectbox("Select OEM to Compare:", available_oems, index=default_idx, key="vahan_comp_oem_selector")
        
        # Extract previous and current month data
        df_oem_daily = df_daily[df_daily["Maker"] == comp_oem].copy()
        
        # Split into previous and current month
        df_prev = df_oem_daily[df_oem_daily["Date"].dt.month == _prev_m].copy()
        df_curr = df_oem_daily[df_oem_daily["Date"].dt.month == _current_month].copy()
        
        # Get Day of Month
        if not df_prev.empty:
            df_prev["Day"] = df_prev["Date"].dt.day
            df_prev = df_prev.sort_values("Day")
        if not df_curr.empty:
            df_curr["Day"] = df_curr["Date"].dt.day
            df_curr = df_curr.sort_values("Day")
        
        # Create Comparative Chart
        fig_compare = go.Figure()
        
        # Previous Month Line
        if not df_prev.empty:
            fig_compare.add_trace(go.Scatter(
                x=df_prev["Day"],
                y=df_prev["Registrations"],
                name=f"{_prev_month_name} {_prev_y} (Previous Month)",
                mode="lines+markers",
                line=dict(color="#8b949e", width=2, dash="dash"),
                marker=dict(size=5),
                hovertemplate=f"{_prev_month_name} Day %{{x}}<br>Registrations: %{{y:,.0f}}<extra></extra>"
            ))
        
        # Current Month Line
        if not df_curr.empty:
            fig_compare.add_trace(go.Scatter(
                x=df_curr["Day"],
                y=df_curr["Registrations"],
                name=f"{_current_month_name} {_current_year} (Current Month)",
                mode="lines+markers",
                line=dict(color=colors.get(comp_oem, "#39d353"), width=4),
                marker=dict(size=8),
                hovertemplate=f"{_current_month_name} Day %{{x}}<br>Registrations: %{{y:,.0f}}<extra></extra>"
            ))
        
        fig_compare.update_layout(
            title=f"Daily Registration Velocity Comparison — {comp_oem}",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                title="Day of Month (1 to 30)", 
                gridcolor="rgba(48,54,61,0.3)",
                tickmode="linear",
                tick0=1,
                dtick=2
            ),
            yaxis=dict(title="Daily Registrations", gridcolor="rgba(48,54,61,0.3)"),
            height=380,
            margin=dict(l=40, r=40, t=50, b=40)
        )
        st.plotly_chart(fig_compare, use_container_width=True)
        st.markdown("---")
        
        # --- Display daily data table & links ---
        col_tbl, col_meta = st.columns([2, 1])
        with col_tbl:
            st.subheader("📋 Daily Registrations Table")
            st.dataframe(df_daily_pivot_display, width="stretch", hide_index=True)
            
        with col_meta:
            st.subheader("🔗 Vahan Daily Audit Guide")
            st.markdown(f"""
            - **Current Date:** {_today.strftime('%B %d, %Y')}
            - **Period:** {_current_month_name} 1, {_current_year} to {_current_month_name} {_today.day}, {_current_year}
            - **Data Type:** Cumulative MTD → daily interpolated
            
            To audit cumulative statistics on Vahan dashboard:
            1. Visit [Vahan Dashboard Portal](https://vahan.parivahan.gov.in/vahan4dashboard/vahan/view/reportview.xhtml)
            2. Choose **Y-Axis** as **'Maker'** and **X-Axis** as **'Month Wise'**
            3. Set **Fuel** filter to **'ELECTRIC'**
            4. Choose **Calendar Year** and year **'{_current_year}'**
            5. The page displays the cumulative MTD total registrations.
            
            💡 **Tip:** Paste the cumulative numbers from Vahan into the
            "Update Cumulative from Vahan Portal" panel above for exact accuracy.
            """)

# ═══════════════════════════════════════════════
# TAB 11: AI PREDICTOR & SCREENER
# ═══════════════════════════════════════════════
with tab11:
    st.subheader(f"🔮 AI Stock Trajectory & 10-Signal Forecast — {ticker_symbol}")
    st.markdown("*Institutional 10-Signal Matrix, Factor Neutralization, and Offline FinGPT / Gemini Trajectory Modeling.*")

    with st.spinner("Calculating 10-Signal Trajectory Score & Factor Neutralization..."):
        prediction = analyzer.predict_stock(ticker_symbol)

    if prediction:
        score = prediction.get("trajectory_score", 50.0)
        stance = prediction.get("stance", "Neutral")
        kelly_alloc = prediction.get("kelly_recommended_allocation_pct", 0.0)
        scenarios = prediction.get("scenarios", {})

        # Top Metrics Bar
        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        p_col1.metric("Trajectory Score", f"{score}/100")
        p_col2.metric("Research Stance", stance)
        p_col3.metric("Kelly Position Allocation", f"{kelly_alloc}%", help="Half-Kelly risk-adjusted portfolio position size limit")
        p_col4.metric("Bull Target (12M)", f"₹{scenarios.get('bull_case', {}).get('target_price', 0):,.1f}", delta=f"{scenarios.get('bull_case', {}).get('upside_pct', 0):+.1f}%")

        st.markdown("---")

        # Scenario Price Target Bands
        st.subheader("🎯 Scenario Price Target Bands")
        sc_col1, sc_col2, sc_col3 = st.columns(3)
        with sc_col1:
            st.success(f"**Bull Case**: ₹{scenarios.get('bull_case', {}).get('target_price', 0):,.1f} ({scenarios.get('bull_case', {}).get('upside_pct', 0):+.1f}%)")
        with sc_col2:
            st.info(f"**Base Case**: ₹{scenarios.get('base_case', {}).get('target_price', 0):,.1f} ({scenarios.get('base_case', {}).get('upside_pct', 0):+.1f}%)")
        with sc_col3:
            st.warning(f"**Bear Case**: ₹{scenarios.get('bear_case', {}).get('target_price', 0):,.1f} ({scenarios.get('bear_case', {}).get('downside_pct', 0):+.1f}%)")

        st.markdown("---")

        # 10-Signal Breakdown & Solvency Checks
        s_col1, s_col2 = st.columns([2, 1])

        with s_col1:
            st.subheader("📊 10-Signal Score Breakdown")
            breakdown = prediction.get("signal_breakdown", {})
            df_signals = pd.DataFrame([
                {"Signal": "Quantitative Fundamentals", "Score": breakdown.get("quant_fundamentals_score", 0)},
                {"Signal": "Concall Management Credibility", "Score": breakdown.get("concall_credibility_score", 0)},
                {"Signal": "Future Opportunities & Order Book", "Score": breakdown.get("future_opportunities_score", 0)},
                {"Signal": "Macro & Trending Themes", "Score": breakdown.get("macro_theme_score", 0)},
                {"Signal": "Deal Flow Disclosures", "Score": breakdown.get("deal_flow_score", 0)},
                {"Signal": "Competitive Intensity", "Score": breakdown.get("competitive_position_score", 0)},
                {"Signal": "Consensus Expectation Surprise Delta", "Score": breakdown.get("consensus_surprise_score", 0)},
                {"Signal": "Smart Money & Insider Sentiment", "Score": breakdown.get("smart_money_score", 0)},
                {"Signal": "PEAD & Institutional Accumulation", "Score": breakdown.get("pead_accumulation_score", 0)},
                {"Signal": "Corporate Governance Penalty", "Score": -breakdown.get("governance_penalty", 0)},
            ])
            st.dataframe(df_signals, width="stretch", hide_index=True)

        with s_col2:
            st.subheader("🕵️ Solvency & Insider Signals")
            st.write(f"- **Altman Z-Score**: `{prediction.get('altman_z_score', 'N/A')}` (Safe Zone)")
            st.write(f"- **Beneish M-Score**: `{prediction.get('beneish_m_score', 'N/A')}` (Clean Accounting)")
            st.write(f"- **Delivery Volume %**: `{prediction.get('delivery_volume_pct', 0)}%` (Strong Accumulation)")
            st.write(f"- **Promoter Open Market Buying**: `₹{prediction.get('promoter_buying_lakhs', 0)} Lakhs`")
            st.write(f"- **Promoter Pledge Risk**: `{prediction.get('promoter_pledge_pct', 0)}%`")

            # Backtesting hit-rate
            backtest_res = analyzer.backtest_engine.run_4q_backtest(ticker_symbol)
            st.info(f"🎯 **Model Precision**: {backtest_res['model_precision']} ({backtest_res['hit_rate_pct']}% Hit Rate over 4Q)")
    else:
        st.warning("⚠️ Prediction unavailable for this ticker. Check network connection or LLM model status.")

    st.markdown("---")

    # Upcoming Earnings Result Calendar Widget
    c_col1, c_col2 = st.columns([2, 1])
    with c_col1:
        st.subheader("📅 Upcoming NSE/BSE Earnings Results Calendar")
        calendar_df = analyzer.calendar_provider.get_upcoming_earnings_calendar()
        st.dataframe(calendar_df, width="stretch", hide_index=True)

    with c_col2:
        st.subheader("🔄 500-Stock Batch Queue")
        st.markdown("*Resumable pipeline checkpointing engine.*")
        if st.button("🚀 Run/Resume 500-Stock Batch Prediction"):
            with st.spinner("Processing batch queue..."):
                sample_universe = ["TVSMOTOR.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "RELIANCE.NS", "INFY.NS", "TCS.NS"]
                batch_res = analyzer.batch_predict_universe(sample_universe)
                st.success(f"Pipeline State: {batch_res['status']} | Processed: {batch_res['total_processed']} tickers!")

    st.markdown("---")
    st.subheader("📝 Live Execution Logs Console")
    
    # Clear logs functionality
    if st.button("🗑️ Clear Execution Logs"):
        import os
        if os.path.exists("data/pipeline.log"):
            os.remove("data/pipeline.log")
        st.success("Logs cleared successfully!")

    # Display logs
    import os
    if os.path.exists("data/pipeline.log"):
        with open("data/pipeline.log", "r") as f:
            log_lines = f.readlines()
        # Show last 25 lines of log console
        st.code("".join(log_lines[-25:]), language="text")
    else:
        st.info("No execution logs recorded yet. Run a single stock forecast or the batch queue to generate logs.")


# ═══════════════════════════════════════════════
# TAB 12: MUTUAL FUND STOCK HOLDINGS & INDEX EXPLORER
# ═══════════════════════════════════════════════
with tab12:
    mf_subtab1, mf_subtab2 = st.tabs([
        "🏦 Smart Money & Holdings Tracker",
        "🔍 Index Constituent Search & Drilldown"
    ])

    with mf_subtab1:
        render_mf_holdings_tab()

    with mf_subtab2:
        st.header("🏛️ Mutual Fund Stock Ownership & SEBI Index Explorer")
        st.markdown("Search any **NSE/BSE listed stock** to discover mutual fund scheme holdings, portfolio weight %, and month-over-month buying/selling actions.")

        mf_col1, mf_col2 = st.columns([2, 1])
        with mf_col1:
            mf_query = st.text_input("🔎 Search Stock by Symbol, Name, or Sector:", value="", placeholder="e.g. Reliance, HDFC, Polycab, BSE, Senco...", key="mf_search_q")
        with mf_col2:
            selected_tier = st.selectbox("Market Cap Tier Filter:", ["ALL", "LARGE_CAP", "MID_CAP", "SMALL_CAP", "MICRO_CAP"], index=0)

        tier_filter = None if selected_tier == "ALL" else selected_tier
        search_results = analyzer.search_stocks(query=mf_query, tier=tier_filter, limit=30)

        if search_results:
            st.subheader(f"Matching Index Stocks ({len(search_results)})")
            cols = st.columns(3)
            for idx, item in enumerate(search_results):
                with cols[idx % 3]:
                    tier_badge = item["tier"].replace("_", " ")
                    st.markdown(f"""
                    <div class="premium-card">
                        <span style="background: rgba(88,166,255,0.2); color: #58a6ff; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{tier_badge}</span>
                        <h4 style="margin: 8px 0 4px 0; color: #f0f6fc;">{item['symbol']}</h4>
                        <p style="font-size: 13px; color: #8b949e; margin-bottom: 8px;">{item['company_name']}</p>
                        <p style="font-size: 12px; color: #c9d1d9;"><b>Index:</b> {item['index_name']} | <b>Sector:</b> {item['sector']}</p>
                        <p style="font-size: 12px; color: #39d353;"><b>Holding MF Schemes:</b> {item['mf_scheme_count']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"View MF Breakdown: {item['symbol']}", key=f"btn_mf_{item['symbol']}"):
                        st.session_state.selected_mf_symbol = item['symbol']

        # Detail View for Selected Stock MF Ownership
        target_sym = st.session_state.get("selected_mf_symbol", ticker_symbol)
        st.markdown("---")
        st.subheader(f"📊 Mutual Fund Scheme Holdings Breakdown: `{target_sym}`")

        mf_data = analyzer.get_stock_mf_ownership(target_sym)
        if "error" not in mf_data:
            s_info = mf_data.get("stock_info", {})
            summary = mf_data.get("summary", {})
            holdings = mf_data.get("holdings_matrix", [])

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Holding Schemes", f"{summary.get('total_mf_schemes_holding', 0)} Schemes")
            m2.metric("Total MF Investment", f"₹{summary.get('total_mf_value_cr', 0):,.2f} Cr")
            m3.metric("Total Shares Held", f"{summary.get('total_mf_shares_held', 0):,} Shares")
            m4.metric("Net MoM Drift", f"{summary.get('net_mom_share_change', 0):+,} Shares", delta=summary.get("sentiment_signal"))

            if holdings:
                df_mf = pd.DataFrame(holdings)
                st.dataframe(df_mf[["scheme_name", "amc_name", "shares_held", "market_value_cr", "portfolio_weight_pct", "action_type", "mom_share_change"]], width="stretch", hide_index=True)
            else:
                st.info("No detailed mutual fund scheme breakdown available for this stock yet.")



