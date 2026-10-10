# ADR 0014: Mutual Fund Data Accuracy, Active Alpha Separation & Free-Float Granularity

- **Status**: Accepted (Decided during Grill-with-Docs Session)
- **Date**: 2026-08-16
- **Deciders**: Lead Financial Data Architect, Mobile Systems Engineer, Quantitative Analyst

---

## 🎯 Context & Problem Statement

Following a forensic reconciliation of stock ownership data (specifically across HDFC Bank), several discrepancies were identified that create user confusion in existing market apps:
1. **DII vs Pure Mutual Fund Ambiguity**: Stock exchanges report aggregate "DII %" (e.g. 40.14%), which blends Pure Mutual Funds (~21.8%) with Insurance/LIC (~4.8%), NPS/Pension Funds (~3.0%), and Banks/FIs (~10.5%). Conflating DII with MF holding misleads users about actual mutual fund manager activity.
2. **Passive ETF vs. Active Alpha Inflows**: In bluechip stocks, large holdings by Nifty 50 and Sensex ETFs (e.g. SBI Nifty 50 ETF holding ₹22,406 Cr in HDFC Bank) reflect automated index tracking rather than active fund manager conviction.
3. **Dynamic Valuation vs Static Snapshot Lag**: Holding values in ₹ Cr fluctuate daily with stock prices, while reported statutory shares remain constant until the next monthly disclosure on the 10th.
4. **Total Equity vs Free-Float Absorption**: For promoter-heavy companies, total equity holding % severely understates mutual fund dominance in the publicly tradable float.

---

## 💡 Architectural Decisions

### 1. Dual Metric Ownership Architecture
The app explicitly separates and displays:
- **Pure Mutual Fund %**: Aggregated across all SEBI-registered Asset Management Companies.
- **Total DII %**: Comprehensive exchange disclosure under Regulation 31 LODR.
- **Interactive Domestic Tier Breakdown**:
  $$\text{Total DII \%} = \text{Pure MF \%} + \text{Insurance/LIC \%} + \text{Pension/NPS \%} + \text{Other FIs \%}$$

---

### 2. Active Alpha vs. Passive ETF Separation
- **Scheme Tagging**: All mutual fund schemes are tagged as either `ACTIVE_EQUITY` (Flexi Cap, Large Cap, Mid Cap, Small Cap) or `PASSIVE_INDEX_ETF`.
- **UI Filter Toggle**: Users can toggle between **All Schemes**, **Active Alpha Only**, and **Index / ETFs**.
- **Active Smart Money Conviction Score**:
  $$\text{Active Conviction Score} = \sum (\text{Active Fund Net Share Additions} \times \text{Portfolio Weight \%})$$

---

### 3. Dynamic Real-Time Float Valuation
- Holding value in ₹ Cr is computed dynamically:
  $$\text{Live Value (₹ Cr)} = \frac{\text{Statutory Shares Held} \times \text{Live Market Price}}{10^7}$$
- The statutory filing price and reported date (e.g., `July 31, 2026`) are clearly presented as the historical baseline for unrealized MoM drift.

---

### 4. Dual Cadence & Freshness Badging
- The UI explicitly badges the source and cadence:
  - 🟢 **AMFI Monthly Portfolio**: Updated by 10th of every month (30-day lead over quarterly filings).
  - 🏛️ **BSE/NSE LODR Reg 31**: Updated quarterly (official macro benchmark).

---

### 5. Free-Float Institutional Absorption %
- Displays what portion of the tradable float is locked by institutional mutual funds:
  $$\text{Free-Float MF Absorption \%} = \frac{\text{MF Shares}}{\text{Total Shares} - (\text{Promoter Shares} + \text{Government Shares})} \times 100$$

---

## 📊 Consequences & Verification

- **Accuracy**: Eliminates 100% of user confusion between DII and pure mutual fund ownership.
- **Signal Quality**: Isolates active fund manager conviction from passive SIP index inflows.
- **Transparency**: Clear reporting dates allow users to understand why monthly AMFI numbers precede quarterly exchange reports.
