# Miscellaneous merchandise management reporting policy — V1.39

Jon approved expansion from Sydney's highlighted November 3 `2026113-13549.XLSX`: literal codes **41381,41382,41384,41387,41388,41389,41390,41391,41392,7518**. Workbook SHA256 `3c3405136b11b1b7cd1404fa1270a3fa31dfd64aa2491b3ae278649974177f5b`; original and highlight evidence retained privately in Hermes Documents/Sydney miscellaneous expansion Nov3. Highlighted41393 is labeled DO NOT USE and remains held pending merchandise identity; no2024+activity observed. Never blanket ITEMTYPE4. Keep the existing formula: **50% of each source extended line sales amount**, not half cost or unitprice/quantity reconstruction. Every salesperson/full history is included. Round decimal half-up per line, then sum. Negative lines reduce estimates; returns reverse cost. GP and source lines remain unchanged; no supplier actual or accounting entry is implied.

Apply after existing rental/GL/supplier policies and before shared snapshot/invoice drilldown. Preserve previous management deltas and original GP values. Invoice00777490 remains reserved to the prior actual-supplier policy: never replace/double-count its verified$16,000 allocation. Explicit rental, freight, surcharge, labor, credit-card/card-fix, expediting, shop-drawing and delivery fee/charge descriptions on any allowlisted code, including 7518, hold the entire document with a visible nonmerchandise_target_line exception. This conservative guard does not prove all other descriptions merchandise. Genuine 7518 merchandise retains the same estimate; explicitly nonmerchandise 7518 retains source cost. Legacy misc_7518_bridge field remains for compatibility; metadata version is misc-merchandise-management-v3 with exact item_codes and held_codes.

## November 11 exact-code additions and JOSH bundle exemption

Read-only item-master evidence (`MISC current item master candidates.json` and
`Additional MISC master codes impact.json`, monthly cleanup evidence folder)
supports the additional literal merchandise codes **204100 — MISC - STONE, 46300 — MISC - LOGIX, RV41390 —
RV MISC - TOOLS** (each ITEMTYPE 4). These three literal additions use the same
merchandise-description, line reconciliation, source-linked override and header
cost guards. Raw line cost alone does not prove incorporation into header cost.
LABOR-MISC 087515, MISC-class COMMENT/serial/service/prepaid codes and held 41393
are not added. This is not a class/type/description wildcard.

Before applying or returning a cached MISC bridge, exclude the **whole exact-JOSH
document** if any source-line description contains the token sequence `Above All
For`, `Above For All`, or `All the Above For`. Case and separating whitespace or
punctuation are ignored; word boundaries exclude partial-word matches. The marker
may occur on a non-MISC line. JOSHK, normal JOSH miscellaneous, other salespeople,
and unknown wording are not exempted. The exception is
`josh_above_all_bundle_excluded`; there is no guessed supplier actual.

Without a previous bridge, leave approved source/current cost unchanged. On
reapplication of an already estimated bundle, reverse only its recorded MISC
adjustment, remove its bridge, and retain rental/GL/supplier and later unrelated
adjustments. New bridges retain `pre_misc_extended_cost`, including negative
source-cost representation. Legacy bridges use recorded signed cost and delta;
original negative-source representation is unavailable, but normalized cost is
preserved. Invalid cached evidence retains current cost and raises
`josh_above_all_bundle_cached_cost_unverified` for review rather than guessing.
Repeated application is idempotent.

No exact policy-version gate was found in UI validation; the generic MISC bridge
and disclosure contract is unchanged. The Josh guard alone should not change
frozen totals: known bundles 00776896 and 00804357 had no previous MISC estimate.
The separately authorized three-code extension can change other totals and needs
offline source replay before acceptance.

## Evidence and double-count protection

Require complete line-sales reconciliation to the GP header and unique line/component identities. Compare original GP header cost with summed absolute nontarget source costs, all source costs, or nontarget costs plus the estimate. These identify respectively excluded source cost, incorporated source cost, and already incorporated estimate. Replace only the identified target component. Ambiguous or missing evidence exposes an exception and retains existing cost. Missing/null header or line amounts are not zero evidence. Negative invoice header/source costs retain unsupported_negative_invoice_cost exceptions; signed returns remain supported. Self-reapplication is idempotent.

## Disclosure

Global disclosure and exceptions appear below reports; invoice detail shows GP cost/profit, merchandise estimate, incorporated source cost, net change and final management figures. Label explicitly: management estimate, not supplier actual. Weekly stock-only orders, raw margin screening, category/source-line charts and line costs retain separately labeled raw-source bases.

## Local verification

New tests cover multiple lines, all salesperson identities, invoice and return signs, half-cent rounding, zero/negative sales, literal item scope, evidence failure, incorporated cost/estimate, idempotence, earlier corrections retained and historical integration. Existing rental/GL/direct-allocation regression tests remain unchanged. No schema/auth/scheduler changes. No GP queries or data refresh are needed to run unit tests.

Deployment must refresh the snapshot to activate policy metadata; stale snapshots show an explicit unverified warning. Review actual exception counts before production acceptance. Sales/header mismatch is fail-closed even if caused by a legitimate document-level discount: use source extended sales, never reconstruct from quantity or unit price.

## Merchandise-only guard and settlement compatibility

Every allowlisted code, including 7518, obeys the explicit nonmerchandise guard before cached-policy reuse. An excluded cached estimate is removed only when its signed identity and monetary bridge can be verified; prior and later unrelated adjustments and original GP cost remain intact. A present malformed cache is held explicitly.

The settlement-discount ledger revision changes only the expected upstream management cost for the 86 affected approved invoices. All 7,493 application events and their GL/SOP/RM evidence pins, owners, dates and discount amounts are retained. The original ledger remains unchanged. Independent validation must retain $137,754.46 across 7,486 invoices with zero exceptions. No validator is weakened; accounting or management-cost drift still withholds the whole invoice.
