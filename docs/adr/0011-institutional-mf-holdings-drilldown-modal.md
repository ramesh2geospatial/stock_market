# ADR 0011: Institutional Mutual Fund Holdings Drilldown Modal & Multi-Dimensional Ownership Matrix

## Status
**ACCEPTED** (2026-08-14)

## Context & Problem Statement
In the stock market research mobile application, tracking mutual fund holding behavior requires deep visibility into individual scheme-level allocations, AMC concentration, and historical accumulation drift. The initial list view only exposed a superficial 2-3 scheme preview, preventing users from seeing:
1. Total holding value in ₹ Crores and % of company's free-float equity.
2. Scheme-level portfolio weight % and exact Month-on-Month (MoM) share changes.
3. AMC-level concentration risk (e.g. SBI MF vs HDFC MF vs ICICI Prudential).
4. Multi-month accumulation/distribution trends.

## Decision Drivers
- **Institutional Depth**: Professional equity analysts require complete scheme-level granularity rather than truncated previews.
- **Zero Friction Navigation**: Users should not lose their scroll position or filter state when inspecting a stock's institutional ownership.
- **Multi-Dimensional Sorting**: Ability to sort 40+ schemes by Holding Value (₹ Cr), Net Shares Bought (MoM), or Fund Portfolio Weight %.

## Decision
Adopt an **Interactive Slide-Up Institutional Bottom Sheet Modal (`MFDrilldownSheet`)** with 4 dedicated analytical views:
1. **📊 Overview & Metric Cards**: Total MF Value (₹ Cr), % of Free-Float, Net Monthly Inflow, Primary Category.
2. **📋 Complete Scheme Master Table**: Searchable, sortable list of all holding schemes with category badges, shares held, MoM deltas, holding value, and action tags.
3. **🏢 AMC Concentration Matrix**: Aggregated holding percentage and capital commitment grouped by Asset Management Company.
4. **📈 Historical Accumulation Drift**: 6-Month MoM tracking of domestic institutional shareholding trajectory.

## Consequences
### Positive
- Sub-second access to complete institutional ownership intelligence without leaving the index tier view.
- Provides immediate clarity on which fund managers are aggressively accumulating vs distributing.
- Fully offline-capable through local SQLite and Supabase PostgREST sync.

### Negative / Trade-offs
- Requires client-side grouping and sorting computations for large scheme catalogs (mitigated via lightweight Dart collections).
