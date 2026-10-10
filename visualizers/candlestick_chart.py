"""
Reusable TradingView-grade Plotly candlestick chart with volume subplot and EMA overlays.
"""
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class CandlestickChart:
    """Builds interactive candlestick charts with technical overlays and volume subplot."""

    @staticmethod
    def build(
        df: pd.DataFrame,
        days: int = 365,
        show_50_ema: bool = False,
        show_200_ema: bool = False,
        show_volume: bool = True,
    ) -> go.Figure:
        """
        Build a candlestick chart from historical OHLCV data with volume subplot.
        """
        if df.empty:
            fig = go.Figure()
            fig.update_layout(
                annotations=[
                    dict(
                        text="No historical data available",
                        showarrow=False,
                        font=dict(size=16, color="#8b949e"),
                    )
                ],
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                height=480,
            )
            return fig

        cutoff = datetime.now() - pd.Timedelta(days=days)
        date_col = pd.to_datetime(df["Date"]).dt.tz_localize(None)
        plot_df = df[date_col >= cutoff].copy()

        has_volume = show_volume and "Volume" in plot_df.columns and plot_df["Volume"].sum() > 0

        if has_volume:
            fig = make_subplots(
                rows=2,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.75, 0.25],
            )
        else:
            fig = go.Figure()

        # Candlestick Trace
        candlestick = go.Candlestick(
            x=plot_df["Date"],
            open=plot_df["Open"],
            high=plot_df["High"],
            low=plot_df["Low"],
            close=plot_df["Close"],
            name="OHLC",
            increasing=dict(line=dict(color="#22c55e"), fillcolor="#22c55e"),
            decreasing=dict(line=dict(color="#ef4444"), fillcolor="#ef4444"),
        )

        if has_volume:
            fig.add_trace(candlestick, row=1, col=1)
        else:
            fig.add_trace(candlestick)

        # Technical EMA Overlays
        if show_50_ema and "Close" in df.columns:
            ema_50 = df["Close"].ewm(span=50, adjust=False).mean()
            trace_50 = go.Scatter(
                x=plot_df["Date"],
                y=ema_50.loc[plot_df.index],
                mode="lines",
                line=dict(color="#38bdf8", width=1.75),
                name="50 EMA",
            )
            if has_volume:
                fig.add_trace(trace_50, row=1, col=1)
            else:
                fig.add_trace(trace_50)

        if show_200_ema and "Close" in df.columns:
            ema_200 = df["Close"].ewm(span=200, adjust=False).mean()
            trace_200 = go.Scatter(
                x=plot_df["Date"],
                y=ema_200.loc[plot_df.index],
                mode="lines",
                line=dict(color="#fbbf24", width=2.0),
                name="200 EMA",
            )
            if has_volume:
                fig.add_trace(trace_200, row=1, col=1)
            else:
                fig.add_trace(trace_200)

        # Volume Histogram Subplot
        if has_volume:
            vol_colors = [
                "#22c55e" if close >= op else "#ef4444"
                for close, op in zip(plot_df["Close"], plot_df["Open"])
            ]
            vol_trace = go.Bar(
                x=plot_df["Date"],
                y=plot_df["Volume"],
                name="Volume",
                marker=dict(color=vol_colors, opacity=0.7),
                showlegend=False,
            )
            fig.add_trace(vol_trace, row=2, col=1)
            fig.update_yaxes(title_text="Vol", row=2, col=1, showgrid=False)

        fig.update_layout(
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,23,42,0.6)",
            height=480,
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor="rgba(0,0,0,0)",
            ),
        )

        return fig

