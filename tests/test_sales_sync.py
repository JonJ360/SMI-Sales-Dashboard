import datetime as dt
import unittest

from scripts.sales_sync import choose_period_start, normalize_invoice, normalize_transaction, build_snapshot


class SalesSyncTests(unittest.TestCase):
    def test_one_month_period_is_rolling_30_days(self):
        self.assertEqual(choose_period_start("1M", dt.date(2026, 9, 13)), dt.date(2026, 8, 15))

    def test_ytd_period_starts_january_first(self):
        self.assertEqual(choose_period_start("YTD", dt.date(2026, 9, 13)), dt.date(2026, 1, 1))

    def test_cost_guard_matches_power_bi_rule(self):
        row = {"sop":"INV1","date":dt.date(2026, 9, 1),"customer":"ACME","salesperson":"RICK","location":"FARGO","sales":100.0,"extended_cost":140.0}
        normalized = normalize_invoice(row)
        self.assertEqual(normalized["cost"], 10.0)
        self.assertEqual(normalized["profit"], 90.0)

    def test_snapshot_counts_unique_invoices(self):
        rows = [
            {"sop":"INV1","date":dt.date(2026, 9, 1),"customer":"ACME","salesperson":"RICK","location":"FARGO","sales":100.0,"extended_cost":60.0},
            {"sop":"INV1","date":dt.date(2026, 9, 1),"customer":"ACME","salesperson":"RICK","location":"FARGO","sales":100.0,"extended_cost":60.0},
            {"sop":"INV2","date":dt.date(2026, 9, 2),"customer":"BETA","salesperson":"AUSTINH","location":"BIS","sales":200.0,"extended_cost":120.0},
        ]
        snap = build_snapshot(rows, as_of=dt.date(2026, 9, 13))
        self.assertEqual(snap["years"]["2026"]["sales"], 300.0)
        self.assertEqual(snap["years"]["2026"]["invoices"], 2)
        self.assertEqual(snap["years"]["2026"]["profit"], 120.0)

    def test_returns_reduce_sales_and_profit(self):
        invoice = normalize_transaction({"sop":"INV1","date":dt.date(2026,9,1),"customer":"A","salesperson":"SAM","location":"FARGO","sales":300,"extended_cost":180,"kind":"Invoice"})
        returned = normalize_transaction({"sop":"RET1","date":dt.date(2026,9,2),"customer":"A","salesperson":"SAM","location":"FARGO","sales":100,"extended_cost":60,"kind":"Return"})
        snap = build_snapshot([invoice, returned], as_of=dt.date(2026,9,13))
        self.assertEqual(returned["sales"], -100.0)
        self.assertEqual(returned["cost"], -60.0)
        self.assertEqual(snap["periods"]["YTD"]["gross_sales"], 300.0)
        self.assertEqual(snap["periods"]["YTD"]["returns"], 100.0)
        self.assertEqual(snap["periods"]["YTD"]["sales"], 200.0)
        self.assertEqual(snap["periods"]["YTD"]["profit"], 80.0)
        self.assertTrue(snap["returns_included"])

    def test_month_views_and_salesperson_drilldown_exist(self):
        rows = [
            normalize_transaction({"sop":"I1","date":dt.date(2026,8,2),"customer":"A","salesperson":"SAM","location":"FARGO","sales":300,"extended_cost":180,"kind":"Invoice"}),
            normalize_transaction({"sop":"R1","date":dt.date(2026,8,3),"customer":"A","salesperson":"SAM","location":"FARGO","sales":50,"extended_cost":30,"kind":"Return"}),
            normalize_transaction({"sop":"I0","date":dt.date(2025,8,2),"customer":"A","salesperson":"SAM","location":"FARGO","sales":200,"extended_cost":120,"kind":"Invoice"}),
        ]
        snap = build_snapshot(rows, as_of=dt.date(2026,9,13))
        self.assertEqual(snap["months"]["2026-08"]["current"]["sales"], 250.0)
        self.assertEqual(snap["months"]["2026-08"]["prior"]["sales"], 200.0)
        self.assertEqual(snap["months"]["2026-08"]["prior_rankings"]["salespeople"][0]["name"], "SAM")
        self.assertEqual(snap["comparisons"]["YTD"]["prior_rankings"]["salespeople"][0]["sales"], 200.0)
        self.assertIn("SAM", snap["salesperson_details"])
        self.assertEqual(snap["salesperson_details"]["SAM"]["monthly"][1]["returns"], 50.0)

    def test_one_month_rankings_exclude_older_sales(self):
        rows = [
            {"sop":"OLD","date":dt.date(2026, 7, 1),"customer":"OLD CO","salesperson":"OLD","location":"GF","sales":900.0,"extended_cost":500.0},
            {"sop":"NEW","date":dt.date(2026, 9, 1),"customer":"NEW CO","salesperson":"NEW","location":"FARGO","sales":100.0,"extended_cost":60.0},
        ]
        snap = build_snapshot(rows, as_of=dt.date(2026, 9, 13))
        self.assertEqual([r["name"] for r in snap["rankings"]["1M"]["salespeople"]], ["NEW"])


if __name__ == "__main__":
    unittest.main()
