# Item 7518 management reporting policy — V1.30

Jon approved a recurring management cost estimate for literal item `7518`: **50% of each source extended line sales amount**, not half the existing cost. Applies to every salesperson and the full shared historical transaction input (2021 onward, including prior comparisons). Round each line estimate to cents using decimal ROUND_HALF_UP, then sum. Negative invoice lines reduce estimated cost; return documents reverse the cost. No supplier actual or accounting entry is implied.

Apply after the existing rental, approved GL and supplier-allocation policies and before build_snapshot / invoice drilldown. Preserve earlier management adjustments by applying only the 7518 delta against the original GP header bridge. Preserve source line dictionaries and GP sales/cost originals.

## Evidence and double-count protection

Require complete line-sales reconciliation to the GP header and unique line/component identities. Compare original GP header cost with summed absolute non-7518 source costs, all source costs, or non-7518 costs plus the estimate. These identify respectively excluded source cost, incorporated source cost, and an already incorporated estimate. Replace only the identified 7518 component. If no unique bridge exists, preserve the existing document and expose an exception. Missing lines and missing/null current or original header costs produce visible exceptions; they are not zero-cost evidence. Invoice documents with negative original/current header cost or negative source-line costs are conservatively retained with `unsupported_negative_invoice_cost` exceptions rather than accepting an absolute-value bridge. Signed returns remain supported. Applying the policy to its own returned rows is idempotent.

## Disclosure

Global disclosure and exceptions appear below reports; adjusted invoice detail shows GP cost/profit, estimated 7518 cost, incorporated source cost, net change and final management cost/profit. Label explicitly: management estimate, not supplier actual. Existing weekly stock-only orders, raw margin screening, category/source-line charts and line costs remain on their separately labeled raw-source bases. Their figures are not replaced by management estimates.

## Local verification

New tests cover multiple lines, all salesperson identities, invoice and return signs, half-cent rounding, zero/negative sales, literal item scope, evidence failure, incorporated cost/estimate, idempotence, earlier corrections retained and historical integration. Existing rental/GL/direct-allocation regression tests remain unchanged. No schema/auth/scheduler changes. No GP queries or data refresh are needed to run unit tests.

Deployment must refresh the snapshot to activate policy metadata; stale snapshots show an explicit unverified warning. Review actual exception counts before production acceptance. Sales/header mismatch is fail-closed even if caused by a legitimate document-level discount: use source extended sales, never reconstruct from quantity or unit price.
