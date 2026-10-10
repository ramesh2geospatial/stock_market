# ADR 0005: Market Cap Tiered Stock Discovery & Mutual Fund Ownership Matrix

- **Status**: Proposed / Under Review
- **Date**: 2026-08-13
- **Deciders**: Lead Financial Data Architect, Mobile UX Lead

## Context & Problem Statement

Users need to browse stocks categorized by market capitalization (**Large Cap**, **Mid Cap**, **Small Cap**, **Micro Cap**) and instantly see for each stock:
1. Which mutual funds own shares in the stock.
2. How many shares & portfolio weight % each mutual fund scheme holds.
3. Industry-wide net buying/selling trends (MoM net share change).

## Decision Drivers

1. **Market Cap Segmentation**: Align with SEBI standard market cap categorization (AMFI half-yearly list).
2. **Reverse Ownership Drilldown**: Allow smooth navigation from Market Cap Tier $\rightarrow$ Stock List $\rightarrow$ Mutual Funds Holding Matrix.
3. **Smart Money Signal**: Highlight high-conviction small/micro cap bets where fund managers initiate fresh entries.

## Decision Outcome

Proposed Design: **4-Tier Market Cap Stock Explorer & MF Holdings Matrix**:
1. **Tier Filter Tabs**: Large Cap (Rank 1-100), Mid Cap (Rank 101-250), Small Cap (Rank 251-500), Micro Cap (Rank 501+).
2. **Stock Card Summary**: Stock name, ticker, market cap (₹ Cr), total MF holding %, number of holding schemes, and MoM net share change (e.g. `+2.4M shares bought`).
3. **MF Holdings Matrix Drawer / Detail View**: Detailed table of every mutual fund scheme holding the stock:
   - Scheme Name & AMC
   - Shares Held & Market Value (₹ Cr)
   - Portfolio Weight % in Scheme
   - MoM Action (`STAKE_INCREASE`, `FRESH_ENTRY`, `STAKE_REDUCTION`, `COMPLETE_EXIT`).

### Consequences

- **Positive**: Clean, intuitive discovery of stock-level mutual fund holdings across all 4 market cap tiers.
- **Negative**: Requires maintaining semi-annual SEBI/AMFI Market Cap classification lists for 1,000+ listed stocks.
