"""
Interactive Plotly spider/radar chart for 10-quarter evolution.
Supports multi-quarter comparison, animated playback, and target overlay.
"""
import plotly.graph_objects as go
from models.analysis import QuarterSpiderData
from config import SPIDER_DIMENSIONS

# Color palette — older quarters more transparent, latest is bold
QUARTER_COLORS = [
    "rgba(88, 166, 255, 0.20)",   # Q1 (oldest)
    "rgba(88, 166, 255, 0.28)",
    "rgba(88, 166, 255, 0.36)",
    "rgba(88, 166, 255, 0.44)",
    "rgba(88, 166, 255, 0.52)",
    "rgba(88, 166, 255, 0.60)",
    "rgba(88, 166, 255, 0.68)",
    "rgba(57, 211, 83, 0.60)",
    "rgba(57, 211, 83, 0.75)",
    "rgba(57, 211, 83, 0.95)",    # Q10 (latest, bold green)
]

QUARTER_LINE_COLORS = [
    "rgba(88, 166, 255, 0.35)",
    "rgba(88, 166, 255, 0.42)",
    "rgba(88, 166, 255, 0.50)",
    "rgba(88, 166, 255, 0.58)",
    "rgba(88, 166, 255, 0.65)",
    "rgba(88, 166, 255, 0.72)",
    "rgba(88, 166, 255, 0.80)",
    "rgba(57, 211, 83, 0.70)",
    "rgba(57, 211, 83, 0.85)",
    "rgba(57, 211, 83, 1.0)",
]


