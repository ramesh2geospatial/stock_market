---
name: sec-sebi-forensic-auditor
description: Forensic corporate governance and regulatory audit skill for scanning SEBI/SEC filings, related-party transactions (RPTs), promoter pledging, auditor qualification flags, cash flow diversion, and off-balance-sheet liabilities. Use when auditing corporate governance red flags, evaluating auditor notes, or scanning promoter SAST disclosures for Indian mid/small-cap stocks.
---

# SEC / SEBI Forensic Auditor Skill

This skill provides institutional corporate governance auditing rules, forensic accounting heuristics, and regulatory compliance scanners modeled after SEBI (Securities & Exchange Board of India) and US SEC enforcement frameworks.

---

## 🔍 1. Promoter Pledging & SAST Risk Matrix

High promoter share pledging creates severe margin-call risk during market downturns:

$$\text{Pledge Risk Factor} = \frac{\text{Pledged Shares}}{\text{Total Promoter Holding}}$$

### Risk Thresholds for Indian Equities
*   **Pledge $< 5\%$**: Low / Negligible Risk.
*   **Pledge $5\% - 20\%$**: Moderate Risk — Monitor weekly.
*   **Pledge $> 20\%$**: **High Downside Warning** — Apply 10% penalty to Trajectory Score.
*   **Pledge $> 50\%$**: **Severe Insolvency Hazard** — Cap maximum rating at Bearish/Underperform.

---

## 💸 2. Cash Flow Diversion & Accounting Quality Scanners

### A. Operating Cash Flow to Net Profit Ratio ($\text{CFO} / \text{PAT}$)
$$\text{Cash Conversion Index} = \frac{\sum_{t=1}^{3} \text{CFO}_t}{\sum_{t=1}^{3} \text{PAT}_t}$$

*   $\text{CFO}/\text{PAT} \ge 1.0$: **High Accounting Quality** (Earnings backed by real cash inflows).
*   $0.5 \le \text{CFO}/\text{PAT} < 1.0$: **Moderate Quality** (Working capital lockup).
*   $\text{CFO}/\text{PAT} < 0.5$: **Severe Red Flag** (Potential paper profits or aggressive revenue recognition).

### B. Related Party Transaction (RPT) Exposure Ratio
$$\text{RPT Ratio} = \frac{\text{Total Related Party Transactions}}{\text{Net Profit}}$$

*   If RPT Ratio $> 30\%$, trigger an automatic **Governance Warning Flag** for potential cash siphoning to promoter-owned entities.

---

## 📢 3. SEBI LODR Regulation 30 Material Disclosures Audit

Under SEBI Regulation 30 (Listing Obligations and Disclosure Requirements), companies must disclose material events within 24 hours:

| Disclosure Event | Category | Impact Weight | Action in Model |
| :--- | :--- | :--- | :--- |
| **Resignation of Statutory Auditor** | Governance Warning | **Severe (-25 pts)** | Trigger immediate forensic audit. |
| **SEBI / RBI / IRDAI Show-Cause Notice** | Regulatory Penalty | **High (-20 pts)** | Deduct regulatory risk score. |
| **Marquee Contract / Order Win ($>10\%$ TTM Rev)** | Deal Flow Boost | **Positive (+15 pts)** | Increase Deal Feeder score. |
| **Key Management Personnel (KMP) Resignation** | Leadership Risk | **Moderate (-10 pts)** | Track executive stability. |
| **Promoter Open-Market Purchase (SAST)** | Insider Confidence | **Positive (+12 pts)** | Boost Smart Money score. |

---

## 📋 4. Forensic Audit Output Format

When executing a forensic audit, produce a structured findings report:

```json
{
  "ticker": "TVSMOTOR.NS",
  "governance_score": 95.0,
  "red_flags": [],
  "auditor_status": "Clean (No qualifications or mid-term resignations)",
  "promoter_pledge_pct": 0.0,
  "cfo_pat_ratio": 1.12,
  "rpt_risk_level": "Low",
  "audit_conclusion": "Passes all SEBI forensic accounting thresholds."
}
```
