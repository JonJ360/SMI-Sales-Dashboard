"""SMI-only raw-cost regression contract; no estimated replacement costs."""
import datetime as dt
import re
import pytest
from scripts.sales_sync import normalize_transaction, build_snapshot, build_weekly_reports, WEEKLY_ORDER_SQL


@pytest.mark.parametrize("kind,sales,cost,expected_sales,expected_cost,profit", [
    ("Invoice", 100, 140, 100, 140, -40),
    ("Return", 100, 140, -100, -140, 40),
    ("Return", -100, -140, -100, -140, 40),
    ("Invoice", 0, 25, 0, 25, -25),
    ("Return", 0, 25, 0, -25, 25),
    ("Invoice", 100, 60, 100, 60, 40),
    ("Invoice", 100, 0, 100, 0, 100),
    ("Invoice", 100, None, 100, 0, 100),
])
def test_raw_cost_and_existing_signs(kind, sales, cost, expected_sales, expected_cost, profit):
    row = normalize_transaction(dict(sop="TEST", date=dt.date(2026, 8, 1), kind=kind,
                                     sales=sales, extended_cost=cost))
    assert (row["sales"], row["cost"], row["profit"]) == (expected_sales, expected_cost, profit)


def test_snapshot_propagates_negative_profit_without_losing_sales_or_counts():
    rows = [dict(sop="I", date=dt.date(2026, 8, 1), customer="C", salesperson="P", location="L",
                 kind="Invoice", sales=100, extended_cost=140)]
    snap = build_snapshot(rows, as_of=dt.date(2026, 8, 31))
    for total in [snap["periods"]["YTD"], snap["months"]["2026-08"]["current"],
                  snap["salesperson_details"]["P"]["months"]["2026-08"]["total"],
                  snap["customer_details"]["C"]["months"]["2026-08"]["total"]]:
        assert (total["sales"], total["profit"], total["invoices"]) == (100, -40, 1)


def test_weekly_sql_uses_raw_absolute_stock_cost_in_both_lifecycles():
    sql = re.sub(r"\s+", " ", WEEKLY_ORDER_SQL)
    assert "0.10" not in sql
    assert "ABS(l.EXTDCOST) > ABS(l.XTNDPRCE)" not in sql
    assert sql.count("SUM(CASE WHEN i.ITEMTYPE = 1 THEN ABS(CAST(l.EXTDCOST AS decimal(19,2))) ELSE 0 END)") == 2
    assert "FROM dbo.SOP10200 l" in sql and "FROM dbo.SOP30300 l" in sql


def test_weekly_negative_stock_profit_survives_totals_and_drilldown():
    report = build_weekly_reports([dict(sop="ORDER", created_date=dt.date(2026, 9, 20),
        stock_total=100, stock_cost=140, subtotal=100, line_items=1, salesperson="P")],
        as_of=dt.date(2026, 9, 20))
    for selected in [report["today"], report["weeks"][0]]:
        assert selected["totals"]["stock_profit"] == -40
        assert selected["totals"]["stock_margin_pct"] == -40
        assert selected["salespeople"][0]["orders"][0]["stock_profit"] == -40
