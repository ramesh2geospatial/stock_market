---
name: multi-signal-stock-predictor
description: Institutional-grade 10-signal AI stock trajectory prediction engine analyzing 500 stocks across Fundamentals, Opportunities, Macro Themes, Governance, Deals, Competition, Consensus Surprise, Insider Buying, PEAD Drift, and Market Neutralization using Gemini 2.5 Flash and Local Financial LLMs (FinGPT RLSP / Qwen 2.5). Use when building, fine-tuning, or predicting stock price trajectories, evaluating management credibility, scanning corporate governance red flags, or ranking stocks by forward trajectory score.
---

# Institutional 10-Signal Stock Trajectory Prediction Skill

This skill documents the institutional architecture, data schemas, prompt fusion matrix, RLSP (Reinforcement Learning from Stock Performance) training workflow, and 10-signal prediction algorithms for forecasting stock price trajectories.

---

## 🏛️ Institutional 10-Signal Matrix Architecture

The prediction engine ingests **500 stocks** and synthesizes **10 Signal Feeders** into a factor-neutralized vector:

```
┌───────────────────────────────────────────────────────────────────────────┐
│                      INSTITUTIONAL 10-SIGNAL MATRIX                       │
├───────────────────────────────────────────────────────────────────────────┤
│  1. Quantitative Fundamentals ──> YoY Revenue, EBITDA Margins, CFO/PAT    │
│  2. Concall Management Credibility ──> 10-Quarter Promise Delivery Rate   │
│  3. Future Opportunities & Order Book ──> Order Book ₹ Cr, Capex          │
│  4. Macro & Trending Themes ──> EV, Defence, PLI, AI Infra Alignment       │
│  5. Governance & Risk Scanner ──> Promoter Pledging %, Auditor Flags      │
│  6. Deal Flow Disclosures ──> Reg 30 Filings, M&A, Marquee Contracts      │
│  7. Competitive Intensity ──> Peer Price Wars, Market Share Shifts        │
│  8. [NEW] Consensus Surprise Delta ──> Actual vs Market Consensus         │
│  9. [NEW] Smart Money & Insider Sentiment ──> Promoter Buying, Block Deals│
│ 10. [NEW] Post-Earnings Price Drift (PEAD) ──> Delivery % & FII/DII Drift │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                                      ▼
                      ┌───────────────────────────────┐
                      │    RLSP INFERENCE ENGINE      │ (FinGPT / Qwen 2.5 + Gemini)
                      └───────────────┬───────────────┘
                                      │
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                          INSTITUTIONAL PREDICTION                         │
│  • Risk-Adjusted Alpha Score (-100 to +100)                               │
│  • PEAD Accumulation Window Forecast (15D / 45D / 90D)                    │
│  • Factor-Neutral Target Bands (Bull, Base, Bear)                         │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 🛰️ The 10 Signal Feeders Technical Specification

### Feeder 1: Quantitative & Financial Fundamentals
*   **Metrics**: YoY/QoQ Revenue Growth %, EBITDA Margin Expansion (bps), Net Profit Growth %.
*   **Cash Quality**: CFO/PAT Ratio ($>1.0\times$ ideal), Free Cash Flow Yield, Debt/EBITDA ($<2.5\times$ safe).

### Feeder 2: Concall Management Credibility Index
*   **Promise Delivery Rate**: Ratio of Delivered Promises vs. Missed/Abandoned Promises over 10 quarters.
*   **Guidance Penalty**: Penalizes management for changing or diluting revenue/margin guidance.

### Feeder 3: Future Opportunities & Order Book Pipeline
*   **Order Book Visibility**: Monitored in ₹ Crores & Book-to-Bill Ratio parsed from concalls & presentations.
*   **Capex & Asset Turnover**: Plant commissioning dates and target capacity multiplier (e.g. 2x capacity by Q4 FY27).

### Feeder 4: Macro & Trending Theme Classifier
*   **Theme Tagging**: Mapping stocks to active macro tailwinds (*EV 2W Transition*, *Defence Indigenization*, *Semiconductor Packaging*, *Data Center Infra*, *PLI Scheme Recipient*).

### Feeder 5: Corporate Governance & Risk Scanner
*   **Promoter Pledging**: Tracking % of promoter holding pledged ($>20\%$ triggers severe risk penalty).
*   **Auditor Quality**: Mid-term auditor resignations, qualified audit opinions, or accounting restatements.

### Feeder 6: Deal Flow & Material Announcements (Reg 30 LODR Filings)
*   **Order Wins & Contracts**: Monetized contract value relative to TTM revenue.
*   **M&A & Joint Ventures**: Strategic synergy impact of acquisitions or technology JVs.

### Feeder 7: Competitive Intensity & Market Share Shift
*   **Cross-Peer Analysis**: Parsing competitor transcripts (e.g. TVS vs Bajaj vs Ola) for price war warnings, market share shifts (+/- bps), or discounting.

### Feeder 8: [NEW] Consensus Expectation Surprise Delta
*   **Surprise Equation**: $\text{Surprise Delta} = \frac{\text{Actual Revenue/PAT} - \text{Consensus Estimate}}{\text{Consensus Estimate}}$.
*   **Rule**: Stocks move on expectation beats/misses, not absolute growth numbers.

### Feeder 9: [NEW] Smart Money & Insider Sentiment
*   **Promoter Buying/Selling**: Open market SAST disclosures of promoter purchases or share sales.
*   **Institutional Block Deals**: Size and frequency of bulk/block deals.

### Feeder 10: [NEW] Post-Earnings Announcement Drift (PEAD) & Accumulation
*   **Institutional Accumulation**: Tracking delivery volume % ($\text{Delivery Volume} / \text{Traded Volume}$) for 30 days post-earnings.
*   **FII / DII Net Change**: Net institutional ownership change QoQ.

---

## 🤖 RLSP (Reinforcement Learning from Stock Performance) Engine

Unlike general sentiment models, the predictor uses **RLSP**:
$$\text{Reward} = \text{Sign}(\text{Predicted Return} \times \text{Actual Alpha Return}) \cdot \left| \text{Actual Alpha Return} \right| - \text{Penalty}_{\text{Governance}}$$

This trains the local model (FinGPT / Qwen 2.5) to align sentiment output with **real market price impact** rather than superficial dictionary tone!

---

---

## 🏛️ Institutional Mutual Fund Ingestion & Anti-Blocking Architecture

### 1. Two-Tier Ingestion & Rate-Limit Shield (ADR 0012)
To guarantee zero upstream IP rate-limiting from public/regulatory portals while providing sub-50ms query latency to 100,000+ mobile clients:

```
┌─────────────────────────────────────────────────────────────┐
│ 🌐 Official Regulatory Disclosures / Investor Portals        │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               │                               │
    [Tier 1: Central Shield]       [Tier 2: Crowdsourced Edge]
    Low-frequency Jittered Cron    Mobile App Lazy Cache-Warming
    (1 req / 30D / stock)          (Natural 4G/5G Residential IPs)
               │                               │
               └───────────────┬───────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ ☁️ Supabase Cloud (Central Shared Cache)                    │
