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

INVOICE_SQL = """
WITH invoices AS (
  SELECT
    LTRIM(RTRIM([SOP Number])) AS sop,
    CAST([Document Date] AS date) AS document_date,
    LTRIM(RTRIM([Customer Name])) AS customer,
    LTRIM(RTRIM([Salesperson ID])) AS salesperson,
    LTRIM(RTRIM([Location Code])) AS location,
    CAST([Subtotal] AS float) AS sales,
    CAST([Extended Cost] AS float) AS extended_cost,
    ROW_NUMBER() OVER (
      PARTITION BY [SOP Number]
      ORDER BY [Document Date] DESC, [Posted Date] DESC
    ) AS rn
  FROM dbo.SalesTransactions
  WHERE [SOP Type] = 'Invoice'
    AND [Posting Status] = 'Posted'
    AND [Void Status] = 'Normal'
    AND [Document Date] >= '2024-01-01'
    AND [Document Date] < DATEADD(day, 1, CAST(GETDATE() AS date))
)
SELECT sop, document_date, customer, salesperson, location, sales, extended_cost
FROM invoices WHERE rn = 1
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


def normalize_invoice(row: Mapping[str, Any]) -> dict[str, Any]:
    sales = round(float(row.get("sales") or 0), 2)
    raw_cost = float(row.get("extended_cost") or 0)
    cost = sales * 0.10 if raw_cost > sales else raw_cost
    return {
        "sop": str(row.get("sop") or "").strip(),
        "date": _date(row.get("date") or row.get("document_date")),
        "customer": str(row.get("customer") or "Unknown").strip() or "Unknown",
        "salesperson": str(row.get("salesperson") or "Unassigned").strip() or "Unassigned",
        "location": str(row.get("location") or "Unassigned").strip() or "Unassigned",
        "sales": sales,
        "cost": round(cost, 2),
        "profit": round(sales - cost, 2),
    }


def _totals(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    return {
        "sales": round(sum(float(r["sales"]) for r in rows), 2),
        "cost": round(sum(float(r["cost"]) for r in rows), 2),
        "profit": round(sum(float(r["profit"]) for r in rows), 2),
        "invoices": len({str(r["sop"]) for r in rows}),
        "customers": len({str(r["customer"]) for r in rows}),
    }


def _rank(rows: list[dict[str, Any]], key: str, limit: int | None = None) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    ranked = [{"name": name, **_totals(items)} for name, items in groups.items()]
    ranked.sort(key=lambda item: (-item["sales"], item["name"]))
    return ranked[:limit] if limit else ranked


def build_snapshot(rows: Iterable[Mapping[str, Any]], as_of: dt.date | None = None) -> dict[str, Any]:
    as_of = as_of or dt.date.today()
    unique: dict[str, dict[str, Any]] = {}
    for source in rows:
        row = normalize_invoice(source)
        if row["sop"] and row["date"] <= as_of:
            unique[row["sop"]] = row
    invoices = list(unique.values())
    years = {str(year): _totals([r for r in invoices if r["date"].year == year]) for year in YEARS}
    monthly = []
    for year in YEARS:
        for month in range(1, 13):
            total = _totals([r for r in invoices if r["date"].year == year and r["date"].month == month])
            monthly.append({"year": year, "month": month, **total})
    period_start = choose_period_start("1M", as_of)
    rolling = [r for r in invoices if period_start <= r["date"] <= as_of]
    ytd = [r for r in invoices if r["date"].year == as_of.year and r["date"] <= as_of]
    full = invoices
    def rankings(period_rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "salespeople": _rank(period_rows, "salesperson"),
            "branches": _rank(period_rows, "location"),
            "customers": _rank(period_rows, "customer", 25),
        }
    return {
        "as_of": as_of.isoformat(),
        "source": "Dynamics GP SQL",
        "returns_included": False,
        "years": years,
        "periods": {"1M": _totals(rolling), "YTD": _totals(ytd), "FULL": _totals(full)},
        "monthly": monthly,
        "rankings": {"1M": rankings(rolling), "YTD": rankings(ytd), "FULL": rankings(full)},
        "salespeople": _rank(ytd, "salesperson"),
        "branches": _rank(ytd, "location"),
        "customers": _rank(ytd, "customer", 25),
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


def extract() -> dict[str, Any]:
    with connect() as connection:
        cursor = connection.cursor()
        cols = ["sop", "document_date", "customer", "salesperson", "location", "sales", "extended_cost"]
        invoice_rows = [dict(zip(cols, row)) for row in cursor.execute(INVOICE_SQL).fetchall()]
        order_cols = ["sop", "salesperson", "location", "amount"]
        order_rows = [dict(zip(order_cols, row)) for row in cursor.execute(OPEN_ORDER_SQL).fetchall()]
    snapshot = build_snapshot(invoice_rows)
    snapshot["open_orders"] = build_open_orders(order_rows)
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
    print(json.dumps({"output": str(path.resolve()), "as_of": snapshot["as_of"], "sha256": snapshot["sha256"], "ytd_sales": snapshot["periods"]["YTD"]["sales"], "open_orders": snapshot["open_orders"]["amount"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
