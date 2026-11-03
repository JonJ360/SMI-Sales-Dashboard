# Rental management reporting policy — rental-management-v1

The SMI refresh applies this standing policy to posted invoices and returns, for every salesperson and every date in the source header population. It is not an invoice/person override and does not require Power BI. SQL reads remain read-only.

- Recognized rental item codes: `GROUND HEATER RENTAL`, `207527`.
- Positive recorded normal rental line costs are included when the header/other-line reconciliation proves they are absent. Already included costs are not added again.
- Rental lines explicitly describing repair, damage or breakdown are separated: customer reimbursement and associated recorded repair cost are both excluded from management sales/profit. Company accounting is unchanged.
- Owned-equipment rentals with zero recorded direct cost retain zero: no estimated depreciation, maintenance allowance, replacement cost or target margin is invented.
- Negative rental costs, unknown heater-rental item codes and ambiguous header-cost allocations retain the original figures and surface in the policy exception list. Resolve source/coding issues rather than review every normal invoice or automatically suppress losses.
- Returns reverse the same treatment. Zero-sales cost documents remain included.
- Original GP sales, cost and profit are retained in adjustment bridges, alongside the exact reporting adjustments. Raw item lines remain unchanged.
- Apply the policy before building report totals: overview, salesperson, customer, branch, periods, prior comparisons and related management report exports share the same snapshot. Source-line category analysis and raw margin exception screening retain their explicitly labeled original bases; weekly order reports remain stock-only order bookings, not posted management profit.
- Full comparison history receives policy source lines; the drilldown display window remains independently restricted to 2024 onward.

The rule runs on each existing scheduled refresh. Normal activity requires no manual review. A genuinely new rental code or changed costing pattern requires an intentional rule/source correction, not a monthly person-by-person reconciliation. Material exceptions and repeated smaller issues remain review candidates. Other previously identified GP cost anomalies are not automatically repaired by this policy.
