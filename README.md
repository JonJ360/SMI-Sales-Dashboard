# SMI Sales Intelligence

Live, authenticated sales reporting sourced from read-only Dynamics GP SQL. It preserves Anthony Berger's current report measures and reporting sections while using the AR CRM navigation model and Asset Tracker blue visual system.

## Report contract

- Posted, normal invoices and returns
- Net sales = invoice `Subtotal` less return `Subtotal`
- Cost = source extended-cost magnitude, rounded to cents and signed by invoice/return type; costs above sales are not replaced
- Profit = net sales minus signed source cost; losses are retained
- Zero/missing costs remain zero under the existing policy; profit is not fully costed or GL net income. Missing purchase-cost linkage is not repaired by this change.
- Invoice count = distinct invoice SOP number
- Open orders = remaining subtotal on normal, unposted orders
- Periods: rolling 30 days (`1M`), YTD, any selectable month, and 2024–2026 history through the current as-of date
- Overview, Salespeople, Branches, and Customers each retain their own period and month filter; Open Orders is current-only, while Weekly Report and Margin Exceptions keep their dedicated controls
- Like-for-like comparisons: prior-year rolling 30-day, YTD, and month; the 2024–2026 window compares with 2021–2023 through the same month/day cutoff
- All-salespeople report shows current-period sales, comparable prior-period sales, and dollar change
- Click-through salesperson detail uses the selected period for customer rankings and totals, with phone-friendly customer cards
- Customer detail compares monthly net sales for 2025 and 2026 in aligned bars
- Tickets written today = distinct normal orders by GP `Created Date`, with `Subtotal` dollars
- Invoices posted today = distinct normal posted invoices by GP `Posted Date`, with `Subtotal` dollars
- Weekly Report = live normal GP sales orders grouped Sunday–Saturday by `CREATDDT`
- Weekly Total $ = order header `SUBTOTAL` (tax excluded)
- Weekly stock metrics = inventory items with `IV00101.ITEMTYPE = 1`; cost uses the absolute source line extended cost, rounded to cents, without a cost-over-sales substitution
- Weekly salesperson rows drill into their open or transferred/history order documents
- V1.16: expand any order number to see every source line, item ID/description, sequence/component, quantity/UOM, sales, signed source cost, absolute cost, profit/margin, and stock contribution
- Line flags explain cost above price, zero/missing cost, nonpositive sales with cost, negative source cost, nonstock/missing item types, and items excluded only from the separate Margin Exceptions screen. Flags do not exclude lines or change costing.
- Order detail preserves the V1.15 cost policy and all header/weekly totals. It shows stock reconciliation and all-line sales versus header subtotal; changes between sequential GP reads are disclosed rather than forced to balance. Orders are not posted-invoice/GL profit.
- Detail shares the existing authenticated JSON snapshot, with lossless columnar `order_line_fields` / `order_lines` transport. Legacy snapshots show an explicit unavailable message, not fabricated lines.
- The snapshot carries the current week plus the previous 15 weeks; Tickets Written Today opens the same report in Today mode
- Margin Exceptions reviews posted, nonvoid SMI invoices from the trailing 30 days by GP posting date
- Margin price and cost use raw `SOP30300.XTNDPRCE` and `SOP30300.EXTDCOST`; screening thresholds and exclusions are independent of the sales/weekly cost policy
- Exceptions include negative/zero-cost issues, invoice margin below 10%, and item margin at least 15 percentage points below its historical median
- Historical item comparison requires at least 5 prior posted lines and $500 of prior sales within the trailing 395-day extraction
- Approved noncost or non-margin items are excluded from margin calculations and historical baselines: `107517`, `207527`, `227528`, `41389`, `41390`, `7518`, `7519`, `CREDIT CARD SURCHARGE`, `DC`, `DOSENGO`, `FREIGHT`, `LFS`, `LFSB`, `LOGBR`, `MILEAGE`, `RV41390`, `SURCHARGE`, and `U1700`
- GP item class `MISC` is excluded from margin calculations and historical baselines
- Rebar is excluded using GP item master rules: item class `REBAR`, or item class `STEEL` with user category 1 equal to `50`
- The dashboard defaults to the latest posting day and supports selectable day or Sunday–Saturday week views
- Margin Exceptions is dashboard-only and refreshes through the existing live snapshot pipeline

