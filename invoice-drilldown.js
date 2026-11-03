/* Posted document detail: separate from Weekly Report's orders-written math. */
const invoiceMoney = value => Number(value || 0).toLocaleString('en-US', {style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2});
function decodeInvoiceRows(fields, rows){return (rows||[]).map(row=>Array.isArray(row)?Object.fromEntries(fields.map((field,i)=>[field,row[i]])):row)}
function invoiceScope(name,view){
  const detail=state.data.invoice_drilldown;if(!detail)return null;
  const f=filterForView(view),end=state.data.as_of;
  let start=detail.start;
  if(f.period==='YTD')start=end.slice(0,4)+'-01-01';
  if(f.period==='1M'){const date=new Date(end+'T12:00:00Z');date.setUTCDate(date.getUTCDate()-29);start=date.toISOString().slice(0,10)}
  return decodeInvoiceRows(detail.document_fields,detail.documents).filter(d=>d.salesperson===name&&d.date<=end&&(f.period==='MONTH'?d.date.slice(0,7)===f.month:d.date>=start));
}
function renderSalespersonInvoices(name,view,current){
  state.invoiceRows=invoiceScope(name,view);state.invoicePage=0;
  invoiceKind.value='Invoice';invoiceSearch.value='';invoiceSort.value='profit';
  if(state.invoiceRows===null){invoiceBridge.textContent='Invoice detail unavailable in this snapshot. Refresh after the next data update.';renderInvoicePage();return}
  const sum=(rows,key)=>rows.reduce((v,d)=>v+Number(d[key]||0),0),rows=state.invoiceRows;
  const inv=rows.filter(d=>d.kind==='Invoice'),ret=rows.filter(d=>d.kind==='Return');
  const reconciled=['sales','cost','profit'].every(k=>Math.abs(sum(rows,k)-current[k])<.011)&&inv.length===current.invoices&&ret.length===current.return_docs;
  invoiceBridge.innerHTML=`<div class="table-wrap"><table><thead><tr><th>Population</th><th class="num">Sales</th><th class="num">Cost</th><th class="num">Profit</th></tr></thead><tbody>${[['Posted invoices',inv],['Posted returns (signed)',ret],['Net report',rows]].map(([label,items])=>`<tr><td>${label} · ${number(items.length)}</td>${['sales','cost','profit'].map(k=>`<td class="num ${sum(items,k)<0?'negative':''}">${invoiceMoney(sum(items,k))}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="panel-note">${reconciled?'Document totals reconcile to the selected salesperson report.':'Document / report totals differ. Report totals are unchanged; refresh or review the source.'}</p>`;
  renderInvoicePage();
}
function renderInvoicePage(){
  const q=invoiceSearch.value.trim().toLowerCase(),rows=(state.invoiceRows||[]).filter(d=>d.kind===invoiceKind.value&&(!q||[d.sop,d.customer,d.location].some(v=>String(v).toLowerCase().includes(q))));
  rows.sort(invoiceSort.value==='date'?(a,b)=>b.date.localeCompare(a.date)||a.sop.localeCompare(b.sop):(a,b)=>a.profit-b.profit||b.date.localeCompare(a.date)||a.sop.localeCompare(b.sop));
  const pages=Math.max(1,Math.ceil(rows.length/50));state.invoicePage=Math.min(state.invoicePage,pages-1);
  state.invoiceVisible=rows.slice(state.invoicePage*50,(state.invoicePage+1)*50);
  invoiceDocuments.innerHTML=state.invoiceVisible.map((d,i)=>`<tr><td>${esc(d.date)}</td><td><button type="button" class="order-expand" data-invoice-index="${i}" aria-expanded="false" aria-controls="invoice-lines-${i}">+ ${esc(d.sop)}</button></td><td>${esc(d.customer)}<div class="panel-note">${esc(d.location)} · ${esc(d.kind)}</div></td>${['sales','cost','profit'].map(k=>`<td class="num ${d[k]<0?'negative':''}">${invoiceMoney(d[k])}</td>`).join('')}<td class="num ${d.margin_pct<0?'negative':''}">${d.margin_pct==null?'—':pct(d.margin_pct)}</td></tr><tr id="invoice-lines-${i}" hidden><td colspan="7"></td></tr>`).join('')||'<tr><td colspan="7">No matching posted documents.</td></tr>';
  invoicePage.textContent=`${number(rows.length)} documents · page ${state.invoicePage+1} of ${pages} · 50 per page`;
  invoicePrev.disabled=state.invoicePage===0;invoiceNext.disabled=state.invoicePage>=pages-1;
}
function renderInvoiceLines(doc){
  const detail=state.data.invoice_drilldown,lines=decodeInvoiceRows(detail.line_fields,detail.lines[doc.key]);
  if(!lines.length)return '<div class="empty">No source lines returned for this posted document. Header totals remain unchanged; this is not evidence of zero cost.</div>';
  const misc=(state.data.misc_item_policy?.documents||[]).find(d=>d.kind===doc.kind&&d.sop===doc.sop);
  const miscNote=misc?`<p class="panel-note"><b>7518 management estimate, not supplier actual:</b> GP cost ${invoiceMoney(misc.gp_cost)} · GP profit ${invoiceMoney(misc.gp_profit)} · 50% extended-sales estimate ${invoiceMoney(misc.estimate)} · Source cost already incorporated ${invoiceMoney(misc.source_cost_in_header)} · Net management cost change ${invoiceMoney(misc.cost_added)} · Final cost ${invoiceMoney(misc.cost)} · Final profit ${invoiceMoney(misc.profit)}. Source lines and GP remain unchanged.</p>`:'';
  const adjustment=(state.data.rental_policy?.documents||[]).find(d=>d.kind===doc.kind&&d.sop===doc.sop);
  const policyNote=adjustment?`<p class="panel-note"><b>Management rental policy:</b> GP sales ${invoiceMoney(adjustment.gp_sales)} · GP cost ${invoiceMoney(adjustment.gp_cost)} · GP profit ${invoiceMoney(adjustment.gp_profit)}. Normal rental cost added ${invoiceMoney(adjustment.rental_cost_added)}. Repair recovery excluded ${invoiceMoney(adjustment.repair_recovery_excluded)}; repair line cost excluded ${invoiceMoney(adjustment.repair_cost_excluded)}. Source lines below remain unmodified; company GL is unchanged.</p>`:'';
  const gl=(state.data.verified_gl_corrections?.documents||[]).find(d=>d.kind===doc.kind&&d.sop===doc.sop);
  const glNote=gl?`<p class="panel-note"><b>Verified posted GL correction:</b> journal ${esc(gl.journal)}, GL date ${esc(gl.gl_date)}. Original GP sales ${invoiceMoney(gl.gp_sales)}, cost ${invoiceMoney(gl.gp_cost)}, profit ${invoiceMoney(gl.gp_profit)}. Posted cost reduction ${invoiceMoney(gl.cost_reduction)} is included once in the management figures above. ${gl.excluded_duplicate_journal?` Journal ${esc(gl.excluded_duplicate_journal)} is excluded from this management correction; its possible duplication remains a separate accounting review.`:''} No new accounting entry.</p>`:'';
  const direct=(state.data.approved_direct_costs?.documents||[]).find(d=>d.kind===doc.kind&&d.sop===doc.sop);
  const directNote=direct?`<p class="panel-note"><b>Approved direct supplier cost:</b> ${invoiceMoney(direct.cost_added)} added once to management cost. Original GP cost ${invoiceMoney(direct.gp_cost)}; management cost ${invoiceMoney(direct.cost)}. PO ${esc(direct.po)}, supplier invoice ${esc(direct.supplier_invoice)}, journal ${esc(direct.journal)} (GL ${esc(direct.gl_date)}; sale-date attribution ${esc(direct.management_date)}). Approved matching purchase package, not an explicit GP sales-to-PO link. Company expense already posted; no new GP entry.</p>`:'';
  return `${miscNote}${policyNote}${glNote}${directNote}<div class="order-line-detail"><p><b>${esc(doc.kind)} ${esc(doc.sop)} · ${number(lines.length)} item lines</b></p><p class="panel-note">Header less lines: sales ${invoiceMoney(doc.sales_difference)} · cost ${invoiceMoney(doc.cost_difference)} · profit ${invoiceMoney(doc.profit_difference)}. Source-line differences remain visible; approved rental adjustments are explained separately above. Original GP header source cost ${invoiceMoney(doc.raw_cost)}. Every source line is shown, including components and nonstock lines. Cost uses absolute GP cost, signed negative for returns. Source cost retains its original sign. Zero / missing costs remain zero; no margin override. Quantities use each line's UOM.</p><div class="table-wrap"><table class="order-lines"><thead><tr><th>Item / description</th><th>Qty / UOM</th><th class="num">Sales</th><th class="num">Source cost</th><th class="num">Cost</th><th class="num">Profit</th><th class="num">Margin</th></tr></thead><tbody>${lines.map(line=>`<tr><td><b>${esc(line.item||'No item ID')}</b><div>${esc(line.description)}</div><small>Line ${esc(line.line_sequence)} / component ${esc(line.component_sequence)}</small></td><td>${Number(line.quantity).toLocaleString('en-US',{maximumFractionDigits:5})} ${esc(line.uom)}</td>${['sales','raw_cost','cost','profit'].map(k=>`<td class="num ${line[k]<0?'negative':''}">${invoiceMoney(line[k])}</td>`).join('')}<td class="num ${line.margin_pct<0?'negative':''}">${line.margin_pct==null?'—':pct(line.margin_pct)}</td></tr>`).join('')}</tbody></table></div></div>`;
}
function toggleInvoice(button){const i=Number(button.dataset.invoiceIndex),doc=state.invoiceVisible[i],row=document.getElementById(`invoice-lines-${i}`);if(!doc||!row)return;const opening=row.hidden;if(opening&&!row.dataset.rendered){row.firstElementChild.innerHTML=renderInvoiceLines(doc);row.dataset.rendered='true'}row.hidden=!opening;button.setAttribute('aria-expanded',String(opening));button.textContent=`${opening?'−':'+'} ${doc.sop}`}
document.getElementById('invoiceDocuments').onclick=e=>{const b=e.target.closest('[data-invoice-index]');if(b)toggleInvoice(b)};
for(const id of ['invoiceKind','invoiceSort','invoiceSearch'])document.getElementById(id).addEventListener(id==='invoiceSearch'?'input':'change',()=>{state.invoicePage=0;renderInvoicePage()});
document.getElementById('invoicePrev').onclick=()=>{state.invoicePage=Math.max(0,state.invoicePage-1);renderInvoicePage()};
document.getElementById('invoiceNext').onclick=()=>{state.invoicePage++;renderInvoicePage()};
