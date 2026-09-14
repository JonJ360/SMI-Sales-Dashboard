# SMI Sales Intelligence

Live, authenticated sales reporting sourced from read-only Dynamics GP SQL. It preserves Anthony Berger's current report measures and reporting sections while using the AR CRM navigation model and Asset Tracker blue visual system.

## Report contract

- Posted, normal invoices and returns
- Net sales = invoice `Subtotal` less return `Subtotal`
- Cost guard = 10% of sales when source extended cost exceeds sales
- Profit = sales minus guarded cost
- Invoice count = distinct invoice SOP number
- Open orders = remaining subtotal on normal, unposted orders
- Periods: rolling 30 days (`1M`), YTD, any selectable month, and 2024–2026 history through the current as-of date
- Like-for-like comparisons: prior-year rolling 30-day, YTD, and month; the 2024–2026 window compares with 2021–2023 through the same month/day cutoff
- All-salespeople report shows current-period sales, comparable prior-period sales, and dollar change
- Click-through salesperson detail uses the selected period for customer rankings and totals
- Tickets written today = distinct normal orders by GP `Created Date`, with `Subtotal` dollars
- Invoices posted today = distinct normal posted invoices by GP `Posted Date`, with `Subtotal` dollars

## Refresh

```bash
python scripts/sales_sync.py --output data/sales.json
python scripts/publish_snapshot.py --snapshot data/sales.json --credentials "%LOCALAPPDATA%/hermes/arcrm/credentials/current-ar.json"
```

The SQL password and Supabase role tokens remain outside the repository. `data/sales.json` is local-only and ignored by Git.

## Local preview

```bash
python -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/`.

## Production

GitHub Pages serves the static shell. The browser requires the same Supabase login as the AR CRM and reads only `smi_sales_current_snapshot()`. Raw invoice rows are never published.

## Tests

```bash
python -m unittest discover -s tests -q
```
