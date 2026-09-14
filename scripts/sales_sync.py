"""Read-only Dynamics GP extractor for the SMI Sales dashboard."""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
from collections import defaultdict
from ctypes import wintypes
from pathlib import Path
from typing import Any, Iterable, Mapping

import pyodbc

CREDENTIAL_TARGET = "Hermes/ARCRM/SMI-SQL"
SERVER = "192.168.1.25,50497"
DATABASE = "SMI"
SOURCE = "dbo.SalesTransactions"
YEARS = (2024, 2025, 2026)

TRANSACTION_SQL = """
WITH transactions AS (
  SELECT
    LTRIM(RTRIM([SOP Number])) AS sop,
    CAST([Document Date] AS date) AS document_date,
    LTRIM(RTRIM([Customer Name])) AS customer,
    LTRIM(RTRIM([Salesperson ID])) AS salesperson,
    LTRIM(RTRIM([Location Code])) AS location,
    CAST([Subtotal] AS float) AS sales,
    CAST([Extended Cost] AS float) AS extended_cost,
    LTRIM(RTRIM([SOP Type])) AS kind,
    ROW_NUMBER() OVER (
      PARTITION BY [SOP Type], [SOP Number]
      ORDER BY [Document Date] DESC, [Posted Date] DESC
    ) AS rn
  FROM dbo.SalesTransactions
  WHERE [SOP Type] IN ('Invoice', 'Return')
    AND [Posting Status] = 'Posted'
    AND [Void Status] = 'Normal'
    AND [Document Date] >= '2021-01-01'
    AND [Document Date] < DATEADD(day, 1, CAST(GETDATE() AS date))
)
SELECT sop, document_date, customer, salesperson, location, sales, extended_cost, kind
FROM transactions WHERE rn = 1
ORDER BY document_date, sop
"""

OPEN_ORDER_SQL = """
WITH orders AS (
  SELECT
    LTRIM(RTRIM([SOP Number])) AS sop,
    LTRIM(RTRIM([Salesperson ID])) AS salesperson,
    LTRIM(RTRIM([Location Code])) AS location,
    CAST([Remaining Subtotal] AS float) AS amount,
    ROW_NUMBER() OVER (
      PARTITION BY [SOP Number]
      ORDER BY [Document Date] DESC, [Modified Date] DESC
    ) AS rn
  FROM dbo.SalesTransactions
  WHERE [SOP Type] = 'Order'
    AND [Posting Status] = 'Unposted'
    AND [Void Status] = 'Normal'
)
SELECT sop, salesperson, location, amount
FROM orders WHERE rn = 1 AND amount > 0
ORDER BY sop
"""

TODAY_ACTIVITY_SQL = """
WITH documents AS (
  SELECT
    LTRIM(RTRIM([SOP Type])) AS sop_type,
    LTRIM(RTRIM([Posting Status])) AS posting_status,
    LTRIM(RTRIM([SOP Number])) AS sop,
    CAST([Created Date] AS date) AS created_date,
    CAST([Posted Date] AS date) AS posted_date,
    CAST([Subtotal] AS decimal(19,2)) AS amount,
    ROW_NUMBER() OVER (
      PARTITION BY [SOP Type], [SOP Number]
      ORDER BY [Document Date] DESC, [Posted Date] DESC, [Modified Date] DESC
    ) AS rn
  FROM dbo.SalesTransactions
  WHERE [SOP Type] IN ('Order', 'Invoice')
    AND [Void Status] = 'Normal'
)
SELECT 'tickets' AS metric, COUNT(*) AS document_count, COALESCE(SUM(amount), 0) AS amount
FROM documents
WHERE rn = 1 AND sop_type = 'Order' AND created_date = CAST(GETDATE() AS date)
UNION ALL
SELECT 'invoices', COUNT(*), COALESCE(SUM(amount), 0)
FROM documents
WHERE rn = 1 AND sop_type = 'Invoice' AND posting_status = 'Posted'
  AND posted_date = CAST(GETDATE() AS date)
"""

