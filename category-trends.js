/* Annual company-wide invoice-line category trends; no extraction or accounting changes. */
let categoryTrendSnapshot=null,categoryTrendYear=null,categoryTrendResult=null;
function renderCategoryTrends() {
  const data=state.data,yearSelect=document.getElementById('categoryYear'),choice=document.getElementById('categoryChoice');
  const first=Number((data.invoice_drilldown?.start||'2024-01-01').slice(0,4)),last=Number(data.as_of.slice(0,4));
  if(categoryTrendSnapshot!==data) {
    const previous=yearSelect.value;
    yearSelect.innerHTML=Array.from({length:Math.max(0,last-first+1)},(_,i)=>last-i).map(y=>`<option value="${y}">${y}${y===last?' · YTD':''}</option>`).join('');
    if([...yearSelect.options].some(o=>o.value===previous))yearSelect.value=previous;
    categoryTrendSnapshot=data;categoryTrendYear=null;
  }
  const year=Number(yearSelect.value);
  if(categoryTrendYear!==year){categoryTrendResult=ItemCategoryModel.annual(data,year);categoryTrendYear=year;}
  // Missing classification must never leave stale charts visible.
  const result=data.item_categories?categoryTrendResult:null,rows=result?.categories||[];
  const selected=choice.value;
  choice.innerHTML=rows.map(r=>`<option value="${esc(r.name)}">${esc(r.name)}</option>`).join('');
  if(rows.some(r=>r.name===selected))choice.value=selected;
  const row=rows.find(r=>r.name===choice.value),months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  categoryScope.textContent=`${year===last?'Year to date through '+data.as_of:year+' calendar year'} · document date · gross invoice-line sales before returns · independent of other report filters`;
  categoryCoverage.textContent=!result?'Category detail unavailable in this snapshot; existing report totals are unchanged.':
    `Current GP item class, not historical classification. REBAR includes STEEL / category 50; Tools appears only when mapped by the item master. Unmatched or ambiguous items remain Unclassified. All signed invoice source lines and components retained; no cost or margin adjustment. All category line sales ${invoiceMoney(result.line_sales)}; invoice headers ${invoiceMoney(result.header_sales)}; header less lines ${invoiceMoney(result.difference)} (unallocated). ${result.missing_documents} invoices without source lines. Returns excluded from category charts: ${result.returns_included?result.return_documents+' return documents; signed return header sales '+invoiceMoney(result.return_sales):'return coverage unavailable'}. This is not net sales. Partial months are incomplete; future months are blank, not zero.`;
  categoryMonthlyTable.innerHTML=row?`<table><thead><tr><th>Month</th><th class="num">${esc(row.name)} sales</th></tr></thead><tbody>${result.months.map((m,i)=>`<tr><td>${months[i]}${m.status==='Actual'?'':' · '+m.status}</td><td class="num">${row.months[i]===null?'—':invoiceMoney(row.months[i])}</td></tr>`).join('')}</tbody><tfoot><tr><th>${year===last?'YTD':'Year'} total</th><th class="num">${invoiceMoney(row.sales)}</th></tr></tfoot></table>`:'<p class="panel-note">No invoice source lines in this year.</p>';
  categoryComparisonTable.innerHTML=rows.length?`<table><thead><tr><th>Category</th><th class="num">${year===last?'YTD':'Year'} gross sales</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.name)}</td><td class="num">${invoiceMoney(r.sales)}</td></tr>`).join('')}</tbody><tfoot><tr><th>All categories</th><th class="num">${invoiceMoney(result.line_sales)}</th></tr></tfoot></table>`:'';
  for(const id of ['categoryTrendChart','categoryCompareChart']){if(state.charts[id]){state.charts[id].destroy();delete state.charts[id];}document.getElementById(id).parentElement.hidden=!rows.length;}
  if(!rows.length)return;
  const compact=v=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',notation:'compact',maximumFractionDigits:1}).format(v);
  chart('categoryTrendChart',{type:'line',data:{labels:result.months.map((m,i)=>months[i]+(m.status==='Partial'?' *':'')),datasets:[{label:row.name,data:row.months,borderColor:'#2E6FD9',backgroundColor:'#2E6FD9',tension:0.15,spanGaps:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>invoiceMoney(c.parsed.y)}}},scales:{y:{ticks:{callback:compact}},x:{ticks:{autoSkip:false,maxRotation:0,font:{size:10}}}}}});
  const comparison=rows.slice(0,8);
  chart('categoryCompareChart',{type:'bar',data:{labels:comparison.map(r=>r.name),datasets:[{label:'Gross invoice-line sales',data:comparison.map(r=>r.sales),backgroundColor:'#2E6FD9',borderRadius:3}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>invoiceMoney(c.parsed.x)}}},scales:{x:{ticks:{maxTicksLimit:4,callback:compact}},y:{ticks:{autoSkip:false}}}}});
}
document.getElementById('categoryYear').onchange=renderCategoryTrends;
document.getElementById('categoryChoice').onchange=renderCategoryTrends;