│  • RPC: contribute_stock_holding_snapshot(symbol, holdings) │
│  • Tables: public.mf_schemes, public.mf_stock_holdings      │
│  • PostgREST CDN query latency ≤ 40 ms                      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 📱 Flutter Mobile Clients (Zero Scraping, Pure PostgREST)   │
└─────────────────────────────────────────────────────────────┘
```

### 2. Live Database Schemas (Supabase PostgreSQL)
* **`public.index_stocks`**: 756 Indian equities indexed across 5 Market Cap Tiers (`NIFTY_50`, `NIFTY_NEXT_50`, `NIFTY_MIDCAP_150`, `NIFTY_SMALLCAP_250`, `NIFTY_MICROCAP_250`).
* **`public.mf_schemes`**: 300+ real registered mutual fund and mega ETF schemes (`scheme_id`, `scheme_name`, `amc_name`, `category`, `aum_cr`).
* **`public.mf_stock_holdings`**: Scheme-level portfolio holding records (`scheme_id`, `symbol`, `as_of_date`, `shares_held`, `market_value_cr`, `portfolio_weight_pct`, `mom_share_change`, `action_type`).

### 3. Institutional 4-Tab Drilldown UI (`MFDrilldownSheet` - ADR 0011)
* **Tab 1: Overview & Metrics**: Total MF Holding Value ₹ Cr, % of Free Float, Net 30D MoM Inflow, Active Schemes Count.
* **Tab 2: Scheme Master Table**: Searchable and 1-tap sortable by Value (₹ Cr), Fund Weight %, and MoM Net Shares Bought with Action Badges (`FRESH_ENTRY`, `STAKE_INCREASE`, `STAKE_REDUCTION`, `COMPLETE_EXIT`).
* **Tab 3: AMC Concentration Matrix**: Aggregated holding % and capital commitment grouped by fund house (SBI MF, HDFC MF, ICICI Pru, PPFAS, Kotak, Nippon).
* **Tab 4: 6-Month Historical Drift**: Trajectory tracking across consecutive months.

---

## 📁 Architectural Decision Records (ADRs)

* [ADR 0010: MF Holdings Incremental Sync Protocol](file:///d:/GeoNagrik/Dev/git/stock_market/docs/adr/0010-mf-holdings-incremental-sync-protocol.md)
* [ADR 0011: Institutional MF Holdings Drilldown Modal](file:///d:/GeoNagrik/Dev/git/stock_market/docs/adr/0011-institutional-mf-holdings-drilldown-modal.md)
* [ADR 0012: Provider Rate-Limit Shield & Distributed Ingestion Architecture](file:///d:/GeoNagrik/Dev/git/stock_market/docs/adr/0012-anti-blocking-distributed-ingestion-architecture.md)

- [Real-World Quant Architecture Analysis](file:///C:/Users/rames/.gemini/antigravity/brain/df51d154-bb4a-4cbf-b13c-21bdcd20de68/real_life_quant_prediction_architecture.md)
- [Signal Feeders Specification](file:///d:/GeoNagrik/Dev/git/stock_market/.agents/skills/multi-signal-stock-predictor/references/signal_feeders_spec.md)
- [Prompt Fusion Matrix Schema](file:///d:/GeoNagrik/Dev/git/stock_market/.agents/skills/multi-signal-stock-predictor/references/prompt_fusion_matrix.json)
- [Sample Prediction Output](file:///d:/GeoNagrik/Dev/git/stock_market/.agents/skills/multi-signal-stock-predictor/examples/prediction_output_sample.json)
