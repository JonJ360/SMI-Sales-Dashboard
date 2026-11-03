# Verified posted cost corrections

`verified-gl-v1` includes only explicitly reviewed and approved corrections: journal 1452013 for invoice 00786458 / item UD39514, and journal 1469379 for invoice 00795214 / item S1100. It is not a general margin override or an automatic importer of arbitrary GL entries.

Dylan's S1100 correction is applied once: original invoice cost $237,663.36 less the supported $235,862.88 correction gives cost $1,800.48 and profit $443.52. Journal 1471752 is deliberately excluded, not added to the correction; its suspected duplication remains Anthony's separate company-accounting investigation. This approved original journal must still contain exactly the balanced inventory debit and COGS credit on their specified accounts, invoice/item/PO note, nonvoid actual-ledger status and original GL date. The original invoice date, header cost and S1100 source line (132 units) must also match. Missing or changed evidence raises a visible exception. Already-corrected source cost is never corrected twice.

Each refresh reads the complete journal from open and closed GL history, validates its exact invoice/item note, effective GL date, accounts, balanced debit/credit amount, actual ledger, nonvoid status and absence of backout. The original invoice date and source cost must still match the reviewed evidence. A changed or missing source is left unchanged and flagged visibly for review.

The adjustment is applied once before management aggregates are built, so salesperson, customer, branch, period totals and their management report exports share the same treatment. Raw GP invoice cost and unmodified source item lines remain visible; invoice detail identifies the posted journal and the cost reduction. If GP later incorporates the corrected invoice cost, the reduction is not applied a second time.

This changes reporting only. It creates no GP journal, alters no company GL balance, estimates no unit cost and does not adjust the residual difference against Power BI. Further journal mappings require evidence and approval; this already-approved mapping persists automatically on future refreshes.
