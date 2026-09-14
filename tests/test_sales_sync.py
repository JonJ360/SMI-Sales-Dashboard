import datetime as dt
import unittest
from unittest.mock import patch

from scripts.sales_sync import (
    TODAY_ACTIVITY_SQL,
    TRANSACTION_SQL,
    WEEKLY_ORDER_SQL,
    build_today_activity,
    build_weekly_reports,
    build_snapshot,
    choose_period_start,
    extract,
    normalize_invoice,
    normalize_transaction,
)


class SalesSyncTests(unittest.TestCase):
    def test_weekly_order_sql_combines_work_and_history_by_created_date(self):
        self.assertIn("FROM dbo.SOP10100", WEEKLY_ORDER_SQL)
        self.assertIn("FROM dbo.SOP30200", WEEKLY_ORDER_SQL)
        self.assertIn("SOPTYPE = 2", WEEKLY_ORDER_SQL)
        self.assertIn("VOIDSTTS = 0", WEEKLY_ORDER_SQL)
        self.assertIn("IV00101", WEEKLY_ORDER_SQL)
        self.assertIn("ITEMTYPE = 1", WEEKLY_ORDER_SQL)
        self.assertIn("ABS(l.EXTDCOST) > ABS(l.XTNDPRCE)", WEEKLY_ORDER_SQL)
        self.assertIn("CREATDDT", WEEKLY_ORDER_SQL)
        self.assertIn("ROW_NUMBER() OVER", WEEKLY_ORDER_SQL)

    def test_weekly_reports_use_sunday_saturday_and_keep_drilldown(self):
        rows = [
            {"sop":"O1","created_date":dt.date(2026,9,13),"salesperson":"SAM","salesperson_name":"Sam Seller","location":"FARGO","subtotal":100,"line_items":2,"stock_total":80,"stock_cost":50,"status":"open"},
            {"sop":"O2","created_date":dt.date(2026,9,14),"salesperson":"SAM","salesperson_name":"Sam Seller","location":"FARGO","subtotal":200,"line_items":3,"stock_total":150,"stock_cost":90,"status":"history"},
            {"sop":"O3","created_date":dt.date(2026,9,12),"salesperson":"RICK","salesperson_name":"Rick Seller","location":"BIS","subtotal":50,"line_items":1,"stock_total":50,"stock_cost":30,"status":"history"},
        ]
        reports = build_weekly_reports(rows, as_of=dt.date(2026,9,14))
        current = reports["weeks"][0]
        self.assertEqual((current["start"], current["end"]), ("2026-09-13", "2026-09-19"))
        self.assertEqual(current["totals"], {"orders":2,"line_items":5,"total":300.0,"stock_total":230.0,"stock_profit":90.0,"stock_margin_pct":39.13})
        self.assertEqual(current["salespeople"][0]["name"], "Sam Seller")
        self.assertEqual([row["sop"] for row in current["salespeople"][0]["orders"]], ["O2", "O1"])
        self.assertEqual(reports["today"]["totals"]["orders"], 1)

    def test_weekly_report_keeps_duplicate_display_names_separate_by_salesperson_id(self):
        rows = [
            {"sop": "O-1", "created_date": "2026-09-14", "salesperson": "A1", "salesperson_name": "Pat O'Brien", "location": "HQ", "subtotal": 10, "line_items": 1, "stock_total": 10, "stock_cost": 8, "status": "open"},
            {"sop": "O-2", "created_date": "2026-09-14", "salesperson": "B2", "salesperson_name": "Pat O'Brien", "location": "HQ", "subtotal": 20, "line_items": 1, "stock_total": 20, "stock_cost": 16, "status": "open"},
        ]
        report = build_weekly_reports(rows, dt.date(2026, 9, 14), week_count=1)["today"]
        self.assertEqual({person["salesperson"] for person in report["salespeople"]}, {"A1", "B2"})
        self.assertEqual([person["name"] for person in report["salespeople"]], ["Pat O'Brien", "Pat O'Brien"])
        self.assertNotIn("salesperson", report["salespeople"][0]["orders"][0])
        self.assertNotIn("name", report["salespeople"][0]["orders"][0])

    def test_today_activity_sql_uses_distinct_documents_and_separate_gp_dates(self):
        self.assertIn("PARTITION BY [SOP Type], [SOP Number]", TODAY_ACTIVITY_SQL)
        self.assertIn("sop_type = 'Order' AND created_date = CAST(GETDATE() AS date)", TODAY_ACTIVITY_SQL)
        self.assertIn("sop_type = 'Invoice' AND posting_status = 'Posted'", TODAY_ACTIVITY_SQL)
        self.assertIn("posted_date = CAST(GETDATE() AS date)", TODAY_ACTIVITY_SQL)
        self.assertIn("CAST([Subtotal] AS decimal(19,2))", TODAY_ACTIVITY_SQL)

    def test_today_activity_keeps_ticket_and_posted_invoice_counts_and_dollars(self):
        activity = build_today_activity([
            {"metric": "tickets", "count": 12, "amount": 3456.78},
            {"metric": "invoices", "count": 7, "amount": 8901.23},
        ])
        self.assertEqual(activity["tickets"], {"count": 12, "amount": 3456.78})
        self.assertEqual(activity["invoices"], {"count": 7, "amount": 8901.23})

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
        self.assertNotIn("ytd_customers", snap["salesperson_details"]["SAM"])

    def test_customer_comparison_and_drilldown_exist(self):
        rows = [
            normalize_transaction({"sop":"A0","date":dt.date(2025,8,2),"customer":"A","salesperson":"SAM","location":"FARGO","sales":500,"extended_cost":300,"kind":"Invoice"}),
            normalize_transaction({"sop":"B0","date":dt.date(2025,8,2),"customer":"B","salesperson":"RICK","location":"FARGO","sales":400,"extended_cost":240,"kind":"Invoice"}),
            normalize_transaction({"sop":"A1","date":dt.date(2026,8,2),"customer":"A","salesperson":"SAM","location":"FARGO","sales":100,"extended_cost":60,"kind":"Invoice"}),
            normalize_transaction({"sop":"B1","date":dt.date(2026,8,2),"customer":"B","salesperson":"RICK","location":"FARGO","sales":600,"extended_cost":360,"kind":"Invoice"}),
        ]
        snap = build_snapshot(rows, as_of=dt.date(2026,9,13))
        comparison = snap["months"]["2026-08"]["customer_comparison"]
        self.assertEqual([r["name"] for r in comparison], ["A", "B"])
        self.assertEqual(comparison[0]["prior_sales"], 500.0)
        self.assertEqual(comparison[0]["current_sales"], 100.0)
        self.assertIn("A", snap["customer_details"])
        self.assertEqual(snap["customer_details"]["A"]["salespeople"][0]["name"], "SAM")

    def test_one_month_rankings_exclude_older_sales(self):
        rows = [
            {"sop":"OLD","date":dt.date(2026, 7, 1),"customer":"OLD CO","salesperson":"OLD","location":"GF","sales":900.0,"extended_cost":500.0},
            {"sop":"NEW","date":dt.date(2026, 9, 1),"customer":"NEW CO","salesperson":"NEW","location":"FARGO","sales":100.0,"extended_cost":60.0},
        ]
        snap = build_snapshot(rows, as_of=dt.date(2026, 9, 13))
        self.assertEqual([r["name"] for r in snap["rankings"]["1M"]["salespeople"]], ["NEW"])

    def test_salesperson_customer_detail_follows_selected_period(self):
        rows = [
            {"sop":"OLD","date":dt.date(2026, 6, 1),"customer":"OLD CUSTOMER","salesperson":"SAM","location":"FARGO","sales":900.0,"extended_cost":500.0},
            {"sop":"AUG","date":dt.date(2026, 8, 20),"customer":"AUGUST CUSTOMER","salesperson":"SAM","location":"FARGO","sales":200.0,"extended_cost":120.0},
            {"sop":"SEP","date":dt.date(2026, 9, 10),"customer":"SEPTEMBER CUSTOMER","salesperson":"SAM","location":"FARGO","sales":100.0,"extended_cost":60.0},
        ]

        detail = build_snapshot(rows, as_of=dt.date(2026, 9, 13))["salesperson_details"]["SAM"]

        self.assertEqual(detail["periods"]["1M"]["total"]["sales"], 300.0)
        self.assertEqual(
            [customer["name"] for customer in detail["periods"]["1M"]["customers"]],
            ["AUGUST CUSTOMER", "SEPTEMBER CUSTOMER"],
        )
        self.assertEqual(detail["months"]["2026-08"]["total"]["sales"], 200.0)
        self.assertEqual(
            [customer["name"] for customer in detail["months"]["2026-08"]["customers"]],
            ["AUGUST CUSTOMER"],
        )
        self.assertEqual(detail["periods"]["FULL"]["total"]["sales"], 1200.0)

    def test_salesperson_comparisons_follow_rolling_ytd_month_and_three_year_periods(self):
        rows = [
            {"sop":"P30","date":dt.date(2025, 8, 20),"customer":"A","salesperson":"SAM","location":"FARGO","sales":40.0,"extended_cost":20.0},
            {"sop":"C30","date":dt.date(2026, 8, 20),"customer":"A","salesperson":"SAM","location":"FARGO","sales":100.0,"extended_cost":60.0},
            {"sop":"PM","date":dt.date(2025, 7, 10),"customer":"A","salesperson":"SAM","location":"FARGO","sales":300.0,"extended_cost":180.0},
            {"sop":"CM","date":dt.date(2026, 7, 10),"customer":"A","salesperson":"SAM","location":"FARGO","sales":500.0,"extended_cost":300.0},
            {"sop":"P3Y","date":dt.date(2021, 3, 1),"customer":"A","salesperson":"SAM","location":"FARGO","sales":700.0,"extended_cost":420.0},
            {"sop":"P3YLATE","date":dt.date(2023, 12, 1),"customer":"A","salesperson":"SAM","location":"FARGO","sales":9000.0,"extended_cost":5000.0},
            {"sop":"C3Y","date":dt.date(2024, 3, 1),"customer":"A","salesperson":"SAM","location":"FARGO","sales":1000.0,"extended_cost":600.0},
        ]

        snap = build_snapshot(rows, as_of=dt.date(2026, 9, 13))

        rolling = snap["comparisons"]["1M"]["salesperson_comparison"][0]
        self.assertEqual((rolling["current_sales"], rolling["prior_sales"], rolling["dollar_change"]), (100.0, 40.0, 60.0))
        ytd = snap["comparisons"]["YTD"]["salesperson_comparison"][0]
        self.assertEqual((ytd["current_sales"], ytd["prior_sales"], ytd["dollar_change"]), (600.0, 340.0, 260.0))
        month = snap["months"]["2026-07"]["salesperson_comparison"][0]
        self.assertEqual((month["current_sales"], month["prior_sales"], month["dollar_change"]), (500.0, 300.0, 200.0))
        full = snap["comparisons"]["FULL"]["salesperson_comparison"][0]
        self.assertEqual((full["current_sales"], full["prior_sales"], full["dollar_change"]), (1940.0, 700.0, 1240.0))
        self.assertEqual(snap["periods"]["FULL"]["sales"], 1940.0)
        self.assertEqual(snap["comparisons"]["FULL"]["prior"]["sales"], 700.0)

    def test_three_year_comparison_handles_leap_day_like_for_like(self):
        rows = [
            {"sop":"PRIOR","date":dt.date(2021, 2, 28),"customer":"A","salesperson":"SAM","location":"FARGO","sales":25.0,"extended_cost":15.0},
            {"sop":"CURRENT","date":dt.date(2024, 2, 29),"customer":"A","salesperson":"SAM","location":"FARGO","sales":50.0,"extended_cost":30.0},
        ]
        snap = build_snapshot(rows, as_of=dt.date(2024, 2, 29))
        self.assertEqual(snap["comparisons"]["FULL"]["prior"]["sales"], 25.0)

    def test_three_year_comparison_source_does_not_expand_visible_trend_beyond_three_years(self):
        rows = [
            {"sop":"PRIOR","date":dt.date(2021, 2, 28),"customer":"A","salesperson":"SAM","location":"FARGO","sales":25.0,"extended_cost":15.0},
            {"sop":"CURRENT","date":dt.date(2024, 2, 29),"customer":"A","salesperson":"SAM","location":"FARGO","sales":50.0,"extended_cost":30.0},
        ]
        snap = build_snapshot(rows, as_of=dt.date(2024, 2, 29))
        self.assertEqual([row["year"] for row in snap["salesperson_details"]["SAM"]["monthly"]], [2024])
        self.assertEqual([row["year"] for row in snap["customer_details"]["A"]["monthly"]], [2024])

    def test_transaction_source_includes_prior_three_year_window(self):
        self.assertIn("[Document Date] >= '2021-01-01'", TRANSACTION_SQL)

    def test_daily_activity_uses_created_date_for_orders_and_posted_date_for_invoices(self):
        self.assertIn("[SOP Type] IN ('Order', 'Invoice')", TODAY_ACTIVITY_SQL)
        self.assertIn("[Void Status] = 'Normal'", TODAY_ACTIVITY_SQL)
        self.assertIn("created_date = CAST(GETDATE() AS date)", TODAY_ACTIVITY_SQL)
        self.assertIn("posting_status = 'Posted'", TODAY_ACTIVITY_SQL)
        self.assertIn("posted_date = CAST(GETDATE() AS date)", TODAY_ACTIVITY_SQL)
        self.assertIn("PARTITION BY [SOP Type], [SOP Number]", TODAY_ACTIVITY_SQL)
        self.assertEqual(
            build_today_activity([
                {"metric": "tickets", "count": 7, "amount": 1234.56},
                {"metric": "invoices", "count": 5, "amount": 789.01},
            ]),
            {
                "tickets": {"count": 7, "amount": 1234.56},
                "invoices": {"count": 5, "amount": 789.01},
            },
        )

    def test_extract_includes_daily_activity_in_snapshot(self):
        class FakeCursor:
            def execute(self, sql):
                self.sql = sql
                return self

            def fetchall(self):
                if self.sql == TODAY_ACTIVITY_SQL:
                    return [("tickets", 7, 1234.56), ("invoices", 5, 789.01)]
                return []

        class FakeConnection:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def cursor(self):
                return FakeCursor()

        with patch("scripts.sales_sync.connect", return_value=FakeConnection()):
            snapshot = extract()

        self.assertEqual(snapshot["today_activity"], {
            "tickets": {"count": 7, "amount": 1234.56},
            "invoices": {"count": 5, "amount": 789.01},
        })
        self.assertEqual(snapshot["today"], {
            "tickets_written": 7,
            "invoices_posted": 5,
        })

    def test_customer_watchlist_uses_prior_year_top_25(self):
        rows = []
        for rank in range(30):
            rows.append(normalize_transaction({"sop":f"P{rank}","date":dt.date(2025,8,2),"customer":f"C{rank:02d}","salesperson":"SAM","location":"FARGO","sales":3000-rank,"extended_cost":1000,"kind":"Invoice"}))
            rows.append(normalize_transaction({"sop":f"C{rank}","date":dt.date(2026,8,2),"customer":f"C{rank:02d}","salesperson":"SAM","location":"FARGO","sales":1000+rank,"extended_cost":500,"kind":"Invoice"}))
        snap = build_snapshot(rows, as_of=dt.date(2026,9,13))
        watchlist = snap["comparisons"]["YTD"]["customer_comparison"]
        self.assertEqual(len(watchlist), 25)
        self.assertEqual(watchlist[0]["name"], "C00")
        self.assertEqual(watchlist[-1]["name"], "C24")
        current_top = snap["rankings"]["YTD"]["customers"][0]
        self.assertEqual(current_top["name"], "C29")
        self.assertEqual(current_top["prior_sales"], 2971.0)


if __name__ == "__main__":
    unittest.main()
