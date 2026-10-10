"""
Cashflow Analysis Engine.
Processes raw Screener.in cashflow/balance-sheet DataFrames into structured
CashFlowPeriod objects with derived metrics and diagnostic signals,
and cross-validates/augments with yfinance data when available.
"""
import pandas as pd
from typing import Optional

from models.cashflow import CashFlowPeriod, CashFlowDiagnostic, CashFlowAnalysisResult


class CashflowAnalyzer:
    """
    Builds comprehensive cashflow analysis from Screener.in data:
    - Annual cash flow statement (CFO, CFI, CFF)
    - Annual/quarterly balance sheet (receivables, payables, inventory)
    - Quarterly P&L for revenue/profit context
    - Derived metrics: CCR, FCF, DSO, DPO, working capital days
    - Diagnostic signals: red/yellow/green flags
    - Cross-validation with yfinance data where available
    """

    def analyze(
        self,
        cashflow_df: pd.DataFrame,
        balance_sheet_df: pd.DataFrame,
        profit_loss_df: pd.DataFrame = None,
        quarterly_results: list = None,
        symbol: str = "",
        yf_financials: dict = None,
    ) -> CashFlowAnalysisResult:
        """
        Main entry point. Takes raw DataFrames and returns structured analysis.
        """
        annual_data = self._build_annual_data(cashflow_df, balance_sheet_df, profit_loss_df)
        quarterly_bs = self._build_quarterly_bs_from_annual(balance_sheet_df, quarterly_results, yf_financials)

        # Compute derived metrics
        self._compute_derived_metrics(annual_data)
        self._compute_derived_metrics(quarterly_bs)

        # Growth rates (YoY for annual, QoQ for quarterly)
        self._compute_growth_rates(annual_data)
        self._compute_growth_rates(quarterly_bs)

        # Generate diagnostics & cross-validation
        diagnostics = self._generate_diagnostics(annual_data, quarterly_bs)
        cross_val_diags = self._cross_validate_annual(annual_data, yf_financials)
        diagnostics.extend(cross_val_diags)

        # Cash quality score
        score = self._compute_quality_score(annual_data, diagnostics)

        # Summary
        summary = self._generate_summary(annual_data, score)

        return CashFlowAnalysisResult(
            symbol=symbol,
            annual_data=annual_data,
            quarterly_bs_data=quarterly_bs,
            diagnostics=diagnostics,
            cash_quality_score=score,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Build structured data from raw DataFrames
    # ------------------------------------------------------------------

    def _build_annual_data(
        self, cashflow_df: pd.DataFrame, balance_sheet_df: pd.DataFrame, profit_loss_df: pd.DataFrame = None
    ) -> list[CashFlowPeriod]:
        """Parse annual cash flow statement + balance sheet + P&L into CashFlowPeriod list."""
        periods = []
        if cashflow_df.empty:
            return periods

        metric_col = cashflow_df.columns[0]
        year_cols = [c for c in cashflow_df.columns if c != metric_col]

        for year_col in year_cols:
            cfo = self._get_metric(cashflow_df, metric_col, year_col,
                                   ["Cash from Operating Activity", "Operating Activity"])
            cfi = self._get_metric(cashflow_df, metric_col, year_col,
                                   ["Cash from Investing Activity", "Investing Activity"])
            cff = self._get_metric(cashflow_df, metric_col, year_col,
                                   ["Cash from Financing Activity", "Financing Activity"])
            net_cf = self._get_metric(cashflow_df, metric_col, year_col,
                                      ["Net Cash Flow", "Net Cash"])

            # Revenue and net profit from cash flow table (some have it)
            revenue = self._get_metric(cashflow_df, metric_col, year_col,
                                       ["Sales", "Revenue"])
            net_profit = self._get_metric(cashflow_df, metric_col, year_col,
                                          ["Net Profit", "Profit after tax", "PAT"])

            # Balance sheet items for this year
            recv = pay = inv = borr = cash_eq = 0.0
            if not balance_sheet_df.empty:
                bs_col = balance_sheet_df.columns[0]
                if year_col in balance_sheet_df.columns:
                    recv = self._get_metric(balance_sheet_df, bs_col, year_col,
                                            ["Trade Receivables", "Receivables", "Debtors",
                                             "Trade receivables"])
                    pay = self._get_metric(balance_sheet_df, bs_col, year_col,
                                           ["Trade Payables", "Payables", "Trade payables",
                                            "Creditors"])
                    inv = self._get_metric(balance_sheet_df, bs_col, year_col,
                                           ["Inventories", "Inventory"])
                    borr = self._get_metric(balance_sheet_df, bs_col, year_col,
                                            ["Borrowings", "Total Borrowings",
                                             "Long Term Borrowings", "Short Term Borrowings"])
                    cash_eq = self._get_metric(balance_sheet_df, bs_col, year_col,
                                               ["Cash Equivalents", "Cash", "Cash & Bank",
                                                "Cash and bank"])
                    total_assets = self._get_metric(balance_sheet_df, bs_col, year_col,
                                                    ["Total Assets"])
                    total_liabilities = self._get_metric(balance_sheet_df, bs_col, year_col,
                                                         ["Total Liabilities"])
                    retained_earnings = self._get_metric(balance_sheet_df, bs_col, year_col,
                                                         ["Reserves", "Reserves & Surplus", "Reserves and surplus", "Retained Earnings"])

            # EBIT from profit_loss_df
            ebit = 0.0
            if profit_loss_df is not None and not profit_loss_df.empty:
                pl_col = profit_loss_df.columns[0]
                if year_col in profit_loss_df.columns:
                    ebit = self._get_metric(profit_loss_df, pl_col, year_col,
                                            ["Operating Profit", "EBIT", "PBIT", "Profit before interest and tax"])
                    if revenue == 0.0:
                        revenue = self._get_metric(profit_loss_df, pl_col, year_col,
                                                   ["Sales", "Revenue", "Total Revenue"])
                    if net_profit == 0.0:
                        net_profit = self._get_metric(profit_loss_df, pl_col, year_col,
                                                      ["Net Profit", "Profit after tax", "PAT"])

            # Get revenue from balance sheet / P&L if not in CF
            if revenue == 0.0 and not balance_sheet_df.empty:
                bs_col = balance_sheet_df.columns[0]
                if year_col in balance_sheet_df.columns:
                    revenue = self._get_metric(balance_sheet_df, bs_col, year_col,
                                               ["Sales", "Revenue", "Total Revenue"])

            periods.append(CashFlowPeriod(
                period=str(year_col).strip(),
                period_type="annual",
                revenue=revenue,
                net_profit=net_profit,
                cfo=cfo,
                cfi=cfi,
                cff=cff,
                net_cash_flow=net_cf if net_cf != 0 else cfo + cfi + cff,
                trade_receivables=recv,
                trade_payables=pay,
                inventory=inv,
                total_borrowings=borr,
                cash_and_equivalents=cash_eq,
                total_assets=total_assets if 'total_assets' in locals() else 0.0,
                total_liabilities=total_liabilities if 'total_liabilities' in locals() else 0.0,
                retained_earnings=retained_earnings if 'retained_earnings' in locals() else 0.0,
                ebit=ebit if 'ebit' in locals() else 0.0,
            ))

        return periods

    def _build_quarterly_bs_from_annual(
        self, balance_sheet_df: pd.DataFrame, quarterly_results: list, yf_financials: dict = None
    ) -> list[CashFlowPeriod]:
        """
        Build quarterly working capital data by combining quarterly P&L
        (revenue/profit we already have) with quarterly balance sheet from yfinance.
        """
        periods = []
        if not quarterly_results:
            return periods

        # Parse yfinance quarterly balance sheet if available
        qbs_df = None
        if yf_financials and "quarterly_balance_sheet" in yf_financials:
            qbs_df = yf_financials["quarterly_balance_sheet"]

        # Use quarterly P&L data as the base
        for qr in quarterly_results:
            recv = pay = inv = borr = cash_eq = 0.0

            # 1. Look in yfinance quarterly balance sheet first for precise quarterly numbers
            if qbs_df is not None and not qbs_df.empty:
                matched_col = None
                for col in qbs_df.columns:
                    if col == "index":
                        continue
                    col_q = self._normalize_date_to_quarter(col)
                    if col_q == qr.quarter:
                        matched_col = col
                        break

                if matched_col:
                    metric_col = "index"
                    recv = self._get_metric(qbs_df, metric_col, matched_col,
                                            ["Accounts Receivable", "Receivables", "Trade Receivables"]) / 1e7
                    pay = self._get_metric(qbs_df, metric_col, matched_col,
                                           ["Accounts Payable", "Payables", "Trade Payables"]) / 1e7
                    inv = self._get_metric(qbs_df, metric_col, matched_col,
                                           ["Inventory", "Inventories"]) / 1e7
                    borr = self._get_metric(qbs_df, metric_col, matched_col,
                                            ["Total Debt", "Net Debt"]) / 1e7
                    cash_eq = self._get_metric(qbs_df, metric_col, matched_col,
                                               ["Cash Cash Equivalents And Short Term Investments",
                                                "Cash And Cash Equivalents", "Cash Financial"]) / 1e7

            # 2. Fallback to Screener annual/half-yearly balance sheet if yfinance failed to match
            if recv == 0.0 and pay == 0.0 and balance_sheet_df is not None and not balance_sheet_df.empty:
                bs_col = balance_sheet_df.columns[0]
                matched_col = None
                for col in balance_sheet_df.columns:
                    if col == bs_col:
                        continue
                    if str(col).strip() == qr.quarter:
                        matched_col = col
                        break

                if matched_col:
                    recv = self._get_metric(balance_sheet_df, bs_col, matched_col,
                                            ["Trade Receivables", "Receivables", "Debtors"])
                    pay = self._get_metric(balance_sheet_df, bs_col, matched_col,
                                           ["Trade Payables", "Payables", "Creditors"])
                    inv = self._get_metric(balance_sheet_df, bs_col, matched_col,
                                           ["Inventories", "Inventory"])
                    borr = self._get_metric(balance_sheet_df, bs_col, matched_col,
                                            ["Borrowings", "Total Borrowings"])
                    cash_eq = self._get_metric(balance_sheet_df, bs_col, matched_col,
                                               ["Cash Equivalents", "Cash", "Cash & Bank"])

            periods.append(CashFlowPeriod(
                period=qr.quarter,
                period_type="quarterly",
                revenue=qr.revenue,
                net_profit=qr.net_profit,
                expenses=qr.expenses,
                trade_receivables=recv,
                trade_payables=pay,
                inventory=inv,
                total_borrowings=borr,
                cash_and_equivalents=cash_eq,
            ))

        return periods

    def _normalize_date_to_quarter(self, date_str: str) -> str:
        """Map a date string like '2026-03-31' to closest Indian quarter name like 'Mar 2026'."""
        try:
            dt = pd.to_datetime(date_str)
            months = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                      7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
            m = dt.month
            closest_m = min([3, 6, 9, 12], key=lambda x: abs(x - m))
            return f"{months[closest_m]} {dt.year}"
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Derived metrics computation
    # ------------------------------------------------------------------

    def _compute_derived_metrics(self, periods: list[CashFlowPeriod]):
        """Compute CCR, FCF, DSO, DPO, inventory days, working capital cycle."""
        for p in periods:
            # Cash Conversion Ratio = CFO / PAT
            if p.net_profit and p.net_profit != 0 and p.cfo != 0 and pd.notna(p.net_profit) and pd.notna(p.cfo):
                p.cash_conversion_ratio = round(p.cfo / abs(p.net_profit), 2)

            # Free Cash Flow = CFO - |CFI| (investing outflows as CAPEX proxy)
            if p.cfo != 0 and p.cfi != 0:
                # CFI is typically negative (outflow). FCF = CFO + CFI (since CFI is negative)
                p.free_cash_flow = round(p.cfo + p.cfi, 2)

            # Receivable Days = (Trade Receivables / Revenue) * 365
            days_factor = 365 if p.period_type == "annual" else 90  # ~quarter
            if p.revenue and p.revenue > 0 and p.trade_receivables > 0:
                p.receivable_days = round((p.trade_receivables / p.revenue) * days_factor, 1)

            # Payable Days = (Trade Payables / Expenses) * 365
            expenses = p.expenses if p.expenses > 0 else p.revenue * 0.85  # rough estimate
            if expenses > 0 and p.trade_payables > 0:
                p.payable_days = round((p.trade_payables / expenses) * days_factor, 1)

            # Inventory Days = (Inventory / Revenue) * 365
            if p.revenue and p.revenue > 0 and p.inventory > 0:
                p.inventory_days = round((p.inventory / p.revenue) * days_factor, 1)

            # Working Capital Cycle = Receivable Days + Inventory Days - Payable Days
            recv_d = p.receivable_days or 0
            inv_d = p.inventory_days or 0
            pay_d = p.payable_days or 0
            if recv_d > 0 or inv_d > 0:
                p.working_capital_days = round(recv_d + inv_d - pay_d, 1)
                
            # FCF Margin
            if p.revenue > 0 and p.free_cash_flow is not None:
                p.fcf_margin = round((p.free_cash_flow / p.revenue) * 100, 2)

            # DuPont ROE Components
            if p.revenue > 0:
                p.dupont_npm = p.net_profit / p.revenue
            if p.total_assets > 0:
                p.dupont_at = p.revenue / p.total_assets
            
            equity = p.total_assets - p.total_liabilities
            if equity > 0:
                p.dupont_fl = p.total_assets / equity
                
            if p.dupont_npm is not None and p.dupont_at is not None and p.dupont_fl is not None:
                p.dupont_roe = round((p.dupont_npm * p.dupont_at * p.dupont_fl) * 100, 2)

            # Altman Z-Score
            if p.total_assets > 0:
                working_capital = (p.trade_receivables + p.inventory) - p.trade_payables
                x1 = working_capital / p.total_assets
                x2 = p.retained_earnings / p.total_assets
                x3 = p.ebit / p.total_assets
                x4 = equity / p.total_liabilities if p.total_liabilities > 0 else 0
                x5 = p.revenue / p.total_assets
                p.altman_z_score = round(1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 0.999 * x5, 2)

    def _compute_growth_rates(self, periods: list[CashFlowPeriod]):
        """Compute YoY/period-over-period growth in receivables and revenue."""
        for i in range(1, len(periods)):
            curr = periods[i]
            prev = periods[i - 1]

            if prev.trade_receivables and prev.trade_receivables > 0 and curr.trade_receivables > 0:
                curr.receivable_growth_pct = round(
                    ((curr.trade_receivables - prev.trade_receivables) / prev.trade_receivables) * 100, 1
                )

            if prev.revenue and prev.revenue > 0 and curr.revenue > 0:
                curr.revenue_growth_pct = round(
                    ((curr.revenue - prev.revenue) / prev.revenue) * 100, 1
                )
            
            if prev.cfo and prev.cfo != 0:
                curr.cfo_growth_pct = round(
                    ((curr.cfo - prev.cfo) / abs(prev.cfo)) * 100, 1
                )

    # ------------------------------------------------------------------
    # Diagnostic signal generation
    # ------------------------------------------------------------------

    def _generate_diagnostics(
        self, annual: list[CashFlowPeriod], quarterly: list[CashFlowPeriod]
    ) -> list[CashFlowDiagnostic]:
        """Generate red/yellow/green diagnostic flags from the data."""
        diags = []
        data = annual if annual else quarterly

        if not data:
            return diags

        # 1. Cash Conversion Ratio analysis (last 3 years)
        recent = [p for p in data[-5:] if p.cash_conversion_ratio is not None]
        if recent:
            avg_ccr = sum(p.cash_conversion_ratio for p in recent) / len(recent)
            if avg_ccr < 0.5:
                diags.append(CashFlowDiagnostic(
                    severity="red",
                    category="Cash Conversion",
                    message=f"Poor cash conversion: avg CFO/PAT = {avg_ccr:.2f}x over last {len(recent)} years. Business is NOT converting profits to cash.",
                    metric_value=avg_ccr,
                ))
            elif avg_ccr < 0.8:
                diags.append(CashFlowDiagnostic(
                    severity="yellow",
                    category="Cash Conversion",
                    message=f"Below-average cash conversion: avg CFO/PAT = {avg_ccr:.2f}x. Some profits are stuck in working capital.",
                    metric_value=avg_ccr,
                ))
            else:
                diags.append(CashFlowDiagnostic(
                    severity="green",
                    category="Cash Conversion",
                    message=f"Healthy cash conversion: avg CFO/PAT = {avg_ccr:.2f}x. Profits are well-backed by operating cash flows.",
                    metric_value=avg_ccr,
                ))

        # 2. Credit Sales Detection (receivables growing faster than revenue)
        growth_data = [p for p in data if p.receivable_growth_pct is not None and p.revenue_growth_pct is not None]
        if len(growth_data) >= 2:
            credit_flags = 0
            for p in growth_data[-3:]:
                if (p.receivable_growth_pct is not None and p.revenue_growth_pct is not None
                        and p.receivable_growth_pct > p.revenue_growth_pct * 1.5
                        and p.receivable_growth_pct > 10):
                    credit_flags += 1

            if credit_flags >= 2:
                diags.append(CashFlowDiagnostic(
                    severity="red",
                    category="Credit Sales",
                    message=f"Receivables growing significantly faster than revenue in {credit_flags} recent periods. Revenue may be credit-driven or collections are slowing.",
                    metric_value=float(credit_flags),
                ))
            elif credit_flags == 1:
                diags.append(CashFlowDiagnostic(
                    severity="yellow",
                    category="Credit Sales",
                    message="Receivables outpaced revenue growth in 1 recent period. Monitor collection efficiency.",
                    metric_value=1.0,
                ))
            else:
                diags.append(CashFlowDiagnostic(
                    severity="green",
                    category="Credit Sales",
                    message="Receivable growth is in line with receivable growth. No signs of credit-driven revenue.",
                    metric_value=0.0,
                ))

        # 3. Working Capital Cycle
        wc_data = [p for p in data if p.working_capital_days is not None]
        if wc_data:
            latest_wc = wc_data[-1].working_capital_days
            if latest_wc is not None:
                if latest_wc > 120:
                    diags.append(CashFlowDiagnostic(
                        severity="red",
                        category="Working Capital",
                        message=f"Working capital cycle is {latest_wc:.0f} days - very high. Cash is locked up in operations.",
                        metric_value=latest_wc,
                    ))
                elif latest_wc > 60:
                    diags.append(CashFlowDiagnostic(
                        severity="yellow",
                        category="Working Capital",
                        message=f"Working capital cycle is {latest_wc:.0f} days. Moderate - some cash efficiency improvement possible.",
                        metric_value=latest_wc,
                    ))
                elif latest_wc < 0:
                    diags.append(CashFlowDiagnostic(
                        severity="green",
                        category="Working Capital",
                        message=f"Negative working capital cycle ({latest_wc:.0f} days) - business is funded by suppliers. Very capital efficient!",
                        metric_value=latest_wc,
                    ))
                else:
                    diags.append(CashFlowDiagnostic(
                        severity="green",
                        category="Working Capital",
                        message=f"Working capital cycle is {latest_wc:.0f} days - healthy and efficient.",
                        metric_value=latest_wc,
                    ))

        # 4. Free Cash Flow trend
        fcf_data = [p for p in data if p.free_cash_flow is not None]
        if len(fcf_data) >= 3:
            neg_count = sum(1 for p in fcf_data[-3:] if p.free_cash_flow < 0)
            if neg_count >= 3:
                diags.append(CashFlowDiagnostic(
                    severity="red",
                    category="Free Cash Flow",
                    message="Negative FCF for 3+ consecutive years. Business is burning cash after investments.",
                    metric_value=float(neg_count),
                ))
            elif neg_count >= 2:
                diags.append(CashFlowDiagnostic(
                    severity="yellow",
                    category="Free Cash Flow",
                    message=f"Negative FCF in {neg_count} of last 3 years. Heavy CAPEX or weak cash generation.",
                    metric_value=float(neg_count),
                ))
            else:
                latest_fcf = fcf_data[-1].free_cash_flow
                diags.append(CashFlowDiagnostic(
                    severity="green",
                    category="Free Cash Flow",
                    message=f"Positive FCF in recent years. Latest FCF: Rs {latest_fcf:,.0f} Cr.",
                    metric_value=latest_fcf,
                ))

        # 5. Borrowings trend
        borr_data = [p for p in data if p.total_borrowings > 0]
        if len(borr_data) >= 2:
            first_borr = borr_data[0].total_borrowings
            last_borr = borr_data[-1].total_borrowings
            if first_borr > 0:
                borr_change = ((last_borr - first_borr) / first_borr) * 100
                if borr_change > 50:
                    diags.append(CashFlowDiagnostic(
                        severity="red",
                        category="Debt Trajectory",
                        message=f"Borrowings increased {borr_change:.0f}% from Rs {first_borr:,.0f} Cr to Rs {last_borr:,.0f} Cr.",
                        metric_value=borr_change,
                    ))
                elif borr_change < -20:
                    diags.append(CashFlowDiagnostic(
                        severity="green",
                        category="Debt Trajectory",
                        message=f"Borrowings reduced {abs(borr_change):.0f}% from Rs {first_borr:,.0f} Cr to Rs {last_borr:,.0f} Cr. Active deleveraging.",
                        metric_value=borr_change,
                    ))



        # 6. SEBI Forensic: 3-Year Rolling Cash Conversion Index
        if len(data) >= 3:
            recent_3 = data[-3:]
            sum_cfo = sum(p.cfo for p in recent_3)
            sum_pat = sum(p.net_profit for p in recent_3)
            if sum_pat > 0:
                cci = sum_cfo / sum_pat
                if cci < 0.5:
                    diags.append(CashFlowDiagnostic(
                        severity="red",
                        category="Forensic Audit (SEBI)",
                        message=f"Severe Red Flag: 3-Year Cash Conversion Index is {cci:.2f}x (<0.5). Potential paper profits or aggressive revenue recognition.",
                        metric_value=cci,
                    ))
                elif cci < 1.0:
                    diags.append(CashFlowDiagnostic(
                        severity="yellow",
                        category="Forensic Audit (SEBI)",
                        message=f"Moderate Quality: 3-Year Cash Conversion Index is {cci:.2f}x. Working capital lockup.",
                        metric_value=cci,
                    ))
                else:
                    diags.append(CashFlowDiagnostic(
                        severity="green",
                        category="Forensic Audit (SEBI)",
                        message=f"High Accounting Quality: 3-Year Cash Conversion Index is {cci:.2f}x. Earnings backed by real cash inflows.",
                        metric_value=cci,
                    ))

        # 7. Bloomberg Analyst: Altman Z-Score (Solvency)
        z_scores = [p.altman_z_score for p in data if p.altman_z_score is not None]
        if z_scores:
            latest_z = z_scores[-1]
            if latest_z < 1.81:
                diags.append(CashFlowDiagnostic(
                    severity="red",
                    category="Solvency (Altman Z)",
                    message=f"Distress Zone: Altman Z-Score is {latest_z:.2f} (<1.81). High financial distress risk.",
                    metric_value=latest_z,
                ))
            elif latest_z <= 2.99:
                diags.append(CashFlowDiagnostic(
                    severity="yellow",
                    category="Solvency (Altman Z)",
                    message=f"Grey Zone: Altman Z-Score is {latest_z:.2f} (1.81 - 2.99). Moderate solvency risk.",
                    metric_value=latest_z,
                ))
            else:
                diags.append(CashFlowDiagnostic(
                    severity="green",
                    category="Solvency (Altman Z)",
                    message=f"Safe Zone: Altman Z-Score is {latest_z:.2f} (>2.99). Low probability of insolvency.",
                    metric_value=latest_z,
                ))

        return diags

    # ------------------------------------------------------------------
    # Cross Validation
    # ------------------------------------------------------------------

    def _cross_validate_annual(
        self, annual: list[CashFlowPeriod], yf_financials: dict
    ) -> list[CashFlowDiagnostic]:
        """Cross-validate annual cash flow data from Screener against yfinance."""
        diags = []
        if not yf_financials or "cash_flow" not in yf_financials:
            return diags

        yf_cf = yf_financials["cash_flow"]
        if yf_cf.empty:
            return diags

        # Map yfinance columns (e.g., "2026-03-31") to year labels (e.g., "Mar 2026")
        for p in annual:
            matched_col = None
            for col in yf_cf.columns:
                if col == "index":
                    continue
                col_q = self._normalize_date_to_quarter(col)
                if col_q == p.period:
                    matched_col = col
                    break

            if matched_col:
                metric_col = "index"
                yf_cfo = self._get_metric(yf_cf, metric_col, matched_col, ["Operating Cash Flow"]) / 1e7
                yf_cfi = self._get_metric(yf_cf, metric_col, matched_col, ["Investing Cash Flow"]) / 1e7
                yf_cff = self._get_metric(yf_cf, metric_col, matched_col, ["Financing Cash Flow"]) / 1e7

                # Check CFO discrepancy
                if p.cfo and yf_cfo:
                    diff_pct = abs(p.cfo - yf_cfo) / max(abs(p.cfo), 1.0) * 100
                    if diff_pct > 15 and abs(p.cfo - yf_cfo) > 50:  # >15% difference and >50 Cr absolute difference
                        diags.append(CashFlowDiagnostic(
                            severity="yellow",
                            category="Cross Validation",
                            message=f"Discrepancy in CFO for {p.period}: Screener reports Rs {p.cfo:,.0f} Cr, Yahoo reports Rs {yf_cfo:,.0f} Cr (+-{diff_pct:.0f}%). Check reports.",
                            metric_value=diff_pct,
                        ))

        return diags

    # ------------------------------------------------------------------
    # Quality score
    # ------------------------------------------------------------------

    def _compute_quality_score(
        self, annual: list[CashFlowPeriod], diagnostics: list[CashFlowDiagnostic]
    ) -> float:
        """Compute 0-100 cash quality score from diagnostics."""
        if not diagnostics:
            return 50.0

        score = 50.0
        for d in diagnostics:
            if d.severity == "green":
                score += 10
            elif d.severity == "yellow":
                score -= 5
            elif d.severity == "red":
                score -= 15

        return max(0.0, min(100.0, round(score, 1)))

    def _generate_summary(self, annual: list[CashFlowPeriod], score: float) -> str:
        """One-liner summary of cash position."""
        if score >= 75:
            return "Strong cash generator. Operating profits are well-backed by real cash flows."
        elif score >= 50:
            return "Adequate cash position. Some areas need monitoring (working capital or conversion efficiency)."
        elif score >= 30:
            return "Weak cash position. Significant concerns around cash conversion or credit quality."
        else:
            return "Poor cash health. Business may be showing profits without generating actual cash."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_metric(
        df: pd.DataFrame, metric_col: str, value_col: str, search_terms: list[str]
    ) -> float:
        """Extract a numeric value from a DataFrame row matching any of the search terms."""
        for term in search_terms:
            mask = df[metric_col].astype(str).str.contains(term, case=False, na=False)
            matched = df[mask]
            if not matched.empty:
                try:
                    val = str(matched.iloc[0][value_col]).replace(",", "").replace("%", "").strip()
                    if val and val.lower() not in ("nan", "", "none", "-"):
                        return float(val)
                except (ValueError, TypeError, KeyError):
                    continue
        return 0.0
