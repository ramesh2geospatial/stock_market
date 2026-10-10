# Workspace Agents & Architecture Guidelines: Indian Stock Market Research Platform

This file defines the project-scoped rules, architectural conventions, and institutional multi-signal prediction design for the stock market analysis platform.

---

## 🏛️ Project Architecture & Design Principles

### 1. Unified Modular Stack
- **Dashboard UI (`app.py`)**: Streamlit-based 11-tab platform featuring Plotly interactive visualizers, cashflow analysis, spider charts, milestone trackers, Vahan EV registration metrics, and AI Stock Trajectory Predictions.
- **Orchestrator (`stock_analyzer.py`)**: Central coordinator wiring providers, analyzers, storage layers, and prediction engines.
- **Data Providers (`providers/`)**:
  - `screener_provider.py`: Financial tables, quarterly balance sheets, P&L, concall transcripts.
  - `yfinance_provider.py`: Real-time quotes, historical price series, valuation metrics.
  - `vahan_provider.py`: MoRTH electric 2-wheeler registration data with SQLite caching.
  - `insider_data_provider.py`: Promoter open-market buying/selling (SAST), bulk/block deals, and daily delivery volume %.
  - `local_llm_provider.py`: Ollama REST API interface (`http://localhost:11434`) for local model execution with Gemini 2.5 Flash fallback.
- **Analyzers (`analyzers/`)**:
  - `gemini_analyzer.py`: AI concall transcript extraction & structured sentiment parsing.
  - `intelligence_engine.py`: 10-quarter cross-quarter synthesis, promise delivery tracking, credibility index.
  - `consensus_analyzer.py`: Consensus Expectation Surprise Delta calculation ($\text{Actual} - \text{Expected}$).
  - `prediction_engine.py`: Institutional 10-Signal Matrix aggregation, factor neutralization (Nifty Beta stripping), and scenario target price bands.
- **Storage Layer (`storage/`)**:
  - `sqlite_store.py`: Persistent database storing watchlists, notes, concall analysis, milestone tracks, cashflow caches, Vahan daily sales, and institutional stock predictions.
  - `cache.py`: FileCache TTL-based JSON storage for API network responses.

---

## 🛰️ The Institutional 10-Signal Matrix

All stock price trajectory predictions use the **10-Signal Matrix**:

| Signal # | Signal Name | Core Metrics / Source | Weight |
| :--- | :--- | :--- | :--- |
| **1** | **Quantitative Fundamentals** | YoY Revenue, EBITDA Margins, CFO/PAT, Debt/EBITDA | $15\%$ |
| **2** | **Concall Credibility Index** | 10-Quarter Promise Delivery Rate (Delivered vs Missed) | $15\%$ |
| **3** | **Future Opportunities & Order Book** | Order Book ₹ Cr, Capex Commissioning, TAM Expansion | $10\%$ |
| **4** | **Macro & Trending Themes** | EV, Defence, PLI, AI Infra Sectoral Alignment Index | $10\%$ |
| **5** | **Governance & Risk Scanner** | Promoter Pledging %, RPT Volume %, Auditor Flags | $10\%$ (Penalty) |
| **6** | **Deal Flow & LODR Disclosures** | Reg 30 Filings, M&A, Marquee Order Wins | $5\%$ |
| **7** | **Competitive Intensity** | Peer Concall Price War Warnings, Market Share Shifts | $5\%$ |
| **8** | **Consensus Surprise Delta** | Actual Earnings vs. Consensus Expectations ($\frac{\text{Actual} - \text{Expected}}{\text{Expected}}$) | **10%** |
| **9** | **Smart Money & Insider Actions** | Open-Market Promoter Buying (SAST) & Bulk Deals | **10%** |
| **10** | **PEAD & Institutional Accumulation**| 30-Day Delivery Volume % & FII/DII Ownership Drift | **10%** |

---

## 🤖 RLSP (Reinforcement Learning from Stock Performance)

