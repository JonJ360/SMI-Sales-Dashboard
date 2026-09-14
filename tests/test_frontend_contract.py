import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def test_asset_tracker_blue_tokens_and_one_month_control_exist(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for token in ("#E9ECF1", "#FFFFFF", "#222A33", "#2E6FD9", "#1F5AB8"):
            self.assertIn(token, html)
        self.assertIn('data-period="1M"', html)

    def test_power_bi_report_sections_exist(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for section in ("Overview", "Salespeople", "Branches", "Customers", "Open Orders"):
            self.assertIn(section, html)

    def test_freshness_and_sql_source_are_visible(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Last refreshed", html)
        self.assertIn("Dynamics GP SQL", html)

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
        self.assertIn("const today=state.data.today", html)
        self.assertIn("ticketsTodayKpi.textContent=number(today.tickets_written)", html)
        self.assertIn("invoicesTodayKpi.textContent=number(today.invoices_posted)", html)

    def test_sales_drilldown_month_and_comparison_controls_exist(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="monthSelect"', html)
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
        self.assertIn("state.period==='FULL'?'prior 3 years':'prior year'", html)

    def test_salesperson_drilldown_uses_month_over_month_columns(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Month-over-Month Net Sales", html)
        self.assertIn("function salespersonMonthlyChart", html)
        self.assertIn("type:'bar'", html)
        self.assertIn("salespersonMonthlyChart(detail.monthly)", html)

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
        self.assertIn("const selected=selectedSalespersonDetail(detail)", html)
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
        self.assertIn("Prior-Year Top 25 Customers — Year-over-Year", html)
        self.assertIn("Last Year", html)
        self.assertIn("This Year", html)
        self.assertIn("Dollar Change", html)
        self.assertIn("function customerDollarChange", html)
        self.assertNotIn('id="customerComparisonBody"', html)

    def test_version_is_visible_beneath_top_left_brand_on_mobile_and_desktop(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('<div class="version">VERSION 1.3</div>', html)
        self.assertNotIn("VERSION 1.2", html)
        self.assertNotIn(".brand .eyebrow,.version,.side-foot{display:none}", html)


if __name__ == "__main__":
    unittest.main()