WEEKLY_ORDER_SQL = """
WITH header_source AS (
  SELECT 'open' AS record_status, 0 AS source_rank, SOPTYPE, LTRIM(RTRIM(SOPNUMBE)) AS sop,
         CAST(CREATDDT AS date) AS created_date, LTRIM(RTRIM(SLPRSNID)) AS salesperson,
         LTRIM(RTRIM(LOCNCODE)) AS location, CAST(SUBTOTAL AS decimal(19,2)) AS subtotal,
         DEX_ROW_TS
  FROM dbo.SOP10100
  WHERE SOPTYPE = 2 AND VOIDSTTS = 0
    AND CREATDDT >= DATEADD(day, -111, CAST(GETDATE() AS date))
  UNION ALL
  SELECT 'history', 1, SOPTYPE, LTRIM(RTRIM(SOPNUMBE)), CAST(CREATDDT AS date),
         LTRIM(RTRIM(SLPRSNID)), LTRIM(RTRIM(LOCNCODE)), CAST(SUBTOTAL AS decimal(19,2)),
         DEX_ROW_TS
  FROM dbo.SOP30200
  WHERE SOPTYPE = 2 AND VOIDSTTS = 0
    AND CREATDDT >= DATEADD(day, -111, CAST(GETDATE() AS date))
), headers AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY SOPTYPE, sop ORDER BY source_rank, DEX_ROW_TS DESC
  ) AS rn
  FROM header_source
), line_source AS (
  SELECT 'open' AS record_status, LTRIM(RTRIM(l.SOPNUMBE)) AS sop,
         COUNT(*) AS line_items,
         SUM(CASE WHEN i.ITEMTYPE = 1 THEN CAST(l.XTNDPRCE AS decimal(19,2)) ELSE 0 END) AS stock_total,
         SUM(CASE WHEN i.ITEMTYPE = 1 THEN
               CASE WHEN ABS(l.EXTDCOST) > ABS(l.XTNDPRCE)
                    THEN ABS(CAST(l.XTNDPRCE AS decimal(19,2))) * 0.10
                    ELSE ABS(CAST(l.EXTDCOST AS decimal(19,2))) END
             ELSE 0 END) AS stock_cost
  FROM dbo.SOP10200 l
  JOIN headers h ON h.rn = 1 AND h.record_status = 'open'
    AND h.SOPTYPE = l.SOPTYPE AND h.sop = LTRIM(RTRIM(l.SOPNUMBE))
  LEFT JOIN dbo.IV00101 i ON i.ITEMNMBR = l.ITEMNMBR
  WHERE l.SOPTYPE = 2
  GROUP BY l.SOPNUMBE
  UNION ALL
  SELECT 'history', LTRIM(RTRIM(l.SOPNUMBE)), COUNT(*),
         SUM(CASE WHEN i.ITEMTYPE = 1 THEN CAST(l.XTNDPRCE AS decimal(19,2)) ELSE 0 END),
         SUM(CASE WHEN i.ITEMTYPE = 1 THEN
               CASE WHEN ABS(l.EXTDCOST) > ABS(l.XTNDPRCE)
                    THEN ABS(CAST(l.XTNDPRCE AS decimal(19,2))) * 0.10
                    ELSE ABS(CAST(l.EXTDCOST AS decimal(19,2))) END
             ELSE 0 END)
  FROM dbo.SOP30300 l
  JOIN headers h ON h.rn = 1 AND h.record_status = 'history'
    AND h.SOPTYPE = l.SOPTYPE AND h.sop = LTRIM(RTRIM(l.SOPNUMBE))
  LEFT JOIN dbo.IV00101 i ON i.ITEMNMBR = l.ITEMNMBR
  WHERE l.SOPTYPE = 2
  GROUP BY l.SOPNUMBE
), salesperson_names AS (
  SELECT LTRIM(RTRIM(SLPRSNID)) AS salesperson,
         LTRIM(RTRIM(CONCAT(SLPRSNFN, ' ', SPRSNSMN, ' ', SPRSNSLN))) AS salesperson_name
  FROM dbo.RM00301
)
SELECT h.sop, h.created_date, h.salesperson, COALESCE(NULLIF(n.salesperson_name,''), h.salesperson) AS salesperson_name,
       h.location, h.subtotal, COALESCE(l.line_items,0) AS line_items,
       COALESCE(l.stock_total,0) AS stock_total, COALESCE(l.stock_cost,0) AS stock_cost,
       h.record_status AS status
FROM headers h
LEFT JOIN line_source l ON l.sop = h.sop AND l.record_status = h.record_status
LEFT JOIN salesperson_names n ON n.salesperson = h.salesperson
WHERE h.rn = 1 AND h.created_date <= CAST(GETDATE() AS date)
ORDER BY h.created_date DESC, h.sop
"""

