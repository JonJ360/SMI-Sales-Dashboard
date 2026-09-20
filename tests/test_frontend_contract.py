import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def test_today_ticket_and_posted_invoice_cards_show_counts_and_dollars(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for token in ("Tickets Written Today", "Invoices Posted Today", 'id="ticketsTodayKpi"', 'id="invoicesTodayKpi"', "today_activity"):
            self.assertIn(token, html)

    def test_asset_tracker_blue_tokens_and_independent_tab_filters_exist(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for token in ("#E9ECF1", "#FFFFFF", "#222A33", "#2E6FD9", "#1F5AB8"):
            self.assertIn(token, html)
        for view in ("overview", "salespeople", "branches", "customers"):
            self.assertIn(f'id="{view}Period"', html)
            self.assertIn(f'id="{view}Month"', html)
        self.assertIn("viewFilters", html)
        self.assertIn("bindPeriodFilter", html)
        self.assertNotIn('id="monthSelect"', html)
        self.assertNotIn('data-period="1M"', html)

    def test_power_bi_report_sections_exist(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for section in ("Overview", "Salespeople", "Branches", "Customers", "Open Orders", "Weekly Report", "Margin Exceptions"):
            self.assertIn(section, html)

    def test_margin_exception_dashboard_shows_raw_invoice_profitability_and_reasons(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for token in (
            'data-view="margins"', 'id="margins"', "margin_exceptions",
            'id="marginExceptionsKpi"', 'id="marginCriticalKpi"',
            'id="marginLowKpi"', 'id="marginHistoricalKpi"',
            "Extended Price", "Extended Cost", "Profit", "Profit %",
            "renderMarginExceptions", "reasonLabel", "worst_lines",
            "Posted invoices · raw GP line cost", 'id="marginRange"',
            'id="marginDate"', "marginDateBounds", "marginDateWindow",
            "Below 10%", "approved miscellaneous and non-margin items excluded",
        ):
            self.assertIn(token, html)

    def test_weekly_report_and_today_ticket_drilldown_exist(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for token in ('data-view="weekly"', 'id="weekly"', 'id="weeklySelect"',
                      'id="weeklySalespeople"', "openWeeklyReport", "openWeeklyPerson",
                      "weekly_reports", "Tickets Written Today"):
            self.assertIn(token, html)
        self.assertIn('onclick="openWeeklyReport(\'today\')"', html)
        self.assertNotIn('onclick="openWeeklyPerson', html)
        self.assertIn('data-weekly-person=', html)
        self.assertIn("weeklySalespeople.onclick", html)

    def test_freshness_and_sql_source_are_visible(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Last refreshed", html)
        self.assertIn("Dynamics GP SQL", html)
        self.assertIn("smi_sales_snapshot_metadata", html)
        self.assertIn("payload.refreshed_at=metadata.promoted_at", html)
        self.assertIn("metadata.source_sha256===payload.sha256", html)

    def test_unchanged_snapshot_heartbeat_is_atomic(self):
        migration = (ROOT / "supabase" / "migrations" / "003_sales_snapshot_heartbeat.sql").read_text(encoding="utf-8")
        self.assertIn("smi_sales_heartbeat_snapshot", migration)
        self.assertIn("snapshot_id = p_snapshot_id", migration)
        self.assertIn("return found", migration.lower())

    def test_production_data_is_auth_gated_through_supabase(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("smi_sales_current_snapshot", html)
        self.assertIn("signInWithPassword", html)
        self.assertIn('<option value="ben@structuralfab.com">Ben</option>', html)
        migration = (ROOT / "supabase" / "migrations" / "001_sales_snapshot.sql").read_text(encoding="utf-8")
        self.assertIn("auth.uid", migration)
    def test_login_selector_includes_randy_email_without_embedded_pin(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('<option value="randyj@smionline.com">Randy</option>', html)
        self.assertEqual(html.count("randyj@smionline.com"), 1)
        self.assertNotRegex(html, r"(?i)randy.{0,80}(pin|password).{0,20}[0-9]{4,}")

    def test_today_activity_metrics_are_rendered_from_snapshot(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Tickets Written Today", html)
        self.assertIn("Invoices Posted Today", html)
        self.assertIn('id="ticketsTodayKpi"', html)
        self.assertIn('id="invoicesTodayKpi"', html)
        self.assertIn("legacy=state.data.today||{}", html)
        self.assertIn("a=state.data.today_activity", html)
        self.assertIn("count:legacy.tickets_written||0", html)
        self.assertIn("count:legacy.invoices_posted||0", html)
        self.assertIn("ticketsTodayKpi.textContent=number(a.tickets.count)", html)
        self.assertIn("invoicesTodayKpi.textContent=number(a.invoices.count)", html)
        self.assertIn("money(a.tickets.amount)", html)
        self.assertIn("money(a.invoices.amount)", html)
        self.assertEqual(html.count('id="ticketsTodayKpi"'), 1)
        self.assertEqual(html.count('id="invoicesTodayKpi"'), 1)

    def test_sales_drilldown_month_and_comparison_controls_exist(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="salespeopleMonth"', html)
        self.assertIn('id="customersMonth"', html)
        self.assertIn('id="salespersonDrawer"', html)
        self.assertIn("openSalesperson", html)
        self.assertIn("vs. prior year", html)
        self.assertIn("Net Sales", html)
        self.assertIn('id="customerDrawer"', html)
        self.assertIn("openCustomer", html)

    def test_all_salespeople_table_shows_period_comparison_and_dollar_change(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for heading in ("Current Sales", "Prior-Period Sales", "Dollar Change"):
            self.assertIn(heading, html)
        self.assertIn("salespersonComparison:m.salesperson_comparison", html)
        self.assertIn("salespersonComparison:c.salesperson_comparison", html)
        self.assertIn("rows=s.salespersonComparison", html)
        self.assertIn("money(x.current_sales)", html)
        self.assertIn("money(x.prior_sales)", html)
        self.assertIn("customerDollarChange(x.current_sales,x.prior_sales)", html)
        self.assertNotIn("state.period==='FULL'?null:c.prior", html)
        self.assertIn("function comparisonName", html)
        self.assertIn("filterForView(view).period==='FULL'?'prior 3 years':'prior year'", html)

    def test_salesperson_drilldown_uses_month_over_month_columns(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Month-over-Month Net Sales", html)
        self.assertIn("function salespersonMonthlyChart", html)
        self.assertIn("type:'bar'", html)
        self.assertIn("salespersonMonthlyChart(detail.monthly)", html)

    def test_customer_drilldown_uses_only_2025_2026_monthly_bars(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("function customerMonthlyChart", html)
        self.assertIn("years=[2025,2026]", html)
        self.assertIn("customerMonthlyChart(detail.monthly)", html)
        self.assertIn("2025 / 2026", html)

    def test_customer_detail_fills_chart_whitespace_with_current_sales_mix_pie(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for token in ('id="customerSalesMix"', "Sales by Salesperson", "function customerScope", "function customerSalesMixChart"):
            self.assertIn(token, html)
        self.assertIn("type:'doughnut'", html)
        self.assertIn("Math.abs(x.sales)", html)
        self.assertIn("returns / adjustments", html)
        self.assertIn("Net ", html)
        self.assertNotIn("rows.filter(x=>x.sales>0)", html)
        self.assertIn("chart('customerSalesMix',customerSalesMixChart(scope.salespeople))", html)
        self.assertIn("Selected period", html)

    def test_salesperson_customer_list_uses_mobile_cards_without_horizontal_scroll(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="panel-body drawer-customer-wrap"', html)
        self.assertIn('class="drawer-customer-table"', html)
        self.assertIn("#salespersonDrawer .drawer-customer-wrap{overflow:visible}", html)
        self.assertIn("#salespersonDrawer .drawer-customer-table{min-width:0}", html)
        self.assertIn("#salespersonDrawer .drawer-customer-table thead{display:none}", html)

    def test_salesperson_drilldown_has_ytd_sales_and_profit_pies(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="salespersonSalesPie"', html)
        self.assertIn('id="salespersonProfitPie"', html)
        self.assertIn("YTD Sales Total", html)
        self.assertIn("YTD Profit Total", html)
        self.assertIn("Current YTD", html)
        self.assertIn("Prior YTD", html)
        self.assertIn("renderSalespersonPies(detail.monthly)", html)
        self.assertNotIn("Positive net by customer", html)

    def test_salesperson_drilldown_uses_selected_period_customer_totals(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("function selectedSalespersonDetail", html)
        self.assertIn("const selected=selectedSalespersonDetail(detail,view)", html)
        self.assertIn("selected.customers.slice(0,12)", html)
        self.assertIn("Selected period", html)
        self.assertNotIn("detail.customers.slice(0,12)", html)
        self.assertNotIn("Top Customers</span><span class=\"panel-note\">All loaded history", html)

    def test_salesperson_pies_appear_before_customer_section(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("#salespersonDrawer .drawer-pies{order:1}", html)
        self.assertIn("#salespersonDrawer .drawer-grid{order:2}", html)

    def test_prior_year_top_25_customers_show_last_year_this_year_and_dollar_change(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Top 25 Customers — Period Comparison", html)
        self.assertIn("Prior-Period Sales", html)
        self.assertIn("Current Sales", html)
        self.assertIn("Dollar Change", html)
        self.assertIn("function customerDollarChange", html)
        self.assertNotIn('id="customerComparisonBody"', html)

    def test_version_is_visible_beneath_top_left_brand_on_mobile_and_desktop(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('<div class="version">VERSION 1.15</div>', html)
        self.assertNotIn("VERSION 1.3", html)
        self.assertNotIn(".brand .eyebrow,.version,.side-foot{display:none}", html)


if __name__ == "__main__":
    unittest.main()
