"""
MF Holdings Tracker Tab — Streamlit Dashboard Component.

Provides Tab 12 in the main dashboard with:
1. Sync Status Bar (last sync time, row counts, sync button)
2. Market Cap Tier + Action Type Filters
3. Stock-level MF Holdings Summary Table with color-coded actions
4. Individual Stock Drilldown (scheme breakdown, pie chart, bar chart)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, List, Dict, Any
from datetime import datetime

from storage.sqlite_store import SQLiteStore
from services.mf_sync_service import MFHoldingsSyncService
from providers.mf_holdings_provider import MFHoldingsProvider
from backend_pipeline.etl.amc_holdings_scraper import AMCHoldingsEngine
from config import DB_PATH, MF_DEFAULT_TOP_N


def _get_sync_service() -> MFHoldingsSyncService:
    """Get or create MFHoldingsSyncService singleton in session state."""
    if "mf_sync_service" not in st.session_state:
        store = SQLiteStore(str(DB_PATH))
        provider = MFHoldingsProvider()
        st.session_state.mf_sync_service = MFHoldingsSyncService(provider=provider, store=store)
    return st.session_state.mf_sync_service


def _get_store() -> SQLiteStore:
    """Get or create SQLiteStore singleton in session state."""
    if "mf_sqlite_store" not in st.session_state:
        st.session_state.mf_sqlite_store = SQLiteStore(str(DB_PATH))
    return st.session_state.mf_sqlite_store


def _format_shares(n: int) -> str:
    """Format share count for display (e.g., 18.2M, 450K)."""
    if n is None:
        return "—"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif abs(n) >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _format_value(v: float) -> str:
    """Format market value in ₹ Cr."""
    if v is None:
        return "—"
    return f"₹{v:,.1f} Cr"


def _get_action_badge(action: str) -> str:
    """Return colored emoji badge for action type."""
    badges = {
        'STAKE_INCREASE': '🟢 Increased',
        'FRESH_ENTRY': '🆕 Fresh Entry',
        'STAKE_REDUCTION': '🔴 Decreased',
        'COMPLETE_EXIT': '⛔ Exit',
    }
    return badges.get(action, action)


def _get_dominant_action(row: Dict[str, Any]) -> str:
    """Determine dominant MF action for a stock based on scheme counts."""
    counts = {
        'FRESH_ENTRY': row.get('fresh_entry_count', 0) or 0,
        'STAKE_INCREASE': row.get('increase_count', 0) or 0,
        'STAKE_REDUCTION': row.get('decrease_count', 0) or 0,
        'COMPLETE_EXIT': row.get('exit_count', 0) or 0,
    }
    if counts['FRESH_ENTRY'] > 0 and counts['FRESH_ENTRY'] >= counts['STAKE_INCREASE']:
        return 'FRESH_ENTRY'
    if max(counts.values()) == 0:
        return 'STAKE_INCREASE'
    return max(counts, key=counts.get)


def _render_sync_status_bar(sync_service: MFHoldingsSyncService):
    """Render the sync status bar with last sync time and sync button."""
    status = sync_service.get_sync_status()

    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

    with col1:
        holdings_table = status.get("tables", {}).get("mf_stock_holdings", {})
        last_sync = holdings_table.get("last_synced_at", "Never")
        if last_sync and last_sync != "Never":
            try:
                dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                last_sync = dt.strftime("%d %b %Y, %I:%M %p")
            except (ValueError, TypeError):
                pass
        st.metric("Last Synced", last_sync)

    with col2:
        st.metric("Holdings Cached", f"{status.get('total_holdings_cached', 0):,}")

    with col3:
        st.metric("MF Schemes", f"{status.get('total_schemes_cached', 0):,}")

    with col4:
        col_sync, col_full = st.columns(2)
        with col_sync:
            if st.button("🔄 Sync", key="mf_sync_btn", use_container_width=True):
                with st.spinner("Syncing from Supabase..."):
                    result = sync_service.sync_all(force_full=False)
                    summary = result.get("summary", {})
                    if summary.get("status") == "success":
                        st.success(f"✅ Synced {summary.get('total_synced', 0)} new records")
                    else:
                        st.warning(f"⚠️ Partial sync: {summary}")
                    st.rerun()
        with col_full:
            if st.button("🔃 Full", key="mf_full_sync_btn", use_container_width=True):
                with st.spinner("Full sync from Supabase..."):
                    result = sync_service.sync_all(force_full=True)
                    summary = result.get("summary", {})
                    st.success(f"✅ Full sync: {summary.get('total_synced', 0)} records")
                    st.rerun()

    return status


def _render_filters(available_dates: List[str]) -> Dict[str, Any]:
    """Render filter controls and return selected filter values."""
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        date_options = available_dates if available_dates else ["No data"]
        selected_date = st.selectbox(
            "📅 As of Date",
            options=date_options,
            index=0,
            key="mf_date_filter"
        )

    with col2:
        action_options = ["STAKE_INCREASE", "FRESH_ENTRY", "STAKE_REDUCTION", "COMPLETE_EXIT"]
        selected_actions = st.multiselect(
            "📊 Action Type Filter",
            options=action_options,
            default=[],
            key="mf_action_filter",
            format_func=lambda x: _get_action_badge(x)
        )

    with col3:
        top_n = st.number_input(
            "Top N Stocks",
            min_value=5,
            max_value=100,
            value=MF_DEFAULT_TOP_N,
            step=5,
            key="mf_top_n"
        )

    return {
        "as_of_date": selected_date if selected_date != "No data" else None,
        "action_types": selected_actions if selected_actions else None,
        "top_n": top_n
    }


def _render_summary_table(store: SQLiteStore, filters: Dict[str, Any]):
    """Render the stock-level MF holdings summary table."""
    summary_data = store.get_mf_holdings_summary(
        as_of_date=filters.get("as_of_date"),
        action_types=filters.get("action_types")
    )

    if not summary_data:
        st.info("No MF holdings data found. Click '🔄 Sync' to fetch from Supabase.")
        return None

    df = pd.DataFrame(summary_data)

    # Add computed columns
    df['dominant_action'] = df.apply(lambda r: _get_dominant_action(r.to_dict()), axis=1)
    df['action_badge'] = df['dominant_action'].map(lambda x: _get_action_badge(x))
    df['shares_fmt'] = df['total_shares_held'].apply(
        lambda x: _format_shares(int(x)) if pd.notna(x) else '—'
    )
    df['value_fmt'] = df['total_market_value_cr'].apply(
        lambda x: _format_value(x) if pd.notna(x) else '—'
    )
    df['change_fmt'] = df['net_mom_change'].apply(
        lambda x: _format_shares(int(x)) if pd.notna(x) else '—'
    )

    # Sort by net MoM change (biggest accumulators first)
    df = df.sort_values('net_mom_change', ascending=False).head(
        filters.get('top_n', MF_DEFAULT_TOP_N)
    )

    # Display table
    display_df = df[[
        'symbol', 'scheme_count', 'shares_fmt', 'value_fmt', 'change_fmt',
        'action_badge', 'fresh_entry_count', 'increase_count',
        'decrease_count', 'exit_count'
    ]].copy()
    display_df.columns = [
        'Stock', 'MF Schemes', 'Total Shares', 'Market Value', 'MoM Change',
        'Signal', '🆕 Fresh', '🟢 Increased', '🔴 Decreased', '⛔ Exit'
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Stock': st.column_config.TextColumn('Stock', width='medium'),
            'MF Schemes': st.column_config.NumberColumn('MF Schemes', width='small'),
            'MoM Change': st.column_config.TextColumn('MoM Δ', width='small'),
            'Signal': st.column_config.TextColumn('Signal', width='medium'),
        }
    )

    return df


def _render_accumulation_distribution_charts(store: SQLiteStore, as_of_date: Optional[str]):
    """Render side-by-side bar charts for top accumulated and distributed stocks."""
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🟢 Top Accumulated")
        top_acc = store.get_top_accumulated_stocks(as_of_date=as_of_date, limit=10)
        if top_acc:
            df_acc = pd.DataFrame(top_acc)
            fig = px.bar(
                df_acc,
                x='symbol',
                y='net_accumulation',
                color_discrete_sequence=['#4CAF50'],
                labels={'net_accumulation': 'Net Shares Added', 'symbol': 'Stock'},
                title='Top 10 MF Accumulations'
            )
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No accumulation data available")

    with col2:
        st.subheader("🔴 Top Distributed")
        top_dist = store.get_top_distributed_stocks(as_of_date=as_of_date, limit=10)
        if top_dist:
            df_dist = pd.DataFrame(top_dist)
            df_dist['net_distribution_abs'] = df_dist['net_distribution'].abs()
            fig = px.bar(
                df_dist,
                x='symbol',
                y='net_distribution_abs',
                color_discrete_sequence=['#F44336'],
                labels={'net_distribution_abs': 'Net Shares Sold', 'symbol': 'Stock'},
                title='Top 10 MF Distributions'
            )
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No distribution data available")


def _render_stock_drilldown(
    store: SQLiteStore, selected_symbol: str, as_of_date: Optional[str]
):
    """Render detailed drilldown for a selected stock showing all MF scheme holdings."""
    st.subheader(f"📋 {selected_symbol} — MF Scheme Breakdown")

    holdings = store.get_mf_holdings_cache(symbol=selected_symbol, as_of_date=as_of_date)
    if not holdings:
        st.warning(f"No holdings data for {selected_symbol}")
        return

    # Join with scheme names
    schemes = {s['scheme_id']: s for s in store.get_mf_schemes_cache()}
    for h in holdings:
        scheme = schemes.get(h.get('scheme_id'), {})
        h['scheme_name'] = scheme.get('scheme_name', f"Scheme {h.get('scheme_id')}")
        h['amc_name'] = scheme.get('amc_name', 'Unknown AMC')

    df = pd.DataFrame(holdings)

    col1, col2 = st.columns(2)

    with col1:
        # Pie chart: scheme-wise ownership breakdown
        if 'market_value_cr' in df.columns and df['market_value_cr'].notna().any():
            fig_pie = px.pie(
                df,
                values='market_value_cr',
                names='scheme_name',
                title=f'{selected_symbol} — Ownership by Scheme (₹ Cr)',
                hole=0.4
            )
            fig_pie.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        # Bar chart: MoM share changes by scheme
        if 'mom_share_change' in df.columns:
            fig_bar = go.Figure()
            colors = [
                '#4CAF50' if x >= 0 else '#F44336'
                for x in df['mom_share_change'].fillna(0)
            ]
            fig_bar.add_trace(go.Bar(
                x=df['scheme_name'],
                y=df['mom_share_change'],
                marker_color=colors,
                text=df['mom_share_change'].apply(
                    lambda x: _format_shares(int(x)) if pd.notna(x) else '—'
                ),
                textposition='outside'
            ))
            fig_bar.update_layout(
                title=f'{selected_symbol} — MoM Share Changes by Scheme',
                xaxis_title='Scheme',
                yaxis_title='Share Change',
                height=350,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    # Detailed table
    display_cols = [
        'scheme_name', 'amc_name', 'shares_held', 'market_value_cr',
        'portfolio_weight_pct', 'mom_share_change', 'action_type'
    ]
    available_cols = [c for c in display_cols if c in df.columns]
    display_df = df[available_cols].copy()

    # Add action badge
    if 'action_type' in display_df.columns:
        display_df['Signal'] = display_df['action_type'].map(
            lambda x: _get_action_badge(x) if x else '—'
        )

    rename_map = {
        'scheme_name': 'Scheme', 'amc_name': 'AMC', 'shares_held': 'Shares Held',
        'market_value_cr': 'Value (₹ Cr)', 'portfolio_weight_pct': 'Weight %',
        'mom_share_change': 'MoM Change', 'action_type': 'Action'
    }
    display_df = display_df.rename(columns=rename_map)
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_mf_holdings_tab():
    """Main entry point — renders the complete MF Holdings Tracker tab."""
    st.header("🏦 Mutual Fund Holdings Tracker")
    st.caption(
        "Track Smart Money — which mutual funds are buying, selling, "
        "and initiating new positions in Indian stocks."
    )

    sync_service = _get_sync_service()
    store = _get_store()

    # Section 1: Sync Status Bar
    st.divider()
    status = _render_sync_status_bar(sync_service)

    # Section 2: Filters
    st.divider()
    available_dates = status.get("available_dates", [])
    filters = _render_filters(available_dates)

    # Section 3: Holdings Summary Table
    st.divider()
    st.subheader("📊 Stock-Level MF Holdings Summary")
    summary_df = _render_summary_table(store, filters)

    # Section 4: Accumulation vs Distribution Charts
    if summary_df is not None and not summary_df.empty:
        st.divider()
        _render_accumulation_distribution_charts(store, filters.get("as_of_date"))

    # Section 5: Stock Drilldown
    if summary_df is not None and not summary_df.empty:
        st.divider()
        stock_list = summary_df['symbol'].tolist()
        selected_stock = st.selectbox(
            "🔍 Select Stock for Drilldown",
            options=stock_list,
            key="mf_drilldown_stock"
        )
        if selected_stock:
            _render_stock_drilldown(store, selected_stock, filters.get("as_of_date"))

    # Section 6: Scheme Portfolio Explorer & Fund Overlap Calculator
    st.divider()
    _render_scheme_portfolio_explorer(store)


def _render_scheme_portfolio_explorer(store: SQLiteStore):
    """Render Scheme Portfolio Explorer & Fund Overlap Calculator."""
    st.subheader("🏢 Scheme Portfolio Explorer & Overlap Calculator")
    st.caption("View complete stock holdings for any Indian mutual fund scheme or compare portfolio overlap between funds.")

    schemes = store.get_mf_schemes_cache()
    if not schemes:
        st.info("No schemes available in local database.")
        return

    # Filter schemes that have holdings
    conn = store._conn()
    try:
        holding_counts = dict(conn.execute(
            "SELECT scheme_id, COUNT(*) FROM mf_holdings_cache GROUP BY scheme_id"
        ).fetchall())
    finally:
        conn.close()

    schemes_with_holdings = [
        s for s in schemes if holding_counts.get(s.get("scheme_id"), 0) > 0
    ]
    # Sort schemes by holdings count descending, then name
    schemes_with_holdings.sort(
        key=lambda s: (-holding_counts.get(s.get("scheme_id"), 0), s.get("scheme_name", ""))
    )

    if not schemes_with_holdings:
        schemes_with_holdings = schemes

    scheme_labels = {
        s["scheme_id"]: f"{s.get('scheme_name')} ({s.get('amc_name')}) — {holding_counts.get(s['scheme_id'], 0)} stocks"
        for s in schemes_with_holdings
    }

    tab_explore, tab_overlap = st.tabs(["📋 Scheme Holdings Master", "🔄 Portfolio Overlap Calculator"])

    with tab_explore:
        selected_sid = st.selectbox(
            "Select Mutual Fund Scheme:",
            options=list(scheme_labels.keys()),
            format_func=lambda x: scheme_labels.get(x, f"Scheme {x}"),
            key="mf_selected_scheme_explore"
        )

        if selected_sid:
            holdings_res = AMCHoldingsEngine.get_holdings(str(selected_sid))
            s_name = holdings_res.get("scheme_name", f"Scheme {selected_sid}")
            amc = holdings_res.get("amc", "")
            cat = holdings_res.get("category", "Equity")
            holdings_list = holdings_res.get("holdings", [])

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Scheme", s_name[:28] + ("..." if len(s_name) > 28 else ""))
            c2.metric("Fund House", amc)
            c3.metric("Category", cat)
            c4.metric("Holdings Count", f"{len(holdings_list)} stocks")

            if holdings_list:
                df_h = pd.DataFrame(holdings_list)
                
                # Visual charts
                c_pie, c_bar = st.columns(2)
                with c_pie:
                    if "sector" in df_h.columns and df_h["weight_pct"].sum() > 0:
                        sec_df = df_h.groupby("sector")["weight_pct"].sum().reset_index()
                        fig_sec = px.pie(
                            sec_df, values="weight_pct", names="sector",
                            title="Sector Allocation (%)", hole=0.4
                        )
                        fig_sec.update_layout(height=320, margin=dict(l=10, r=10, t=35, b=10))
                        st.plotly_chart(fig_sec, use_container_width=True)

                with c_bar:
                    if "weight_pct" in df_h.columns:
                        top10_df = df_h.head(10)
                        fig_w = px.bar(
                            top10_df, x="stock_name", y="weight_pct",
                            color="weight_pct", color_continuous_scale="Viridis",
                            labels={"stock_name": "Stock", "weight_pct": "Weight %"},
                            title="Top 10 Holdings by Weight (%)"
                        )
                        fig_w.update_layout(height=320, margin=dict(l=10, r=10, t=35, b=10), showlegend=False)
                        st.plotly_chart(fig_w, use_container_width=True)

                # Holdings Table
                st.markdown(f"**All {len(holdings_list)} Holdings for {s_name}:**")
                table_cols = ["stock_name", "sector", "weight_pct", "market_value_cr", "shares_held", "action"]
                available = [c for c in table_cols if c in df_h.columns]
                display_h = df_h[available].copy()
                rename_dict = {
                    "stock_name": "Stock Name", "sector": "Sector", "weight_pct": "Weight %",
                    "market_value_cr": "Value (₹ Cr)", "shares_held": "Shares Held", "action": "Action Signal"
                }
                display_h = display_h.rename(columns=rename_dict)
                st.dataframe(display_h, use_container_width=True, hide_index=True)
            else:
                st.info("No holdings recorded yet for this scheme.")

    with tab_overlap:
        st.markdown("*Compare the common stock portfolio overlap between two mutual funds to avoid portfolio duplication.*")
        col_fa, col_fb = st.columns(2)
        all_ids = list(scheme_labels.keys())
        default_b_idx = 1 if len(all_ids) > 1 else 0

        with col_fa:
            sid_a = st.selectbox(
                "Scheme A:",
                options=all_ids,
                index=0,
                format_func=lambda x: scheme_labels.get(x, f"Scheme {x}"),
                key="mf_overlap_scheme_a"
            )
        with col_fb:
            sid_b = st.selectbox(
                "Scheme B:",
                options=all_ids,
                index=default_b_idx,
                format_func=lambda x: scheme_labels.get(x, f"Scheme {x}"),
                key="mf_overlap_scheme_b"
            )

        if sid_a and sid_b:
            overlap_res = AMCHoldingsEngine.calculate_portfolio_overlap(str(sid_a), str(sid_b))
            o_pct = overlap_res.get("overlap_pct", 0.0)
            common_count = overlap_res.get("common_stock_count", 0)

            ov_c1, ov_c2, ov_c3 = st.columns(3)
            ov_c1.metric("Portfolio Overlap %", f"{o_pct}%")
            ov_c2.metric("Common Stocks", f"{common_count} stocks")
            ov_c3.metric("Diversification Status", "High Overlap ⚠️" if o_pct > 30 else "Good Diversification 🟢")

            common_list = overlap_res.get("common_stocks", [])
            if common_list:
                df_common = pd.DataFrame(common_list)
                f_a_label = overlap_res.get('fund_a', 'Fund A')[:15]
                f_b_label = overlap_res.get('fund_b', 'Fund B')[:15]
                df_common = df_common.rename(columns={
                    "stock_name": "Common Stock",
                    "weight_in_fund_a": f"Weight in {f_a_label} %",
                    "weight_in_fund_b": f"Weight in {f_b_label} %",
                    "overlap_contribution": "Overlap Contribution %"
                })
                st.dataframe(df_common, use_container_width=True, hide_index=True)
            else:
                st.info("Zero common stocks found between these two schemes. Full diversification!")
