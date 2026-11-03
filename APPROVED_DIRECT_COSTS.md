# Approved direct supplier cost policy

`approved-direct-v1` is a reviewed document-specific management allocation, not a blanket miscellaneous-item costing rule.

Approved mapping: invoice `00777490`, item `41381`, line `360448`, direct expedite cost `$16,000`. Supplier Neuweg Industries, vendor `2264`, PO `94079`, supplier invoice `F114466`, receipt `RCT0137027`, billed receipt `RCT0137307`, posted journal `1426964`.

The sales/purchase package corroborates this attribution; GP has no retained explicit SOP–POP link. Jon approved this specific allocation. Other delivery, sign and pallet line costs remain unapproved and unchanged.

Every refresh validates the exact PO fee, supplier receipt and billed receipt (including vendor, amount and nonvoid status), the complete balanced three-line nonvoid actual-ledger journal and its date/source receipt, and the exact sales invoice/date/item/line/quantity/cost. Open and closed GL history are supported. Changed or missing evidence leaves the source cost unchanged and raises a visible exception.

Original GP header cost `$84,292.50` is retained. Management cost becomes `$100,292.50`, once only. Already-incorporated cost is not increased again. No GP entry is created: company expense was posted March 23; management reporting attributes the direct cost to the April 1 sale. Raw item detail and existing stock-only reports keep their disclosed source basis.

Application occurs before shared invoice-based management aggregates, so company, salesperson, branch, customer, comparisons and their management exports inherit the same approved treatment. Existing rental and verified-GL policies remain separate. No residual is plugged to match Power BI.