class SpiderChart:
    """Builds interactive Plotly radar charts for quarter-over-quarter analysis."""

    @staticmethod
    def build_comparison(
        spider_data: list[QuarterSpiderData],
        selected_quarters: list[str] = None,
        show_target: bool = False,
        target_scores: list[float] = None,
    ) -> go.Figure:
        """
        Build a radar chart comparing selected quarters.
        If no quarters selected, shows latest 3.
        """
        if not spider_data:
            return SpiderChart._empty_figure("No quarterly data available")

        # Derive categories from metrics if present, else default
        categories = [m.name for m in spider_data[0].metrics] if (spider_data and spider_data[0].metrics) else SPIDER_DIMENSIONS
        # Close the polygon by repeating first category
        theta = categories + [categories[0]]

        # Filter to selected quarters
        if selected_quarters:
            data_to_plot = [d for d in spider_data if d.quarter in selected_quarters]
        else:
            data_to_plot = spider_data[-3:]  # Default: latest 3

        fig = go.Figure()

        total_q = len(spider_data)
        for qd in data_to_plot:
            scores = [m.score for m in qd.metrics]
            if not scores:
                continue
            r_values = scores + [scores[0]]  # Close polygon

            # Determine color index
            try:
                idx = [d.quarter for d in spider_data].index(qd.quarter)
                color_idx = min(idx, len(QUARTER_COLORS) - 1)
            except ValueError:
                color_idx = len(QUARTER_COLORS) - 1

            # Build hover text with raw values and trends
            hover_texts = []
            for m in qd.metrics:
                arrow = "↑" if m.trend == "up" else "↓" if m.trend == "down" else "→"
                hover_texts.append(
                    f"<b>{m.name}</b><br>"
                    f"Score: {m.score:.0f}/100<br>"
                    f"Value: {m.raw_value or 'N/A'}<br>"
                    f"Trend: {arrow}"
                )
            hover_texts.append(hover_texts[0])  # Close polygon

            fig.add_trace(go.Scatterpolar(
                r=r_values,
                theta=theta,
                fill="toself",
                name=f"{qd.quarter} (Score: {qd.overall_score:.0f})",
                line=dict(color=QUARTER_LINE_COLORS[color_idx], width=2),
                fillcolor=QUARTER_COLORS[color_idx],
                hovertext=hover_texts,
                hoverinfo="text",
            ))

        # Target overlay
        if show_target and target_scores:
            target_r = target_scores + [target_scores[0]]
            fig.add_trace(go.Scatterpolar(
                r=target_r,
                theta=theta,
                fill="none",
                name="Management Target",
                line=dict(color="rgba(248, 81, 73, 0.9)", dash="dash", width=2.5),
                hovertemplate="%{theta}: Target %{r:.0f}<extra>Target</extra>",
            ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True, range=[0, 100],
                    tickvals=[20, 40, 60, 80, 100],
                    gridcolor="rgba(48, 54, 61, 0.6)",
                    linecolor="rgba(48, 54, 61, 0.3)",
                ),
                angularaxis=dict(
                    gridcolor="rgba(48, 54, 61, 0.4)",
                    linecolor="rgba(48, 54, 61, 0.3)",
                ),
                bgcolor="rgba(0,0,0,0)",
            ),
            showlegend=True,
            legend=dict(
                orientation="h", yanchor="bottom", y=-0.2,
                xanchor="center", x=0.5,
                font=dict(size=11, color="#8b949e"),
            ),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=60, r=60, t=30, b=80),
            height=520,
        )

        return fig

    @staticmethod
    def build_animated(spider_data: list[QuarterSpiderData]) -> go.Figure:
        """
        Build an animated radar chart that plays through all quarters.
        """
        valid_data = [d for d in spider_data if d.metrics]
        if not valid_data:
            return SpiderChart._empty_figure("No quarterly metrics available")

        categories = [m.name for m in valid_data[0].metrics] or SPIDER_DIMENSIONS
        theta = categories + [categories[0]]

        # Initial frame: first quarter
        first = valid_data[0]
        first_scores = [m.score for m in first.metrics]
        initial_r = first_scores + [first_scores[0]]

        fig = go.Figure(
            data=[go.Scatterpolar(
                r=initial_r,
                theta=theta,
                fill="toself",
                name=first.quarter,
                line=dict(color="rgba(57, 211, 83, 0.9)", width=2.5),
                fillcolor="rgba(57, 211, 83, 0.2)",
            )]
        )

        # Create frames for each quarter
        frames = []
        for qd in valid_data:
            scores = [m.score for m in qd.metrics]
            r_vals = scores + [scores[0]]
            frames.append(go.Frame(
                data=[go.Scatterpolar(
                    r=r_vals,
                    theta=theta,
                    fill="toself",
                    name=qd.quarter,
                    line=dict(color="rgba(57, 211, 83, 0.9)", width=2.5),
                    fillcolor="rgba(57, 211, 83, 0.2)",
                )],
                name=qd.quarter,
            ))

        fig.frames = frames

        # Animation controls
        fig.update_layout(
            updatemenus=[dict(
                type="buttons",
                showactive=False,
                y=1.12, x=0.5, xanchor="center",
                buttons=[
                    dict(
                        label="▶ Play Evolution",
                        method="animate",
                        args=[None, {
                            "frame": {"duration": 900, "redraw": True},
                            "fromcurrent": True,
                            "transition": {"duration": 400, "easing": "cubic-in-out"},
                        }],
                    ),
                    dict(
                        label="⏸ Pause",
                        method="animate",
                        args=[[None], {"frame": {"duration": 0}, "mode": "immediate"}],
                    ),
                ],
                font=dict(color="#f0f6fc"),
                bgcolor="rgba(22, 27, 34, 0.8)",
                bordercolor="#30363d",
            )],
            sliders=[dict(
                active=0,
                currentvalue={"prefix": "Quarter: ", "font": {"color": "#58a6ff", "size": 14}},
                pad={"t": 40},
                steps=[
                    dict(args=[[qd.quarter], {"frame": {"duration": 300}, "mode": "immediate"}],
                         method="animate", label=qd.quarter)
                    for qd in spider_data
                ],
                font=dict(color="#8b949e"),
                bgcolor="rgba(22, 27, 34, 0.5)",
                bordercolor="#30363d",
                activebgcolor="#58a6ff",
            )],
            polar=dict(
                radialaxis=dict(
                    visible=True, range=[0, 100],
                    tickvals=[20, 40, 60, 80, 100],
                    gridcolor="rgba(48, 54, 61, 0.6)",
                ),
                angularaxis=dict(gridcolor="rgba(48, 54, 61, 0.4)"),
                bgcolor="rgba(0,0,0,0)",
            ),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=60, r=60, t=60, b=100),
            height=580,
        )

        return fig

    @staticmethod
    def build_score_trend(spider_data: list[QuarterSpiderData]) -> go.Figure:
        """Build a line chart showing overall score evolution across quarters."""
        if not spider_data:
            return SpiderChart._empty_figure("No data")

        quarters = [d.quarter for d in spider_data]
        scores = [d.overall_score for d in spider_data]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=quarters, y=scores,
            mode="lines+markers",
            name="Overall Score",
            line=dict(color="#58a6ff", width=3),
            marker=dict(size=10, color="#58a6ff"),
            fill="tozeroy",
            fillcolor="rgba(88, 166, 255, 0.1)",
            hovertemplate="<b>%{x}</b><br>Score: %{y:.1f}/100<extra></extra>",
        ))

        # Add dimension-level traces
        for dim_idx, dim_name in enumerate(SPIDER_DIMENSIONS):
            dim_scores = []
            for qd in spider_data:
                if dim_idx < len(qd.metrics):
                    dim_scores.append(qd.metrics[dim_idx].score)
                else:
                    dim_scores.append(0)

            fig.add_trace(go.Scatter(
                x=quarters, y=dim_scores,
                mode="lines",
                name=dim_name,
                line=dict(width=1.5, dash="dot"),
                opacity=0.6,
                visible="legendonly",
                hovertemplate=f"<b>{dim_name}</b><br>%{{x}}: %{{y:.1f}}<extra></extra>",
            ))

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Quarter", gridcolor="rgba(48,54,61,0.4)"),
            yaxis=dict(title="Score (0-100)", range=[0, 100], gridcolor="rgba(48,54,61,0.4)"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
            height=400,
            margin=dict(l=40, r=20, t=20, b=80),
        )

        return fig

    @staticmethod
    def _empty_figure(message: str) -> go.Figure:
        fig = go.Figure()
        fig.update_layout(
            annotations=[dict(text=message, showarrow=False, font=dict(size=16, color="#8b949e"))],
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            height=400,
        )
        return fig
