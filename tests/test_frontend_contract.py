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
    def test_sales_drilldown_month_and_comparison_controls_exist(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="monthSelect"', html)
        self.assertIn('id="salespersonDrawer"', html)
        self.assertIn("openSalesperson", html)
        self.assertIn("vs. prior year", html)
        self.assertIn("Net Sales", html)
        self.assertIn('id="customerDrawer"', html)
        self.assertIn("openCustomer", html)
        self.assertIn('id="customerComparisonBody"', html)

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

    def test_salesperson_pies_appear_before_customer_section(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("#salespersonDrawer .drawer-pies{order:1}", html)
        self.assertIn("#salespersonDrawer .drawer-grid{order:2}", html)

    def test_customer_watchlist_labels_prior_year_top_25(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Prior-Year Top 25 Customer Watchlist", html)
        self.assertIn("Last Year", html)
        self.assertIn("This Year", html)


if __name__ == "__main__":
    unittest.main()
