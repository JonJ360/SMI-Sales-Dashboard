import datetime as dt
import unittest
from unittest.mock import patch

import scripts.sales_sync as sales_sync

from scripts.sales_sync import (
    MARGIN_EXCEPTION_SQL,
    TODAY_ACTIVITY_SQL,
    TRANSACTION_SQL,
    WEEKLY_ORDER_SQL,
    build_margin_exceptions,
    build_today_activity,
    build_weekly_reports,
    build_snapshot,
    choose_period_start,
    extract,
    normalize_invoice,
    normalize_transaction,
)


class SalesSyncTests(unittest.TestCase):
    def test_margin_exception_sql_uses_posted_nonvoid_invoice_lines_and_raw_cost(self):
        for token in (
            "FROM dbo.SOP30200 h", "JOIN dbo.SOP30300 l",
            "h.SOPTYPE = 3", "h.VOIDSTTS = 0", "h.POSTEDDT",
            "l.XTNDPRCE", "l.EXTDCOST", "h.SUBTOTAL", "h.EXTDCOST",
            "LEFT JOIN dbo.IV00101 i", "i.ITMCLSCD", "i.USCATVLS_1",
        ):
            self.assertIn(token, MARGIN_EXCEPTION_SQL)
        self.assertIn("l.SOPTYPE = h.SOPTYPE", MARGIN_EXCEPTION_SQL)
        self.assertIn("l.SOPNUMBE = h.SOPNUMBE", MARGIN_EXCEPTION_SQL)

    def test_margin_exceptions_flag_cost_low_margin_and_historical_item_deviation(self):
        history = [
            {"sop": f"H{i}", "document_date": "2026-08-01", "posted_date": "2026-08-01",
             "customer": "History", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 100, "header_cost": 70, "line_sequence": i,
             "item": "A", "description": "Widget", "line_sales": 100, "line_cost": 70}
            for i in range(5)
        ]
        recent = [
            {"sop": "LOW", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Low Co", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 100, "header_cost": 91, "line_sequence": 1,
             "item": "A", "description": "Widget", "line_sales": 100, "line_cost": 91},
            {"sop": "ZERO", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Zero Co", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 100, "header_cost": 0, "line_sequence": 1,
             "item": "B", "description": "Missing cost", "line_sales": 100, "line_cost": 0},
            {"sop": "NEG", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Negative Co", "salesperson": "RICK", "location": "BIS",
             "header_sales": 100, "header_cost": 120, "line_sequence": 1,
             "item": "C", "description": "Cost over sales", "line_sales": 100, "line_cost": 120},
            {"sop": "OK", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Healthy Co", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 100, "header_cost": 70, "line_sequence": 1,
             "item": "A", "description": "Widget", "line_sales": 100, "line_cost": 70},
        ]

        report = build_margin_exceptions(history + recent, as_of=dt.date(2026, 9, 17))

        self.assertEqual([row["sop"] for row in report["invoices"]], ["NEG", "ZERO", "LOW"])
        by_sop = {row["sop"]: row for row in report["invoices"]}
        self.assertEqual(by_sop["NEG"]["severity"], "Critical")
        self.assertEqual(by_sop["NEG"]["margin_pct"], -20.0)
        self.assertIn("negative_margin", by_sop["NEG"]["reason_codes"])
        self.assertIn("zero_cost", by_sop["ZERO"]["reason_codes"])
        self.assertIn("below_threshold_margin", by_sop["LOW"]["reason_codes"])
        self.assertIn("historical_item_deviation", by_sop["LOW"]["reason_codes"])
        self.assertEqual(by_sop["LOW"]["worst_lines"][0]["historical_margin_pct"], 30.0)
        self.assertEqual(report["summary"]["exceptions"], 3)
        self.assertEqual(report["thresholds"]["minimum_margin_pct"], 10.0)

    def test_margin_exceptions_exclude_noncost_charge_items_from_calculation(self):
        rows = [
            {"sop": "MISC-ONLY", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Misc Co", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 100, "header_cost": 200, "line_sequence": 1,
             "item": "7518", "description": "Miscellaneous", "line_sales": 100, "line_cost": 200},
            {"sop": "MIXED", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Mixed Co", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 200, "header_cost": 270, "line_sequence": 1,
             "item": "A", "description": "Normal item", "line_sales": 100, "line_cost": 70},
            {"sop": "MIXED", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Mixed Co", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 200, "header_cost": 270, "line_sequence": 2,
             "item": "7518", "description": "Miscellaneous", "line_sales": 100, "line_cost": 200},
            {"sop": "FREIGHT-ONLY", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Freight Co", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 100, "header_cost": 0, "line_sequence": 1,
             "item": "FREIGHT", "description": "Freight", "line_sales": 100, "line_cost": 0},
            {"sop": "DELIVERY-ONLY", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Delivery Co", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 100, "header_cost": 0, "line_sequence": 1,
             "item": "LFS", "description": "Local Delivery", "line_sales": 100, "line_cost": 0},
        ]
        for item, description in (
            ("207527", "Rental of Tools"), ("41389", "Misc - Steel"),
            ("41390", "Misc - Tools"), ("U1700", "Used Tools"),
        ):
            rows.append({
                "sop": f"EXCLUDE-{item}", "document_date": "2026-09-17", "posted_date": "2026-09-17",
                "customer": "Excluded Co", "salesperson": "SAM", "location": "FARGO",
                "header_sales": 100, "header_cost": 0, "line_sequence": 1,
                "item": item, "description": description, "line_sales": 100, "line_cost": 0,
            })

        report = build_margin_exceptions(rows, as_of=dt.date(2026, 9, 17))

        self.assertEqual(report["invoices"], [])
        self.assertEqual(report["summary"]["exceptions"], 0)
        self.assertEqual(
            report["excluded_item_numbers"],
            ["207527", "41389", "41390", "7518", "FREIGHT", "LFS", "U1700"],
        )

    def test_margin_exceptions_exclude_gp_rebar_classes_from_calculation(self):
        rows = [
            {"sop": "REBAR-CLASS", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Rebar Co", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 100, "header_cost": 99, "line_sequence": 1,
             "item": "GATOR3", "description": "Gatorbar", "item_class": "REBAR", "category_1": "50",
             "line_sales": 100, "line_cost": 99},
            {"sop": "STEEL-50", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Steel Co", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 100, "header_cost": 99, "line_sequence": 1,
             "item": "R46020", "description": "Rebar", "item_class": "STEEL", "category_1": "50",
             "line_sales": 100, "line_cost": 99},
            {"sop": "OTHER-STEEL", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Other Steel", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 100, "header_cost": 99, "line_sequence": 1,
             "item": "S1", "description": "Other steel", "item_class": "STEEL", "category_1": "61",
             "line_sales": 100, "line_cost": 99},
            {"sop": "MISC-CLASS", "document_date": "2026-09-17", "posted_date": "2026-09-17",
             "customer": "Misc Co", "salesperson": "SAM", "location": "FARGO",
             "header_sales": 100, "header_cost": 0, "line_sequence": 1,
             "item": "COMMENT", "description": "Comment", "item_class": "MISC", "category_1": "TOOLS",
             "line_sales": 100, "line_cost": 0},
        ]

        report = build_margin_exceptions(rows, as_of=dt.date(2026, 9, 17))

        self.assertEqual([row["sop"] for row in report["invoices"]], ["OTHER-STEEL"])
        self.assertEqual(report["excluded_rebar_rule"], {"item_classes": ["REBAR"], "steel_category_1": ["50"]})
        self.assertEqual(report["excluded_item_classes"], ["MISC"])

    def test_source_hash_ignores_refresh_timestamp(self):
        first = {"company": "SMI", "sales": 100, "refreshed_at": "2026-09-14T19:00:00+00:00"}
        second = {**first, "refreshed_at": "2026-09-14T19:05:00+00:00"}

        self.assertEqual(sales_sync.source_sha256(first), sales_sync.source_sha256(second))

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
        detail = snap["customer_details"]["A"]
        self.assertEqual(detail["salespeople"][0]["name"], "SAM")
        self.assertEqual(detail["periods"]["YTD"]["salespeople"][0]["name"], "SAM")
        self.assertEqual(detail["periods"]["YTD"]["salespeople"][0]["sales"], 100.0)
        self.assertEqual(detail["months"]["2026-08"]["salespeople"][0]["sales"], 100.0)

    def test_customer_sales_mix_keeps_returns_and_every_salesperson(self):
        rows = [
            {"sop": f"I{i}", "date": dt.date(2026, 8, 2), "customer": "A", "salesperson": f"P{i:02d}", "location": "FARGO", "sales": float(i + 1), "extended_cost": 0.0}
            for i in range(21)
        ]
        rows.append(normalize_transaction({"sop": "R1", "date": dt.date(2026, 8, 3), "customer": "A", "salesperson": "RETURNS", "location": "FARGO", "sales": 50, "extended_cost": 0, "kind": "Return"}))

        scope = build_snapshot(rows, as_of=dt.date(2026, 9, 13))["customer_details"]["A"]["periods"]["YTD"]

        self.assertEqual(len(scope["salespeople"]), 21)
        self.assertEqual(scope["salespeople"][-1]["name"], "Other / Adjustments")
        self.assertTrue(scope["salespeople"][-1]["sales"] < 0)
        self.assertAlmostEqual(sum(person["sales"] for person in scope["salespeople"]), scope["total"]["sales"])

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

    def test_extract_includes_margin_exception_report(self):
        row = (
            "LOW", dt.date(2026, 9, 17), dt.date(2026, 9, 17), "Low Co", "SAM", "Sam Seller",
            "FARGO", 100, 91, 1, "A", "Widget", "TOOLS", "TOOLS", 100, 91,
        )

        class FakeCursor:
            def execute(self, sql):
                self.sql = sql
                return self

            def fetchall(self):
                return [row] if self.sql == MARGIN_EXCEPTION_SQL else []

        class FakeConnection:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def cursor(self): return FakeCursor()

        with patch("scripts.sales_sync.connect", return_value=FakeConnection()):
            snapshot = extract()

        self.assertEqual(snapshot["margin_exceptions"]["summary"]["exceptions"], 1)
        self.assertEqual(snapshot["margin_exceptions"]["invoices"][0]["sop"], "LOW")

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
