# SMI Sales Intelligence

Live, authenticated sales reporting sourced from read-only Dynamics GP SQL. It preserves Anthony Berger's current report measures and reporting sections while using the AR CRM navigation model and Asset Tracker blue visual system.

## Report contract

- Posted, normal invoices only
- Returns excluded, matching Anthony's current distributed report
- Sales = `Subtotal`
- Cost guard = 10% of sales when source extended cost exceeds sales
- Profit = sales minus guarded cost
- Invoice count = distinct SOP number
- Open orders = remaining subtotal on normal, unposted orders
- Periods: rolling 30 days (`1M`), YTD, and 2024–2026

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
