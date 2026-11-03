# Miscellaneous merchandise management reporting policy — V1.31

Jon approved expansion from Sydney's highlighted November 3 `2026113-13549.XLSX`: literal codes **41381,41382,41384,41387,41388,41389,41390,41391,41392,7518**. Workbook SHA256 `3c3405136b11b1b7cd1404fa1270a3fa31dfd64aa2491b3ae278649974177f5b`; original and highlight evidence retained privately in Hermes Documents/Sydney miscellaneous expansion Nov3. Highlighted41393 is labeled DO NOT USE and remains held pending merchandise identity; no2024+activity observed. Never blanket ITEMTYPE4. Keep the existing formula: **50% of each source extended line sales amount**, not half cost or unitprice/quantity reconstruction. Every salesperson/full history is included. Round decimal half-up per line, then sum. Negative lines reduce estimates; returns reverse cost. GP and source lines remain unchanged; no supplier actual or accounting entry is implied.

Apply after existing rental/GL/supplier policies and before shared snapshot/invoice drilldown. Preserve previous management deltas and original GP values. Invoice00777490 remains reserved to the prior actual-supplier policy: never replace/double-count its verified$16,000 allocation. Explicit rental, freight, surcharge, labor, credit-card/card-fix, expediting, shop-drawing and delivery fee/charge descriptions on new codes hold the entire document with a visible nonmerchandise_target_line exception. This conservative guard does not prove all other descriptions merchandise. Existing7518 treatment is preserved. Legacy misc_7518_bridge field remains for compatibility; metadata version is misc-merchandise-management-v2 with exact item_codes and held_codes.

## Evidence and double-count protection

Require complete line-sales reconciliation to the GP header and unique line/component identities. Compare original GP header cost with summed absolute nontarget source costs, all source costs, or nontarget costs plus the estimate. These identify respectively excluded source cost, incorporated source cost, and already incorporated estimate. Replace only the identified target component. Ambiguous or missing evidence exposes an exception and retains existing cost. Missing/null header or line amounts are not zero evidence. Negative invoice header/source costs retain unsupported_negative_invoice_cost exceptions; signed returns remain supported. Self-reapplication is idempotent.

## Disclosure

Global disclosure and exceptions appear below reports; invoice detail shows GP cost/profit, merchandise estimate, incorporated source cost, net change and final management figures. Label explicitly: management estimate, not supplier actual. Weekly stock-only orders, raw margin screening, category/source-line charts and line costs retain separately labeled raw-source bases.

## Local verification

New tests cover multiple lines, all salesperson identities, invoice and return signs, half-cent rounding, zero/negative sales, literal item scope, evidence failure, incorporated cost/estimate, idempotence, earlier corrections retained and historical integration. Existing rental/GL/direct-allocation regression tests remain unchanged. No schema/auth/scheduler changes. No GP queries or data refresh are needed to run unit tests.

Deployment must refresh the snapshot to activate policy metadata; stale snapshots show an explicit unverified warning. Review actual exception counts before production acceptance. Sales/header mismatch is fail-closed even if caused by a legitimate document-level discount: use source extended sales, never reconstruct from quantity or unit price.