class _CredentialW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
    ]


def read_windows_credential(target: str = CREDENTIAL_TARGET) -> tuple[str, str]:
    if os.name != "nt":
        raise RuntimeError("Windows Credential Manager is required")
    api = ctypes.WinDLL("Advapi32.dll")
    pointer = ctypes.POINTER(_CredentialW)()
    if not api.CredReadW(target, 1, 0, ctypes.byref(pointer)):
        raise RuntimeError(f"Credential not found: {target}")
    try:
        cred = pointer.contents
        user = cred.UserName or ""
        password = ctypes.wstring_at(cred.CredentialBlob, cred.CredentialBlobSize // 2)
    finally:
        api.CredFree(pointer)
    if not user or not password:
        raise RuntimeError("SQL credential is incomplete")
    return user, password


def connect() -> pyodbc.Connection:
    user, password = read_windows_credential()
    try:
        return pyodbc.connect(
            "DRIVER={SQL Server};"
            f"SERVER={SERVER};DATABASE={DATABASE};UID={user};PWD={password};"
            "Encrypt=no;TrustServerCertificate=yes;APP=Hermes SMI Sales Read Only;",
            timeout=15,
        )
    finally:
        password = ""


def choose_period_start(period: str, as_of: dt.date) -> dt.date:
    if period == "1M":
        return as_of - dt.timedelta(days=29)
    if period == "YTD":
        return dt.date(as_of.year, 1, 1)
    if period == "FULL":
        return dt.date(min(YEARS), 1, 1)
    raise ValueError(f"Unsupported period: {period}")


def _date(value: Any) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def normalize_transaction(row: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(row.get("kind") or "Invoice").strip().title()
    sign = -1 if kind == "Return" else 1
    sales_magnitude = abs(round(float(row.get("sales") or 0), 2))
    raw_cost_value = row.get("extended_cost") if row.get("extended_cost") is not None else row.get("cost")
    raw_cost = abs(float(raw_cost_value or 0))
    cost_magnitude = sales_magnitude * 0.10 if raw_cost > sales_magnitude else raw_cost
    sales = sign * sales_magnitude
    cost = sign * round(cost_magnitude, 2)
    return {
        "sop": str(row.get("sop") or "").strip(),
        "date": _date(row.get("date") or row.get("document_date")),
        "customer": str(row.get("customer") or "Unknown").strip() or "Unknown",
        "salesperson": str(row.get("salesperson") or "Unassigned").strip() or "Unassigned",
        "location": str(row.get("location") or "Unassigned").strip() or "Unassigned",
        "kind": kind,
        "sales": sales,
        "cost": cost,
        "profit": round(sales - cost, 2),
    }


def normalize_invoice(row: Mapping[str, Any]) -> dict[str, Any]:
    return normalize_transaction({**row, "kind": "Invoice"})


def _totals(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    invoices = [r for r in rows if r.get("kind", "Invoice") != "Return"]
    returns = [r for r in rows if r.get("kind") == "Return"]
    return {
        "sales": round(sum(float(r["sales"]) for r in rows), 2),
        "gross_sales": round(sum(float(r["sales"]) for r in invoices), 2),
        "returns": round(abs(sum(float(r["sales"]) for r in returns)), 2),
        "cost": round(sum(float(r["cost"]) for r in rows), 2),
        "profit": round(sum(float(r["profit"]) for r in rows), 2),
        "invoices": len({str(r["sop"]) for r in invoices}),
        "return_docs": len({str(r["sop"]) for r in returns}),
        "customers": len({str(r["customer"]) for r in rows}),
    }


def _rank(rows: list[dict[str, Any]], key: str, limit: int | None = None) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    ranked = [{"name": name, **_totals(items)} for name, items in groups.items()]
    ranked.sort(key=lambda item: (-item["sales"], item["name"]))
    return ranked[:limit] if limit else ranked


def _rank_with_other(rows: list[dict[str, Any]], key: str, limit: int = 20) -> list[dict[str, Any]]:
    """Bound chart payload while preserving exact signed totals."""
    ranked = _rank(rows, key)
    if len(ranked) <= limit:
        return ranked
    kept = ranked[:limit]
    kept_names = {item["name"] for item in kept}
    omitted = [row for row in rows if str(row[key]) not in kept_names]
    return kept + [{"name": "Other / Adjustments", **_totals(omitted)}]


def _shift_year(value: dt.date, years: int) -> dt.date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def _safe_prior(value: dt.date) -> dt.date:
    return _shift_year(value, 1)


def _ranking_bundle(period_rows: list[dict[str, Any]], prior_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    customers = _rank(period_rows, "customer", 25)
    if prior_rows is not None:
        prior_by_name = {item["name"]: item["sales"] for item in _rank(prior_rows, "customer")}
        for customer in customers:
            customer["prior_sales"] = prior_by_name.get(customer["name"], 0.0)
    return {
        "salespeople": _rank(period_rows, "salesperson"),
        "branches": _rank(period_rows, "location"),
        "customers": customers,
    }


def _salesperson_details(
    rows: list[dict[str, Any]],
    period_rows: Mapping[str, list[dict[str, Any]]],
    month_rows: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_person[row["salesperson"]].append(row)
    details: dict[str, Any] = {}
    for name, person_rows in by_person.items():
        trend_rows = [row for row in person_rows if row["date"].year in YEARS]
        monthly = []
        for (year, month) in sorted({(r["date"].year, r["date"].month) for r in trend_rows}):
            selected = [r for r in trend_rows if r["date"].year == year and r["date"].month == month]
            monthly.append({"year": year, "month": month, **_totals(selected)})
        def scoped_detail(selected: list[dict[str, Any]]) -> dict[str, Any]:
            selected = [row for row in selected if row["salesperson"] == name]
            return {"total": _totals(selected), "customers": _rank(selected, "customer", 20)}

        details[name] = {
            "total": _totals(person_rows),
            "monthly": monthly,
            "customers": _rank(person_rows, "customer", 20),
            "periods": {period: scoped_detail(selected) for period, selected in period_rows.items()},
            "months": {month: scoped_detail(selected) for month, selected in month_rows.items()},
        }
    return details


def _customer_details(
    rows: list[dict[str, Any]],
    included_names: set[str],
    period_rows: Mapping[str, list[dict[str, Any]]],
    month_rows: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    by_customer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["customer"] in included_names:
            by_customer[row["customer"]].append(row)
    details: dict[str, Any] = {}
    for name, customer_rows in by_customer.items():
        trend_rows = [row for row in customer_rows if row["date"].year in YEARS]
        monthly = []
        for (year, month) in sorted({(r["date"].year, r["date"].month) for r in trend_rows}):
            selected = [r for r in trend_rows if r["date"].year == year and r["date"].month == month]
            monthly.append({"year": year, "month": month, **_totals(selected)})
        def scoped_detail(selected: list[dict[str, Any]]) -> dict[str, Any]:
            selected = [row for row in selected if row["customer"] == name]
            return {"total": _totals(selected), "salespeople": _rank_with_other(selected, "salesperson")}

        details[name] = {
            "total": _totals(customer_rows),
            "monthly": monthly,
            "salespeople": _rank(customer_rows, "salesperson", 20),
            "periods": {period: scoped_detail(selected) for period, selected in period_rows.items()},
            "months": {month: scoped_detail(selected) for month, selected in month_rows.items()},
        }
    return details


def _customer_comparison(current: list[dict[str, Any]], prior: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current_by_name = {item["name"]: item for item in _rank(current, "customer")}
    result = []
    for prior_item in _rank(prior, "customer", 25):
        current_item = current_by_name.get(prior_item["name"], {})
        result.append({
            "name": prior_item["name"],
            "prior_sales": prior_item["sales"],
            "current_sales": current_item.get("sales", 0),
            "prior_profit": prior_item["profit"],
            "current_profit": current_item.get("profit", 0),
            "prior_invoices": prior_item["invoices"],
            "current_invoices": current_item.get("invoices", 0),
        })
    return result


def _salesperson_comparison(current: list[dict[str, Any]], prior: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current_by_name = {item["name"]: item for item in _rank(current, "salesperson")}
    prior_by_name = {item["name"]: item for item in _rank(prior, "salesperson")}
    result = []
    for name in current_by_name.keys() | prior_by_name.keys():
        current_item = current_by_name.get(name, {})
        current_sales = current_item.get("sales", 0.0)
        prior_sales = prior_by_name.get(name, {}).get("sales", 0.0)
        result.append({
            "name": name,
            "current_sales": current_sales,
            "prior_sales": prior_sales,
            "dollar_change": round(current_sales - prior_sales, 2),
        })
    return sorted(result, key=lambda item: (-item["current_sales"], item["name"]))


def build_snapshot(rows: Iterable[Mapping[str, Any]], as_of: dt.date | None = None) -> dict[str, Any]:
    as_of = as_of or dt.date.today()
    unique: dict[str, dict[str, Any]] = {}
    for source in rows:
        row = normalize_transaction(source)
        key = f'{row["kind"]}:{row["sop"]}'
        if row["sop"] and row["date"] <= as_of:
            unique[key] = row
    transactions = list(unique.values())
    years = {str(year): _totals([r for r in transactions if r["date"].year == year]) for year in YEARS}
    monthly = []
    months: dict[str, Any] = {}
    for year in YEARS:
        for month in range(1, 13):
            current = [r for r in transactions if r["date"].year == year and r["date"].month == month]
            prior = [r for r in transactions if r["date"].year == year - 1 and r["date"].month == month]
            total = _totals(current)
            monthly.append({"year": year, "month": month, **total})
            months[f"{year}-{month:02d}"] = {
                "current": total,
                "prior": _totals(prior),
                "rankings": _ranking_bundle(current, prior),
                "prior_rankings": _ranking_bundle(prior),
                "customer_comparison": _customer_comparison(current, prior),
                "salesperson_comparison": _salesperson_comparison(current, prior),
            }
    rolling_start = choose_period_start("1M", as_of)
    rolling = [r for r in transactions if rolling_start <= r["date"] <= as_of]
    prior_rolling_start, prior_as_of = _safe_prior(rolling_start), _safe_prior(as_of)
    prior_rolling = [r for r in transactions if prior_rolling_start <= r["date"] <= prior_as_of]
    ytd = [r for r in transactions if r["date"].year == as_of.year and r["date"] <= as_of]
    prior_ytd = [r for r in transactions if dt.date(as_of.year - 1, 1, 1) <= r["date"] <= prior_as_of]
    full_start = dt.date(min(YEARS), 1, 1)
    full = [r for r in transactions if full_start <= r["date"] <= as_of]
    prior_full_start = full_start.replace(year=full_start.year - len(YEARS))
    prior_full_end = _shift_year(as_of, len(YEARS))
    prior_full = [r for r in transactions if prior_full_start <= r["date"] <= prior_full_end]
    comparisons = {
        "1M": {"current": _totals(rolling), "prior": _totals(prior_rolling), "prior_rankings": _ranking_bundle(prior_rolling), "customer_comparison": _customer_comparison(rolling, prior_rolling), "salesperson_comparison": _salesperson_comparison(rolling, prior_rolling)},
        "YTD": {"current": _totals(ytd), "prior": _totals(prior_ytd), "prior_rankings": _ranking_bundle(prior_ytd), "customer_comparison": _customer_comparison(ytd, prior_ytd), "salesperson_comparison": _salesperson_comparison(ytd, prior_ytd)},
        "FULL": {"current": _totals(full), "prior": _totals(prior_full), "prior_rankings": _ranking_bundle(prior_full), "customer_comparison": _customer_comparison(full, prior_full), "salesperson_comparison": _salesperson_comparison(full, prior_full)},
    }
    period_rankings = {"1M": _ranking_bundle(rolling, prior_rolling), "YTD": _ranking_bundle(ytd, prior_ytd), "FULL": _ranking_bundle(full, prior_full)}
    detail_customers: set[str] = set()
    for month_data in months.values():
        for group in (month_data["rankings"]["customers"], month_data["prior_rankings"]["customers"], month_data["customer_comparison"]):
            detail_customers.update(item["name"] for item in group)
    for period in ("1M", "YTD", "FULL"):
        detail_customers.update(item["name"] for item in period_rankings[period]["customers"])
        detail_customers.update(item["name"] for item in comparisons[period]["prior_rankings"]["customers"])
        detail_customers.update(item["name"] for item in comparisons[period]["customer_comparison"])
    return {
        "as_of": as_of.isoformat(),
        "source": "Dynamics GP SQL",
        "returns_included": True,
        "years": years,
        "periods": {"1M": _totals(rolling), "YTD": _totals(ytd), "FULL": _totals(full)},
        "comparisons": comparisons,
        "monthly": monthly,
        "months": months,
        "rankings": period_rankings,
        "salespeople": _rank(ytd, "salesperson"),
        "branches": _rank(ytd, "location"),
        "customers": _rank(ytd, "customer", 25),
        "salesperson_details": _salesperson_details(
            transactions,
            {"1M": rolling, "YTD": ytd, "FULL": full},
            {
                month: [
                    row for row in transactions
                    if f'{row["date"].year}-{row["date"].month:02d}' == month
                ]
                for month in months
            },
        ),
        "customer_details": _customer_details(
            transactions,
            detail_customers,
            {"1M": rolling, "YTD": ytd, "FULL": full},
            {
                month: [
                    row for row in transactions
                    if f'{row["date"].year}-{row["date"].month:02d}' == month
                ]
                for month in months
            },
        ),
    }


def build_open_orders(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        sop = str(row.get("sop") or "").strip()
        if sop:
            unique[sop] = {
                "sop": sop,
                "salesperson": str(row.get("salesperson") or "Unassigned").strip() or "Unassigned",
                "location": str(row.get("location") or "Unassigned").strip() or "Unassigned",
                "amount": round(float(row.get("amount") or 0), 2),
            }
    orders = list(unique.values())
    def group(key: str) -> list[dict[str, Any]]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in orders:
            buckets[row[key]].append(row)
        result = [{"name": name, "amount": round(sum(x["amount"] for x in vals), 2), "orders": len(vals)} for name, vals in buckets.items()]
        return sorted(result, key=lambda x: (-x["amount"], x["name"]))
    return {"amount": round(sum(r["amount"] for r in orders), 2), "orders": len(orders), "branches": group("location"), "salespeople": group("salesperson")}


def build_today_activity(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    activity = {"tickets": {"count": 0, "amount": 0.0}, "invoices": {"count": 0, "amount": 0.0}}
    for row in rows:
        metric = str(row.get("metric") or "").strip().lower()
        if metric in activity:
            activity[metric] = {
                "count": int(row.get("count") or 0),
                "amount": round(float(row.get("amount") or 0), 2),
            }
    return activity


def _weekly_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stock_total = round(sum(row["stock_total"] for row in rows), 2)
    stock_profit = round(sum(row["stock_profit"] for row in rows), 2)
    return {
        "orders": len(rows),
        "line_items": sum(row["line_items"] for row in rows),
        "total": round(sum(row["total"] for row in rows), 2),
        "stock_total": stock_total,
        "stock_profit": stock_profit,
        "stock_margin_pct": round(100 * stock_profit / stock_total, 2) if stock_total else 0.0,
    }


def build_weekly_reports(
    rows: Iterable[Mapping[str, Any]], as_of: dt.date | None = None, week_count: int = 16
) -> dict[str, Any]:
    as_of = as_of or dt.date.today()
    unique: dict[str, dict[str, Any]] = {}
    for source in rows:
        sop = str(source.get("sop") or "").strip()
        if not sop:
            continue
        stock_total = round(float(source.get("stock_total") or 0), 2)
        stock_cost = round(float(source.get("stock_cost") or 0), 2)
        unique[sop] = {
            "sop": sop,
            "created_date": _date(source.get("created_date")),
            "salesperson": str(source.get("salesperson") or "Unassigned").strip() or "Unassigned",
            "name": str(source.get("salesperson_name") or source.get("salesperson") or "Unassigned").strip() or "Unassigned",
            "location": str(source.get("location") or "Unassigned").strip() or "Unassigned",
            "total": round(float(source.get("subtotal") or 0), 2),
            "line_items": int(source.get("line_items") or 0),
            "stock_total": stock_total,
            "stock_profit": round(stock_total - stock_cost, 2),
            "status": str(source.get("status") or "history").strip().lower(),
        }
    orders = [row for row in unique.values() if row["created_date"] <= as_of]
    current_start = as_of - dt.timedelta(days=(as_of.weekday() + 1) % 7)

    def report(selected: list[dict[str, Any]], start: dt.date, end: dt.date) -> dict[str, Any]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in selected:
            groups[row["salesperson"]].append(row)
        people = []
        for salesperson, person_orders in groups.items():
            name = person_orders[0]["name"]
            person_orders.sort(key=lambda item: (item["created_date"], item["sop"]), reverse=True)
            display_orders = [{
                key: row[key] for key in (
                    "sop", "location", "total", "line_items", "stock_total", "stock_profit", "status"
                )
            } | {"created_date": row["created_date"].isoformat()} for row in person_orders]
            people.append({"salesperson": salesperson, "name": name, **_weekly_totals(person_orders), "orders": display_orders})
        people.sort(key=lambda item: (-item["total"], item["name"]))
        return {"start": start.isoformat(), "end": end.isoformat(), "totals": _weekly_totals(selected), "salespeople": people}

    weeks = []
    for index in range(week_count):
        start = current_start - dt.timedelta(days=7 * index)
        end = start + dt.timedelta(days=6)
        weeks.append(report([row for row in orders if start <= row["created_date"] <= end], start, end))
    today_report = report([row for row in orders if row["created_date"] == as_of], as_of, as_of)
    return {"weeks": weeks, "today": today_report}


def extract() -> dict[str, Any]:
    with connect() as connection:
        cursor = connection.cursor()
        cols = ["sop", "document_date", "customer", "salesperson", "location", "sales", "extended_cost", "kind"]
        transaction_rows = [dict(zip(cols, row)) for row in cursor.execute(TRANSACTION_SQL).fetchall()]
        order_cols = ["sop", "salesperson", "location", "amount"]
        order_rows = [dict(zip(order_cols, row)) for row in cursor.execute(OPEN_ORDER_SQL).fetchall()]
        activity_cols = ["metric", "count", "amount"]
        activity_rows = [dict(zip(activity_cols, row)) for row in cursor.execute(TODAY_ACTIVITY_SQL).fetchall()]
        weekly_cols = ["sop", "created_date", "salesperson", "salesperson_name", "location", "subtotal", "line_items", "stock_total", "stock_cost", "status"]
        weekly_rows = [dict(zip(weekly_cols, row)) for row in cursor.execute(WEEKLY_ORDER_SQL).fetchall()]
    snapshot = build_snapshot(transaction_rows)
    snapshot["open_orders"] = build_open_orders(order_rows)
    snapshot["today_activity"] = build_today_activity(activity_rows)
    snapshot["weekly_reports"] = build_weekly_reports(weekly_rows)
    snapshot["today"] = {
        "tickets_written": snapshot["today_activity"]["tickets"]["count"],
        "invoices_posted": snapshot["today_activity"]["invoices"]["count"],
    }
    snapshot["refreshed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    snapshot["sha256"] = hashlib.sha256(canonical).hexdigest()
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/sales.json")
    args = parser.parse_args()
    snapshot = extract()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    temp.replace(path)
    print(json.dumps({"output": str(path.resolve()), "as_of": snapshot["as_of"], "sha256": snapshot["sha256"], "ytd_sales": snapshot["periods"]["YTD"]["sales"], "open_orders": snapshot["open_orders"]["amount"], "today_activity": snapshot["today_activity"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
