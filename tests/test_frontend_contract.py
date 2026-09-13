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
        migration = (ROOT / "supabase" / "migrations" / "001_sales_snapshot.sql").read_text(encoding="utf-8")
        self.assertIn("auth.uid", migration)


if __name__ == "__main__":
    unittest.main()
