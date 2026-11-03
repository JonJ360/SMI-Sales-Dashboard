# Verified posted cost corrections

`verified-gl-v1` includes only the explicitly reviewed and approved correction journal 1452013 for invoice 00786458 / item UD39514. It is not a general margin override or an automatic importer of arbitrary GL entries.

Each refresh reads the complete journal from open and closed GL history, validates its exact invoice/item note, effective GL date, accounts, balanced debit/credit amount, actual ledger, nonvoid status and absence of backout. The original invoice date and source cost must still match the reviewed evidence. A changed or missing source is left unchanged and flagged visibly for review.

The adjustment is applied once before management aggregates are built, so salesperson, customer, branch, period totals and their management report exports share the same treatment. Raw GP invoice cost and unmodified source item lines remain visible; invoice detail identifies the posted journal and the cost reduction. If GP later incorporates the corrected invoice cost, the reduction is not applied a second time.

This changes reporting only. It creates no GP journal, alters no company GL balance, estimates no unit cost and does not adjust the residual difference against Power BI. Further journal mappings require evidence and approval; this already-approved mapping persists automatically on future refreshes.
