# Signal Feeders Technical Specification

Detailed extraction specification and scoring logic for the 6 qualitative & quantitative signal feeders:

## 1. Quantitative Fundamentals Feeder
- **Source**: Screener.in financial tables & yfinance income statements.
- **Key Metrics**:
  - `revenue_growth_yoy`: Trailing 4-quarter YoY revenue growth percentage.
  - `ebitda_margin_expansion_bps`: Change in EBITDA margin relative to prior year matching quarter.
  - `cfo_pat_ratio`: 3-Year average Operating Cash Flow divided by Net Profit.
  - `debt_to_ebitda`: Net debt divided by TTM EBITDA.
- **Scoring**: Range 0 to 100 based on sector-adjusted threshold percentiles.

## 2. Future Opportunities Feeder
- **Source**: Concall transcript Q&A and Investor Presentations.
- **Key Extraction Rules**:
  - Extract all monetized order book values in ₹ Crores.
  - Track announced greenfield/brownfield capex completion dates.
  - Calculate target asset turnover ratio = expected incremental revenue / capex.

## 3. Macro & Trending Theme Feeder
- **Source**: News RSS streams & industry policy announcements.
- **Theme Taxonomy**:
  - `EV_TRANSITION`: Electric vehicle OEMs & auto-component supply chain.
  - `DEFENCE_INDIGENIZATION`: DPSUs and private defence order book recipients.
  - `PLI_SCHEME`: Production Linked Incentive approved beneficiaries.
  - `SEMICONDUCTOR_AI_INFRA`: Chip design, packaging, and data center infrastructure.

## 4. Governance & Risk Scanner Feeder
- **Source**: BSE/NSE Regulation 30/31 corporate filings & annual reports.
- **Risk Multipliers**:
  - `promoter_pledging > 25%`: -20 points penalty.
  - `auditor_resignation_midterm`: -30 points penalty.
  - `rpt_to_pat_ratio > 30%`: -15 points penalty.
  - `regulatory_show_cause_notice`: -25 points penalty.

## 5. Deal Flow & Disclosures Feeder
- **Source**: Material disclosures under SEBI LODR Regulation 30.
- **Impact Rating**:
  - Major Contract ($>10\%$ of TTM revenue): +15 points.
  - M&A Acquisition with accretive EPS: +10 points.

## 6. Competitive Intensity & Regulatory Feeder
- **Source**: Peer concall transcript cross-referencing & regulatory notifications.
- **Metrics**:
  - `market_share_delta_bps`: Market share gain or loss relative to top 3 industry peers.
  - `price_war_flag`: Competitor commentary flagging aggressive discounting.
  - `regulatory_policy_impact`: Tariff protection (+), GST reduction (+), Windfall tax (-), Export ban (-).
