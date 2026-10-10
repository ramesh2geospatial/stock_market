"""
Quarterly Visualizer Module.
Generates Plotly charts for dynamic N-quarter analysis:
- N-Quarter Rolling Cash Flow & PAT bar chart
- QoQ Revenue & Margin Divergence Heatmap / Dual-axis chart
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any


def plot_quarterly_cashflow_trajectory(cashflow_data: Dict[str, Any]) -> go.Figure:
    """Plot N-Quarter CFO, PAT, and FCF trajectory."""
    quarters = cashflow_data.get("quarters", [])
    if not quarters:
        fig = go.Figure()
        fig.add_annotation(text="No quarterly cashflow data available", showarrow=False)
        return fig

    labels = [q.get("quarter", "") for q in quarters]
    pat = [q.get("pat", 0.0) for q in quarters]
    est_cfo = [q.get("est_cfo", 0.0) for q in quarters]
    fcf = [q.get("fcf", 0.0) for q in quarters]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=pat, name="Net Profit (PAT) ₹ Cr", marker_color="#3b82f6"))
    fig.add_trace(go.Bar(x=labels, y=est_cfo, name="Est. Operating Cash Flow (CFO) ₹ Cr", marker_color="#10b981"))
    fig.add_trace(go.Scatter(x=labels, y=fcf, name="Free Cash Flow (FCF) ₹ Cr", mode="lines+markers", line=dict(color="#f59e0b", width=3)))

    fig.update_layout(
        title=f"Last {len(quarters)}-Quarter Cash Flow Trajectory (CFO vs PAT)",
        barmode="group",
        xaxis_title="Quarter",
        yaxis_title="₹ Cr",
        template="plotly_dark",
        margin=dict(l=40, r=40, t=50, b=40)
    )
    return fig


def plot_quarterly_divergence(divergence_data: Dict[str, Any]) -> go.Figure:
    """Plot QoQ Revenue growth and EBITDA margin delta across N quarters."""
    matrix = divergence_data.get("matrix", [])
    if not matrix:
        fig = go.Figure()
        fig.add_annotation(text="No quarterly divergence data available", showarrow=False)
        return fig

    labels = [q.get("quarter", "") for q in matrix]
    rev_growth = [q.get("qoq_revenue_growth_pct", 0.0) for q in matrix]
    margin_delta = [q.get("ebitda_margin_delta_bps", 0.0) for q in matrix]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(x=labels, y=rev_growth, name="QoQ Revenue Growth %", marker_color="#6366f1"),
        secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=labels, y=margin_delta, name="EBITDA Margin Delta (bps)", mode="lines+markers", line=dict(color="#ec4899", width=3)),
        secondary_y=True
    )

    fig.update_layout(
        title=f"Last {len(matrix)}-Quarter QoQ Growth & Margin Divergence",
        template="plotly_dark",
        margin=dict(l=40, r=40, t=50, b=40)
    )
    fig.update_yaxes(title_text="Revenue Growth %", secondary_y=False)
    fig.update_yaxes(title_text="Margin Delta (bps)", secondary_y=True)

    return fig
