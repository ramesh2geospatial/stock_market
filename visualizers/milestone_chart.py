"""
Milestone timeline chart — Plotly timeline/Gantt showing
how management concerns and milestones evolve across quarters.
"""
import datetime
import re

import plotly.graph_objects as go
from models.analysis import SentimentResult

STATUS_COLORS = {
    "Concern": "#f85149",
    "In Progress": "#58a6ff",
    "Almost Resolved": "#d29922",
    "Resolved": "#39d353",
    "Milestone Achieved": "#39d353",
    "Future Target": "#bc8cff",
}


class MilestoneChart:
    """Builds interactive milestone tracking visualizations."""

    @staticmethod
    def _parse_quarter_to_date(quarter_str: str):
        """Parse Q-FY or month-year labels into sortable dates."""
        quarter_str = (quarter_str or "").strip()
        if not quarter_str:
            return datetime.date(2000, 1, 1)

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

        text = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", quarter_str, flags=re.I)
        text = text.replace(",", " ")
        text = re.sub(r"\s+", " ", text).strip()
        for fmt in ("%d %b %Y", "%d %B %Y", "%b %Y", "%B %Y", "%Y-%m-%d"):
            try:
                parsed = datetime.datetime.strptime(text, fmt).date()
                return parsed.replace(day=1)
            except ValueError:
                continue

        return datetime.date(2000, 1, 1)

    @staticmethod
    def _format_quarter_date(quarter: str, transcript_date: str = "") -> str:
        if transcript_date and transcript_date not in quarter:
            return f"{quarter} ({transcript_date})"
        return quarter

    @staticmethod
    def build_timeline(analyses: list[SentimentResult]) -> go.Figure:
        """
        Build a horizontal grouped bar chart showing milestones, concerns,
        and targets across quarters.
        """
        if not analyses:
            fig = go.Figure()
            fig.update_layout(
                annotations=[dict(text="No concall analysis data available",
                                  showarrow=False, font=dict(size=16, color="#8b949e"))],
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                height=400,
            )
            return fig

        # Chronological timeline display (oldest first)
        sorted_analyses = sorted(analyses, key=lambda a: MilestoneChart._parse_quarter_to_date(a.quarter))
        quarters = [a.quarter for a in sorted_analyses]

        # Collect all unique items across all quarters
        milestone_items = []
        concern_items = []
        target_items = []

        for a in sorted_analyses:
            for m in a.milestones_achieved:
                milestone_items.append({"quarter": a.quarter, "text": m, "type": "Milestone Achieved"})
            for c in a.concerns:
                concern_items.append({"quarter": a.quarter, "text": c, "type": "Concern"})
            for t in a.future_targets:
                target_items.append({"quarter": a.quarter, "text": t, "type": "Future Target"})

        fig = go.Figure()

        # Sentiment score bar chart across quarters
        fig.add_trace(go.Bar(
            x=quarters,
            y=[a.sentiment_score for a in sorted_analyses],
            name="Sentiment Score",
            marker=dict(
                color=[STATUS_COLORS["Resolved"] if s.sentiment_score > 0.15
                       else STATUS_COLORS["Concern"] if s.sentiment_score < -0.15
                       else STATUS_COLORS["In Progress"]
                       for s in sorted_analyses],
                line=dict(width=1, color="rgba(48, 54, 61, 0.8)"),
            ),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Transcript: %{customdata[1]}<br>"
                "Sentiment: %{y:.2f}<br>"
                "Tone: %{customdata[0]}<extra></extra>"
            ),
            customdata=[
                [a.management_tone, a.transcript_date or "N/A"]
                for a in sorted_analyses
            ],
        ))

        # Add count indicators as scatter markers
        milestone_counts = []
        concern_counts = []
        target_counts = []

        for a in sorted_analyses:
            milestone_counts.append(len(a.milestones_achieved))
            concern_counts.append(len(a.concerns))
            target_counts.append(len(a.future_targets))

        # Scale markers to max sentiment range
        max_val = 1.1

        if any(c > 0 for c in milestone_counts):
            fig.add_trace(go.Scatter(
                x=quarters,
                y=[max_val] * len(quarters),
                mode="markers+text",
                marker=dict(
                    size=[max(8, c * 6) for c in milestone_counts],
                    color=STATUS_COLORS["Milestone Achieved"],
                    symbol="diamond",
                ),
                text=[f"🏆{c}" if c > 0 else "" for c in milestone_counts],
                textposition="top center",
                textfont=dict(size=10, color="#39d353"),
                name="Milestones",
                customdata=[a.transcript_date or "N/A" for a in sorted_analyses],
                hovertemplate="<b>%{x}</b><br>Transcript: %{customdata}<br>Milestones: %{text}<extra></extra>",
            ))

        if any(c > 0 for c in concern_counts):
            fig.add_trace(go.Scatter(
                x=quarters,
                y=[-max_val] * len(quarters),
                mode="markers+text",
                marker=dict(
                    size=[max(8, c * 6) for c in concern_counts],
                    color=STATUS_COLORS["Concern"],
                    symbol="triangle-down",
                ),
                text=[f"⚠{c}" if c > 0 else "" for c in concern_counts],
                textposition="bottom center",
                textfont=dict(size=10, color="#f85149"),
                name="Concerns",
                customdata=[a.transcript_date or "N/A" for a in sorted_analyses],
                hovertemplate="<b>%{x}</b><br>Transcript: %{customdata}<br>Concerns: %{text}<extra></extra>",
            ))

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Quarter", gridcolor="rgba(48,54,61,0.4)"),
            yaxis=dict(
                title="Sentiment Score",
                range=[-1.5, 1.5],
                gridcolor="rgba(48,54,61,0.4)",
                zeroline=True,
                zerolinecolor="rgba(139, 148, 158, 0.5)",
                zerolinewidth=1,
            ),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
            height=450,
            margin=dict(l=40, r=20, t=30, b=80),
            bargap=0.3,
        )

        return fig

    @staticmethod
    def build_detail_cards(analyses: list[SentimentResult]) -> list[dict]:
        """
        Return structured data for rendering detail cards in Streamlit.
        Each card contains quarter info, sentiment, highlights, concerns, milestones, targets,
        and enhanced fields (financial metrics, management quotes, analyst concerns, guidance).
        """
        cards = []
        for a in sorted(
            analyses,
            key=lambda item: MilestoneChart._parse_quarter_to_date(item.quarter),
            reverse=True,
        ):
            tone_color = (
                "#39d353" if a.sentiment_label == "Positive"
                else "#f85149" if a.sentiment_label == "Negative"
                else "#8b949e"
            )
            cards.append({
                "quarter": MilestoneChart._format_quarter_date(a.quarter, a.transcript_date),
                "transcript_date": a.transcript_date,
                "score": a.sentiment_score,
                "label": a.sentiment_label,
                "tone": a.management_tone,
                "tone_color": tone_color,
                "highlights": a.key_highlights,
                "concerns": a.concerns,
                "milestones": a.milestones_achieved,
                "targets": a.future_targets,
                "analyzer": a.analyzer_type,
                # Enhanced fields
                "revenue_growth_pct": a.revenue_growth_pct,
                "ebitda_margin_pct": a.ebitda_margin_pct,
                "pat_growth_pct": a.pat_growth_pct,
                "management_quotes": a.management_quotes or [],
                "analyst_concerns": a.analyst_concerns or [],
                "guidance_numbers": a.guidance_numbers or {},
                # NEW enhanced fields
                "revenue_absolute": a.revenue_absolute,
                "ebitda_absolute": a.ebitda_absolute,
                "pat_absolute": a.pat_absolute,
                "segment_data": a.segment_data or [],
                "net_debt_cr": a.net_debt_cr,
                "capex_actual_cr": a.capex_actual_cr,
                "prior_guidance_met": a.prior_guidance_met or [],
                "prior_guidance_missed": a.prior_guidance_missed or [],
                # Cross-validation fields
                "data_confidence": a.data_confidence,
                "corrections": a.corrections or [],
                # 8 Institutional Concall Analysis Sections
                "key_takeaways": a.key_takeaways or [],
                "volume_yield_flywheel": a.volume_yield_flywheel or [],
                "productivity_efficiency": a.productivity_efficiency or [],
                "margin_architecture": a.margin_architecture or [],
                "customer_segmentation": a.customer_segmentation or [],
                "capital_allocation": a.capital_allocation or [],
                "guidance_commitments": a.guidance_commitments or [],
                "key_operational_metrics": a.key_operational_metrics or {},
            })
        return cards

    @staticmethod
    def build_financial_progression_chart(analyses: list[SentimentResult]) -> go.Figure:
        """
        Build a multi-axis chart showing revenue, EBITDA margin, and PAT progression
        across quarters along with sentiment score overlay.
        """
        sorted_analyses = sorted(analyses, key=lambda a: MilestoneChart._parse_quarter_to_date(a.quarter))
        quarters = [a.quarter for a in sorted_analyses]

        fig = go.Figure()

        # Revenue bars
        revenues = [a.revenue_absolute for a in sorted_analyses]
        if any(r is not None for r in revenues):
            fig.add_trace(go.Bar(
                x=quarters,
                y=[r or 0 for r in revenues],
                name="Revenue (Rs Cr)",
                marker=dict(color="rgba(88, 166, 255, 0.7)", line=dict(width=1, color="rgba(88, 166, 255, 1)")),
                hovertemplate="<b>%{x}</b><br>Revenue: Rs %{y:,.0f} Cr<extra></extra>",
            ))

        # PAT bars
        pats = [a.pat_absolute for a in sorted_analyses]
        if any(p is not None for p in pats):
            fig.add_trace(go.Bar(
                x=quarters,
                y=[p or 0 for p in pats],
                name="PAT (Rs Cr)",
                marker=dict(color="rgba(57, 211, 83, 0.7)", line=dict(width=1, color="rgba(57, 211, 83, 1)")),
                hovertemplate="<b>%{x}</b><br>PAT: Rs %{y:,.0f} Cr<extra></extra>",
            ))

        # EBITDA Margin line (secondary y-axis)
        margins = [a.ebitda_margin_pct for a in sorted_analyses]
        if any(m is not None for m in margins):
            fig.add_trace(go.Scatter(
                x=quarters,
                y=[m or 0 for m in margins],
                name="EBITDA Margin %",
                mode="lines+markers",
                yaxis="y2",
                line=dict(color="#d29922", width=3),
                marker=dict(size=8, color="#d29922"),
                hovertemplate="<b>%{x}</b><br>EBITDA Margin: %{y:.1f}%<extra></extra>",
            ))

        # Sentiment line (secondary y-axis)
        fig.add_trace(go.Scatter(
            x=quarters,
            y=[a.sentiment_score for a in sorted_analyses],
            name="Sentiment",
            mode="lines+markers",
            yaxis="y2",
            line=dict(color="#bc8cff", width=2, dash="dot"),
            marker=dict(size=6, color="#bc8cff"),
            hovertemplate="<b>%{x}</b><br>Sentiment: %{y:.2f}<extra></extra>",
        ))

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Quarter", gridcolor="rgba(48,54,61,0.4)"),
            yaxis=dict(
                title="Rs Cr",
                gridcolor="rgba(48,54,61,0.4)",
                side="left",
            ),
            yaxis2=dict(
                title="% / Score",
                overlaying="y",
                side="right",
                showgrid=False,
            ),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
            height=450,
            margin=dict(l=50, r=50, t=30, b=80),
            barmode="group",
            bargap=0.3,
        )

        return fig

    @staticmethod
    def build_credibility_gauge(score: float) -> go.Figure:
        """Build a gauge chart for management credibility score (0-100)."""
        color = (
            "#39d353" if score >= 70
            else "#d29922" if score >= 40
            else "#f85149"
        )

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            title=dict(text="Management Credibility", font=dict(size=16, color="#f0f6fc")),
            number=dict(suffix="%", font=dict(size=36, color=color)),
            gauge=dict(
                axis=dict(range=[0, 100], tickfont=dict(color="#8b949e")),
                bar=dict(color=color),
                bgcolor="rgba(22, 27, 34, 0.8)",
                bordercolor="rgba(48, 54, 61, 0.5)",
                borderwidth=2,
                steps=[
                    dict(range=[0, 40], color="rgba(248, 81, 73, 0.15)"),
                    dict(range=[40, 70], color="rgba(210, 153, 34, 0.15)"),
                    dict(range=[70, 100], color="rgba(57, 211, 83, 0.15)"),
                ],
                threshold=dict(
                    line=dict(color="#f0f6fc", width=2),
                    thickness=0.8,
                    value=score,
                ),
            ),
        ))

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=250,
            margin=dict(l=30, r=30, t=60, b=20),
        )
        return fig

    @staticmethod
    def build_risk_trajectory_chart(risks: list) -> go.Figure:
        """Build a horizontal bar chart showing risk trajectory direction."""
        if not risks:
            fig = go.Figure()
            fig.update_layout(
                annotations=[dict(text="No risk data available", showarrow=False,
                                  font=dict(size=14, color="#8b949e"))],
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                height=300,
            )
            return fig

        direction_colors = {
            "Escalating": "#f85149",
            "Recurring": "#d29922",
            "New": "#bc8cff",
            "Stable": "#8b949e",
            "Resolving": "#39d353",
        }

        names = [r.risk[:60] + ("..." if len(r.risk) > 60 else "") for r in risks]
        colors = [direction_colors.get(r.direction, "#8b949e") for r in risks]
        quarters = [r.quarters_mentioned for r in risks]

        fig = go.Figure(go.Bar(
            y=names,
            x=quarters,
            orientation="h",
            marker=dict(color=colors, line=dict(width=1, color="rgba(48,54,61,0.8)")),
            text=[r.direction for r in risks],
            textposition="auto",
            textfont=dict(size=11, color="#f0f6fc"),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Direction: %{text}<br>"
                "Quarters mentioned: %{x}<br>"
                "<extra></extra>"
            ),
        ))

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Quarters Mentioned", gridcolor="rgba(48,54,61,0.4)"),
            yaxis=dict(autorange="reversed"),
            height=max(250, len(risks) * 45),
            margin=dict(l=250, r=20, t=20, b=40),
        )
        return fig

