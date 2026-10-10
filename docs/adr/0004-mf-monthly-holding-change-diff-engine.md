# ADR 0004: Month-over-Month (MoM) Portfolio Diff Engine for Mutual Fund Buying & Selling Discovery

- **Status**: Accepted
- **Date**: 2026-08-13
- **Deciders**: Lead Financial Data Architect, Mobile Lead

## Context & Problem Statement

Retail investors and market analysts require transparency into what Indian Mutual Funds are actively buying, holding, and dumping each month across 500+ equity schemes.

## Decision Drivers

1. **Institutional Trade Discovery**: Identify fresh stock additions, complete exits, and major accumulation/distribution trends by top fund managers.
2. **Reverse Stock Search**: Allow users to query any Indian stock (e.g. *Tata Motors*, *Zomato*) and view which mutual funds own it and their net share changes.
3. **SEBI Mandatory Open Disclosures**: Ingest monthly portfolio filings published by AMCs by the 10th of every month.

## Decision Outcome

Chosen Option: **Automated Monthly Portfolio Diff & Aggregation Engine**:
1. Store historical monthly portfolio snapshots per scheme (`scheme_id`, `month`, `year`, `isin`, `stock_name`, `quantity`, `value_in_cr`, `weight_pct`).
2. Run automated monthly diff worker computing:
   - Fresh Entries: \(\text{Quantity}(T-1) = 0 \rightarrow \text{Quantity}(T) > 0\)
   - Exits: \(\text{Quantity}(T-1) > 0 \rightarrow \text{Quantity}(T) = 0\)
   - Net Shares Bought / Sold across all schemes for each stock.

### Consequences

- **Positive**: Provides institutional-grade insights into Smart Money moves, top bought/sold stocks, and scheme portfolio changes.
- **Negative**: Dependent on AMC monthly filing timelines (updated by 10th of every month as mandated by SEBI).