## V1.17 — posted salesperson document drilldown

Click a salesperson, then a document number. The selected report period/date range is retained.
The default list is **posted normal invoices only** (no open/unposted orders), lowest profit first.
Switch to Posted returns for the separate signed credits that reconcile report net totals.
Search matches document/customer/branch; pagination retains every matching document (50 per page).

- The existing `SalesTransactions` header contract is unchanged: document date, historical
  document salesperson, per-type/SOP de-duplication, normal posted Invoice/Return only.
- One columnar `invoice_drilldown` object covers selectable dates from 2024 through as-of.
  It reuses the Weekly drilldown's lossless columnar/lazy-render pattern, not its stock-only math.
- `SOP30300` lines join exact scoped headers by SOPTYPE + SOPNUMBE. Every line/component
  is included, including nonstock/comment/surcharge lines; no margin-screen exclusions.
- Header totals retain the existing signed absolute cost policy. Line prices retain signed
  invoice prices; return prices are negative magnitudes. Costs are absolute for invoices,
  negative absolute for returns; signed source EXTDCOST is also displayed. Zero costs stay zero.
- Sales, cost, profit, margin, quantity/UOM, item/description and line/component ID are visible.
  Negative profit stays visible. Undefined zero-sales margins display a dash.
- Header less line sales/cost/profit residuals are explicit, including missing line groups;
  no balancing plug, cost repair, or manual margin override is introduced. Sequential GP reads
  can race, and header-cost vs line-cost differences are not accounting repairs.
- Net invoice/return-to-report bridge is checked before search/type filtering. Older snapshots
  show an explicit unavailable-detail notice. Weekly Report and Open Orders are unchanged.
- Prior-year comparison totals remain aggregates; this drilldown follows the selected current
  period, not the prior-period cohort. Profit is not fully costed or GL net income.

## Refresh

```bash
python scripts/sales_sync.py --output data/sales.json
python scripts/publish_snapshot.py --snapshot data/sales.json --credentials "%LOCALAPPDATA%/hermes/arcrm/credentials/current-ar.json"
```

For an explicitly approved controlled recovery, the installed normal entrypoint accepts
`python "%LOCALAPPDATA%/hermes/scripts/smi_sales_refresh.py" --single-attempt`.
It still extracts and validates GP data, then stages/promotes/verifies using the existing scoped identities.
The opt-in flag disables automatic retries for **every** publisher RPC, including staging,
promotion, heartbeat and metadata; it is also accepted by `scripts/publish_snapshot.py`.
Without it, the existing two-attempt transient-error behavior is unchanged.
The five-minute Hermes job uses `smi_sales_refresh_scheduled.py`, which always passes
`--single-attempt` to the normal entrypoint. Install both tracked `scripts/smi_sales_refresh*.py`
files beside each other in the default profile scripts directory; only the scheduled
entrypoint forces no-replay. Exceptions fail the job rather than retrying within a run.
A timeout is indeterminate, not proof that the server did nothing: stop, inspect current
metadata and server health, and do not blindly rerun. This flag does not resume a paused
scheduler, acquire a job guard, or replace the fresh host-load/overlap safety checks.

The SQL password and Supabase role tokens remain outside the repository. `data/sales.json` is local-only and ignored by Git.

## Local preview

```bash
python -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/`.

## Production

GitHub Pages serves the static shell. The browser requires the same Supabase login as the AR CRM and reads only `smi_sales_current_snapshot()`. Invoice/return and line detail is available only inside the authenticated snapshot; raw business data is never committed to the public Pages repository.

## Tests

```bash
python -m pytest tests -q
```