Predictive LLM prompts are fine-tuned using **RLSP**, using actual post-earnings 30D/90D risk-adjusted Alpha returns as reward feedback:
$$\text{Reward} = \text{Sign}(\text{Predicted Return} \times \text{Actual Alpha Return}) \cdot \left| \text{Actual Alpha Return} \right| - \text{Penalty}_{\text{Governance}}$$

---

## 📁 Active Workspace Skills

- **`multi-signal-stock-predictor`**: Located at `.agents/skills/multi-signal-stock-predictor/SKILL.md`. Governs 10-signal prediction architecture, prompt fusion schemas, and local LLM workflows.
- **`bloomberg-financial-analyst`**: Located at `.agents/skills/bloomberg-financial-analyst/SKILL.md`. Governs Bloomberg Terminal-style quantitative modeling, DuPont ROE decomposition, Altman Z-Score solvency, Beneish M-Score manipulation detection, and DCF target bands.
- **`sec-sebi-forensic-auditor`**: Located at `.agents/skills/sec-sebi-forensic-auditor/SKILL.md`. Governs SEBI/SEC forensic accounting, promoter pledge risk matrices, CFO/PAT cash conversion checks, and Regulation 30 LODR disclosure audits.
- **`sector-financial-analyst`**: Located at `.agents/skills/sector-financial-analyst/SKILL.md`. Governs sector-specific quantitative modeling for Banking (NIM, NPA, CASA), Pharma (FDA Form 483, ANDA, R&D %), IT (TCV/ACV, Attrition), Semiconductors (Capacity Utilization, Backlog), and QSR/Restaurants (SSSG, Store Count, ADS).
- **`geonagrik-domain-knowledge`**: Located at `.agents/skills/geonagrik-domain-knowledge/SKILL.md`. Governs GeoNagrik ubiquitous language, user/vendor/provider personas, booking/queue token workflows, H3 spatial indexing, ad monetization, chat encryption, campaign rules, and governance models.
- **`domain-modeling`**: Located at `.agents/skills/domain-modeling/SKILL.md`. Governs active domain modeling, ubiquitous language enforcement, glossary management (`CONTEXT.md`), and Architectural Decision Records (`docs/adr/`).
- **`grill-with-docs`**: Located at `.agents/skills/grill-with-docs/SKILL.md`. Governs relentless design stress-testing interviews (`/grilling`) combined with live domain modeling and ADR documentation generation.
- **`geonagrik-website-content`**: Located at `.agents/skills/geonagrik-website-content/SKILL.md`. Governs high-fidelity copy, user/vendor journey steps, and transparency frameworks for the GeoNagrik civic mapping platform (https://geonagrik.in).
- **`agentic-code-orchestrator`**: Located at `.agents/skills/agentic-code-orchestrator/SKILL.md`. Governs the Claude Opus 4.6 + Gemini 3.6 Flash dual-model agentic coding workflow for all code generation, refactoring, and feature requests.
- **`quality-orchestrator`**: Located at `.agents/skills/quality-orchestrator/SKILL.md`. Governs credit-optimized quality orchestration routing work between Opus 4.6 (architect/reviewer) and Flash 3.6 (builder/researcher/tester/reviewer) for 85-95% credit savings.
- **`supabase-postgres-data-pipeline`**: Located at `.agents/skills/supabase-postgres-data-pipeline/SKILL.md`. Governs Supabase PostgreSQL schema design, PL/pgSQL RPCs, RLS security hardening, and financial time-series data ingestion pipelines.


---

## ⚡ Agentic Coding Policy

Whenever the user provides a coding prompt or requests a feature/script:
1. All architectural design, complex logic, and adversarial code reviews are routed to **Claude Opus 4.6 (High Reasoning)**.
2. All context indexing, task decomposition, and initial code drafting are routed to **Gemini 3.6 Flash (Fast Execution)**.
3. Code generation can be executed directly via `python scripts/agentic_coder.py --prompt "<user_prompt>"` or programmatically via `services.agentic_orchestrator.AgenticCodingOrchestrator`.

