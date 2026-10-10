---
name: bloomberg-financial-analyst
description: Bloomberg Terminal-style quantitative financial analysis skill for evaluating valuation multiples (P/E, EV/EBITDA, P/B, P/FCF), DuPont ROE decomposition, Altman Z-Score bankruptcy prediction, Beneish M-Score earnings manipulation detection, and DCF fair value modeling for Indian equities. Use when analyzing financial statements, calculating fair value target bands, assessing solvency, or benchmarking against industry peers.
---

# Bloomberg Financial Analyst Skill

This skill provides institutional financial modeling frameworks, formulas, and evaluation methodologies inspired by Bloomberg Terminal analytics and CFA Institute financial analysis standards.

---

## 🏛️ 1. DuPont 3-Step & 5-Step ROE Decomposition

Deconstruct Return on Equity (ROE) to determine whether profitability is driven by operational efficiency, asset utilization, or dangerous financial leverage:

$$\text{ROE (3-Step)} = \underbrace{\frac{\text{Net Income}}{\text{Revenue}}}_{\text{Net Profit Margin}} \times \underbrace{\frac{\text{Revenue}}{\text{Total Assets}}}_{\text{Asset Turnover}} \times \underbrace{\frac{\text{Total Assets}}{\text{Shareholder Equity}}}_{\text{Financial Leverage}}$$

### Red Flag Thresholds
*   **Quality ROE**: Driven by high Net Profit Margin ($>12\%$) and high Asset Turnover ($>1.2\times$).
*   **Low-Quality ROE**: Driven primarily by high Financial Leverage ($>3.0\times$) despite thin profit margins ($<4\%$).

---

## ⚠️ 2. Altman Z-Score (Financial Distress & Solvency Scanner)

Predicts probability of corporate financial distress/bankruptcy within 2 years:

$$Z = 1.2 \cdot X_1 + 1.4 \cdot X_2 + 3.3 \cdot X_3 + 0.6 \cdot X_4 + 0.999 \cdot X_5$$

Where:
*   $X_1 = \text{Working Capital} / \text{Total Assets}$
*   $X_2 = \text{Retained Earnings} / \text{Total Assets}$
*   $X_3 = \text{EBIT} / \text{Total Assets}$
*   $X_4 = \text{Market Cap} / \text{Total Liabilities}$
*   $X_5 = \text{Revenue} / \text{Total Assets}$

### Z-Score Interpretation Zones
*   $Z > 2.99$: **Safe Zone** (Low probability of insolvency).
*   $1.81 \le Z \le 2.99$: **Grey Zone** (Moderate solvency risk).
*   $Z < 1.81$: **Distress Zone** (High financial distress risk — Apply Governance Penalty).

---

## 🕵️ 3. Beneish M-Score (Earnings Manipulation Scanner)

Detects probability of accounting manipulation or revenue inflation:

$$M = -4.84 + 0.920 \cdot \text{DSRI} + 0.528 \cdot \text{GMI} + 0.404 \cdot \text{AQI} + 0.892 \cdot \text{SGI} + 0.115 \cdot \text{DEPI} - 0.172 \cdot \text{SGAI} + 4.679 \cdot \text{TATA} - 0.327 \cdot \text{LVGI}$$

Where:
*   **DSRI** (Days Sales in Receivables Index): $\frac{\text{Receivables}_t / \text{Rev}_t}{\text{Receivables}_{t-1} / \text{Rev}_{t-1}}$ ($>1.0$ indicates aggressive revenue booking).
*   **GMI** (Gross Margin Index): $\frac{\text{Gross Margin}_{t-1}}{\text{Gross Margin}_t}$ ($>1.0$ indicates deteriorating margins).
*   **TATA** (Total Accruals to Total Assets): $\frac{\text{Net Income}_t - \text{CFO}_t}{\text{Total Assets}_t}$ (High positive value indicates earnings unbacked by cash).

### M-Score Interpretation
*   $M > -1.78$: **High Likelihood of Earnings Manipulation** (Flag immediate Red Alert!).
*   $M \le -1.78$: **Normal Accounting Quality**.

---

## 📈 4. Multi-Scenario DCF Valuation Target Bands

Calculates intrinsic fair value using explicit 5-year Free Cash Flow to Firm (FCFF) projections:

$$\text{Intrinsic Value} = \sum_{t=1}^{5} \frac{\text{FCFF}_t}{(1 + \text{WACC})^t} + \frac{\text{Terminal Value}}{(1 + \text{WACC})^5}$$

Where:
$$\text{Terminal Value} = \frac{\text{FCFF}_5 \times (1 + g)}{\text{WACC} - g}$$

*   **WACC (India Cost of Capital)**: Standardized at $11.5\% - 13.0\%$ for Indian equities.
*   **Terminal Growth Rate ($g$)**: Standardized at $4.5\% - 5.5\%$ (aligned with long-term Indian GDP expansion).
