# V1.20: customer and salesperson item categories

Status: approved release; activation and live verification evidence are recorded privately under the release evidence directory below.

## Metric and source contract

- Both detail drawers display up to five item categories, descending by gross posted invoice-line sales for the originating tab's selected date filter (YTD, last 30 days, full history, or selected month). Customer and salesperson attribution remains the existing posted header attribution. Overview entry points use the overview filter.
- This is before returns, matching the existing branch item chart. It is not net sales or profit. Signed invoice adjustments, components, nonstock lines and zero values are retained; no margin-screen exclusions are applied. Dollars aggregate in integer cents.
- Source: current SMI `dbo.IV00101`, keyed by exact trimmed `ITEMNMBR`; fields `ITMCLSCD` and `USCATVLS_1`. Categories use actual item class values. The existing reviewed SMI Rebar rule combines class REBAR with STEEL/category 50. No description, SKU-prefix, vendor, or machine-generated classification.
- Current master classifications are not historical classifications. Missing/blank/ambiguous mappings are Unclassified. Conflicting duplicate item mappings are discarded conservatively rather than chosen arbitrarily. Unknowns can appear in the top five.
- The UI discloses all-line sales, other categories outside top five, Unclassified dollars, missing invoice lines, and header less all-line residual. Residuals are not allocated. Existing header revenue, returns, costs, profit, and ranking calculations are unchanged.
- The new `item_categories` payload member is a separate dimension, not a join into any accounting population. Existing SQL queries are unchanged. Extraction adds one SELECT-only item-master query. No schema, authentication, scheduler, refresh runner or publication changes.

## Legacy snapshots and activation boundary

The pre-feature invoice-line payload has no item category fields. Weekly detail has only partial class coverage and omits the category-50 distinction, so it is deliberately NOT used to guess missing historical invoice categories. Legacy snapshots display an explicit unavailable message instead of invented bars or zero sales.

The approved release includes both `item-categories.js` / HTML and the updated extractor. Activation uses only the existing five-minute scheduled refresh; no manual duplicate refresh or schedule/auth/schema change is required. The initial private preview used a frozen snapshot enriched by a bounded SELECT-only master read, with every original business field unchanged. Release verification separately reads the actual serving RPC and compares it with the naturally completed extraction and publication receipt. Browser checks using that captured live payload remain split verification, not an interactive signed-in end-to-end session.

Release evidence: `C:/Users/jonj/AppData/Local/hermes/outputs/smi-item-categories/release/` (private; not part of this public repository).

## Tests and local preview

- `python -m pytest tests -q` runs unit/contract tests, including actual Node category model tests.
- `node --test tests/category-model.test.cjs` runs the category model directly.
- `python tests/verify_category_browser.py --payload <private-preview-sales.json> --output <private-evidence-directory> --branch-regression` runs an ephemeral loopback server, Edge browser, independent Python Decimal reconciliation, both drawers and overview entry points, every period type, repeated entity selection, legacy fallback, HTML escaping, desktop/mobile screenshots and the existing branch/browser regression. It stops its server afterward.
- `tools/run_storage_tests.py` runs the full isolated real-PostgreSQL suite; supply the existing portable binary/dependency paths, a fresh scratch cluster directory and the augmented private preview payload. No production connection is used.
- Private evidence and runnable static preview: `C:/Users/jonj/AppData/Local/hermes/outputs/smi-item-categories/` (never commit business payloads/screenshots).

## TDD / verification evidence

Observed RED→GREEN: missing source-category transport, missing extraction integration/shared model/drawer hooks, then browser-discovered mobile dollar-column clipping. The mobile regression failed before the scoped table-width correction; chart currency ticks were compacted to avoid overlap. Saved RED/GREEN output and browser JSON accompany the private screenshots.

The final chart uses the existing blue/white panels, Chart.js horizontal bars, exact-dollar table/tooltip, and responsive drawer layout. Small categories remain proportionally small rather than visually inflated.
