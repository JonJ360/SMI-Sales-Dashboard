# Individual salesperson comparison (v1.24)

Open **Salespeople**, select the period, then select a salesperson. **Export salesperson report** opens a print-ready document; choose **Print / Save as PDF**. While that drawer is open, the main export button also uses the individual-only scope. No salesperson-specific URL/deep link is supported.

## Scope and accounting

- Current dates come from the selected YTD, last 30 days, specific month or full-history window. Each endpoint shifts one calendar year, clamped for February 29. An in-progress month ends on the as-of day in both years. Dates are printed explicitly.
- Invoice/return document dates and exact salesperson identity are used. The model uses integer cents. Net sales = gross invoice headers less signed returns deducted; no cost, margin policy or extraction change.
- Category rows are the union of all current/prior categories, ranked by current dollars with deterministic ties. Prior-only, new, negative and Unclassified rows remain. Shared-scale paired bars show magnitudes; negative bars are striped, with signed dollar values alongside.
- Categories use gross invoice-line sales before returns, including every source line/component. Current GP IV00101 classifications apply to both periods, not historical assignments. The established REBAR rule includes STEEL/category 50. Header/line residuals and missing invoices are disclosed, never allocated.
- Percent change = (current − prior) / abs(prior). Zero prior is New for positive current sales, otherwise N/A. Missing/out-of-coverage detail is Unavailable, not zero. Full history begins January 2024; its one-year-earlier comparison is unavailable with current coverage.
- Existing all-history monthly and monthly-YTD charts remain in the drawer with their original scope. Monthly-YTD pies explicitly disclose full prior calendar months; they are not included in the selected-period individual PDF.

## Export boundary

`ReportExport.exportSalesperson` allowlists **only** `#salespersonComparison` and selected-person metadata. It does not clone the active dashboard, the entire drawer, customer lists, invoice lists, other people, or hidden data. Source SHA, as-of date, refresh heartbeat and capture time are separate. A changed source SHA, loading state, lock or blocked popup prevents export. The captured report does not update with later dashboard changes.

Mobile tables become labeled cards; print restores repeated table headers and vector bars. PDF uses the existing browser print-preview workflow, not a public report upload. Browser print settings (paper, scale, headers/footers) remain user-controlled. Desktop Edge and responsive phone/tablet layouts are exercised; native iPad/Safari print is a separate compatibility check.

## Verification

- `node --test tests/*.test.cjs`: calculation/coverage/source-shape tests, zero and negative bases, prior-only categories, leap endpoints and prototype-like item/category values.
- `python -m pytest tests -q`: existing frontend/data pipeline contracts; optional isolated PostgreSQL suite requires its configured local test database.
- `python tests/verify_salesperson_browser.py --payload <private frozen snapshot> --output <private evidence directory>`: independent Decimal reconciliation, selected-person switching, literal HTML safety, desktop/mobile/tablet screenshots, actual Chromium PDFs, exact cell text, table headers/bars, no other salesperson identities, no company DOM, stale/loading/popup guards.
- Existing category/customer/branch/annual/PDF browser suites remain regression gates. PDF scenarios with an open salesperson drawer now intentionally require the individual comparison instead of underlying dashboard/expanded invoices.

No source payloads, generated PDF files, credentials or screenshots belong in Git/public Pages. This is frontend-only; no GP query, database/auth change, manual refresh or scheduler change is needed.
