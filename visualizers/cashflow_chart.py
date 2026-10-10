"""
Cashflow Analysis Plotly Charts.
Builds interactive visualizations for CFO vs PAT, cash flow composition,
working capital cycle, and receivables vs revenue growth.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from models.cashflow import CashFlowPeriod


class CashflowChart:
    """Builds Plotly charts for cashflow analysis display."""

    @staticmethod
    def build_cfo_vs_pat(data: list[CashFlowPeriod]) -> go.Figure:
        """
        Dual bar chart: CFO vs Net Profit with Cash Conversion Ratio line overlay.
        This is the key chart — shows if profits are backed by cash.
        """
        if not data:
            return _empty_figure("No cash flow data available")

        periods = [p.period for p in data]
        cfo_vals = [p.cfo for p in data]
        pat_vals = [p.net_profit for p in data]
        ccr_vals = [p.cash_conversion_ratio for p in data]

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Net Profit bars
        fig.add_trace(go.Bar(
            x=periods, y=pat_vals,
            name="Net Profit (PAT)",
            marker_color="rgba(88, 166, 255, 0.7)",
            marker_line=dict(width=1, color="rgba(88, 166, 255, 1)"),
            hovertemplate="<b>%{x}</b><br>Net Profit: Rs %{y:,.0f} Cr<extra></extra>",
        ), secondary_y=False)

        # CFO bars
        fig.add_trace(go.Bar(
            x=periods, y=cfo_vals,
            name="Cash from Operations (CFO)",
            marker_color="rgba(57, 211, 83, 0.7)",
            marker_line=dict(width=1, color="rgba(57, 211, 83, 1)"),
            hovertemplate="<b>%{x}</b><br>CFO: Rs %{y:,.0f} Cr<extra></extra>",
        ), secondary_y=False)

        # CCR line
        ccr_clean = [v if v is not None else None for v in ccr_vals]
        if any(v is not None for v in ccr_clean):
            fig.add_trace(go.Scatter(
                x=periods, y=ccr_clean,
                name="Cash Conversion (CFO/PAT)",
                mode="lines+markers",
                line=dict(color="#d29922", width=3, dash="dot"),
                marker=dict(size=8, color="#d29922"),
                hovertemplate="<b>%{x}</b><br>CFO/PAT: %{y:.2f}x<extra></extra>",
            ), secondary_y=True)

            # Add 1.0x reference line
            fig.add_hline(y=1.0, line_dash="dash", line_color="rgba(139, 148, 158, 0.5)",
                          annotation_text="1.0x (ideal)", secondary_y=True)

        fig.update_layout(
            **_base_layout(),
            barmode="group",
            bargap=0.25,
            yaxis_title="Rs Cr",
            height=450,
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        )
        fig.update_yaxes(title_text="CFO/PAT Ratio", secondary_y=True,
                         gridcolor="rgba(0,0,0,0)")

        return fig

    @staticmethod
    def build_cashflow_composition(data: list[CashFlowPeriod]) -> go.Figure:
        """
        Stacked bar chart: Operating / Investing / Financing cash flows.
        Shows where cash comes from and goes.
        """
        if not data:
            return _empty_figure("No cash flow data available")

        periods = [p.period for p in data]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=periods, y=[p.cfo for p in data],
            name="Operating (CFO)",
            marker_color="rgba(57, 211, 83, 0.8)",
            hovertemplate="<b>%{x}</b><br>CFO: Rs %{y:,.0f} Cr<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=periods, y=[p.cfi for p in data],
            name="Investing (CFI)",
            marker_color="rgba(248, 81, 73, 0.8)",
            hovertemplate="<b>%{x}</b><br>CFI: Rs %{y:,.0f} Cr<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=periods, y=[p.cff for p in data],
            name="Financing (CFF)",
            marker_color="rgba(188, 140, 255, 0.8)",
            hovertemplate="<b>%{x}</b><br>CFF: Rs %{y:,.0f} Cr<extra></extra>",
        ))

        # Net cash flow line
        fig.add_trace(go.Scatter(
            x=periods, y=[p.net_cash_flow for p in data],
            name="Net Cash Flow",
            mode="lines+markers",
            line=dict(color="#d29922", width=2),
            marker=dict(size=7),
            hovertemplate="<b>%{x}</b><br>Net: Rs %{y:,.0f} Cr<extra></extra>",
        ))

        fig.add_hline(y=0, line_dash="solid", line_color="rgba(139, 148, 158, 0.5)")

        fig.update_layout(
            **_base_layout(),
            barmode="relative",
            yaxis_title="Rs Cr",
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        )

        return fig

    @staticmethod
    def build_working_capital_chart(data: list[CashFlowPeriod]) -> go.Figure:
        """
        Line chart showing Receivable Days, Payable Days, Inventory Days,
        and Net Working Capital Days over time.
        """
        has_wc = [p for p in data if p.receivable_days is not None or p.inventory_days is not None]
        if not has_wc:
            return _empty_figure("No working capital data available")

        periods = [p.period for p in has_wc]

        fig = go.Figure()

        recv_days = [p.receivable_days for p in has_wc]
        pay_days = [p.payable_days for p in has_wc]
        inv_days = [p.inventory_days for p in has_wc]
        wc_days = [p.working_capital_days for p in has_wc]

        if any(v is not None for v in recv_days):
            fig.add_trace(go.Scatter(
                x=periods, y=recv_days,
                name="Receivable Days (DSO)",
                mode="lines+markers",
                line=dict(color="#58a6ff", width=2),
                marker=dict(size=7),
                hovertemplate="<b>%{x}</b><br>DSO: %{y:.0f} days<extra></extra>",
            ))

        if any(v is not None for v in pay_days):
            fig.add_trace(go.Scatter(
                x=periods, y=pay_days,
                name="Payable Days (DPO)",
                mode="lines+markers",
                line=dict(color="#39d353", width=2),
                marker=dict(size=7),
                hovertemplate="<b>%{x}</b><br>DPO: %{y:.0f} days<extra></extra>",
            ))

        if any(v is not None for v in inv_days):
            fig.add_trace(go.Scatter(
                x=periods, y=inv_days,
                name="Inventory Days",
                mode="lines+markers",
                line=dict(color="#bc8cff", width=2),
                marker=dict(size=7),
                hovertemplate="<b>%{x}</b><br>Inventory: %{y:.0f} days<extra></extra>",
            ))

        if any(v is not None for v in wc_days):
            fig.add_trace(go.Scatter(
                x=periods, y=wc_days,
                name="Net Working Capital Cycle",
                mode="lines+markers",
                line=dict(color="#d29922", width=3),
                marker=dict(size=9, symbol="diamond"),
                fill="tozeroy",
                fillcolor="rgba(210, 153, 34, 0.1)",
                hovertemplate="<b>%{x}</b><br>WC Cycle: %{y:.0f} days<extra></extra>",
            ))

        fig.add_hline(y=0, line_dash="dash", line_color="rgba(139, 148, 158, 0.4)")

        fig.update_layout(
            **_base_layout(),
            yaxis_title="Days",
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        )

        return fig

    @staticmethod
    def build_receivable_vs_revenue_growth(data: list[CashFlowPeriod]) -> go.Figure:
        """
        Dual-axis chart: Receivable Growth % vs Revenue Growth %.
        When receivables outpace revenue, it signals credit-driven sales.
        """
        has_growth = [p for p in data
                      if p.receivable_growth_pct is not None and p.revenue_growth_pct is not None]
        if not has_growth:
            return _empty_figure("Insufficient data for growth comparison")

        periods = [p.period for p in has_growth]
        recv_g = [p.receivable_growth_pct for p in has_growth]
        rev_g = [p.revenue_growth_pct for p in has_growth]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=periods, y=rev_g,
            name="Revenue Growth %",
            marker_color="rgba(57, 211, 83, 0.7)",
            hovertemplate="<b>%{x}</b><br>Revenue Growth: %{y:+.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=periods, y=recv_g,
            name="Receivable Growth %",
            marker_color="rgba(248, 81, 73, 0.7)",
            hovertemplate="<b>%{x}</b><br>Receivable Growth: %{y:+.1f}%<extra></extra>",
        ))

        # Highlight danger zone
        for i, p in enumerate(has_growth):
            if (p.receivable_growth_pct is not None and p.revenue_growth_pct is not None
                    and p.receivable_growth_pct > p.revenue_growth_pct * 1.5
                    and p.receivable_growth_pct > 10):
                fig.add_annotation(
                    x=periods[i], y=p.receivable_growth_pct,
                    text="Credit Risk",
                    showarrow=True, arrowhead=2,
                    font=dict(color="#f85149", size=11, family="Inter"),
                    arrowcolor="#f85149",
                    yshift=15,
                )

        fig.add_hline(y=0, line_dash="solid", line_color="rgba(139, 148, 158, 0.5)")

        fig.update_layout(
            **_base_layout(),
            barmode="group",
            yaxis_title="Growth %",
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        )

        return fig

    @staticmethod
    def build_revenue_vs_cfo_growth(data: list[CashFlowPeriod]) -> go.Figure:
        """
        Dual-axis chart: Revenue Growth % vs CFO Growth %.
        Shows if operating cash generation is scaling with revenue.
        """
        has_growth = [p for p in data
                      if p.cfo_growth_pct is not None and p.revenue_growth_pct is not None]
        if not has_growth:
            return _empty_figure("Insufficient data for growth comparison")

        periods = [p.period for p in has_growth]
        rev_g = [p.revenue_growth_pct for p in has_growth]
        cfo_g = [p.cfo_growth_pct for p in has_growth]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=periods, y=rev_g,
            name="Revenue Growth %",
            marker_color="rgba(88, 166, 255, 0.7)",
            hovertemplate="<b>%{x}</b><br>Revenue Growth: %{y:+.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=periods, y=cfo_g,
            name="CFO Growth %",
            marker_color="rgba(57, 211, 83, 0.7)",
            hovertemplate="<b>%{x}</b><br>CFO Growth: %{y:+.1f}%<extra></extra>",
        ))

        fig.add_hline(y=0, line_dash="solid", line_color="rgba(139, 148, 158, 0.5)")

        fig.update_layout(
            **_base_layout(),
            barmode="group",
            yaxis_title="Growth %",
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        )

        return fig

    @staticmethod
    def build_fcf_trend(data: list[CashFlowPeriod]) -> go.Figure:
        """Free Cash Flow bar chart with cumulative line."""
        has_fcf = [p for p in data if p.free_cash_flow is not None]
        if not has_fcf:
            return _empty_figure("No free cash flow data available")

        periods = [p.period for p in has_fcf]
        fcf_vals = [p.free_cash_flow for p in has_fcf]

        # Cumulative FCF
        cumulative = []
        running = 0
        for v in fcf_vals:
            running += v
            cumulative.append(running)

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        colors = ["rgba(57, 211, 83, 0.7)" if v >= 0 else "rgba(248, 81, 73, 0.7)" for v in fcf_vals]

        fig.add_trace(go.Bar(
            x=periods, y=fcf_vals,
            name="Free Cash Flow",
            marker_color=colors,
            hovertemplate="<b>%{x}</b><br>FCF: Rs %{y:,.0f} Cr<extra></extra>",
        ), secondary_y=False)

        fig.add_trace(go.Scatter(
            x=periods, y=cumulative,
            name="Cumulative FCF",
            mode="lines+markers",
            line=dict(color="#58a6ff", width=2),
            marker=dict(size=6),
            hovertemplate="<b>%{x}</b><br>Cumulative: Rs %{y:,.0f} Cr<extra></extra>",
        ), secondary_y=True)

        fig.add_hline(y=0, line_dash="dash", line_color="rgba(139, 148, 158, 0.5)")

        fig.update_layout(
            **_base_layout(),
            yaxis_title="Rs Cr",
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        )
        fig.update_yaxes(title_text="Cumulative Rs Cr", secondary_y=True,
                         gridcolor="rgba(0,0,0,0)")

        return fig


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _base_layout() -> dict:
    return dict(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="rgba(48,54,61,0.4)"),
        yaxis=dict(gridcolor="rgba(48,54,61,0.4)", zeroline=True,
                   zerolinecolor="rgba(139, 148, 158, 0.3)"),
        margin=dict(l=40, r=20, t=30, b=80),
        font=dict(family="Inter, sans-serif"),
    )


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        annotations=[dict(text=message, showarrow=False,
                          font=dict(size=16, color="#8b949e"))],
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        height=300,
    )
    return fig
