/* Branch reporting is based on the posted document's GP Location Code, never customer geography. */
const BranchModel = (() => {
  const cents = v => Math.round(Number(v || 0) * 100);
  function decode(detail) {
    if (!detail || !Array.isArray(detail.documents)) return null;
    return detail.documents.map(row => Array.isArray(row) ? Object.fromEntries(detail.document_fields.map((key, i) => [key, row[i]])) : row);
  }
  function bounds(filter, asOf, first) {
    let start = first, end = asOf;
    if (filter.period === 'YTD') start = asOf.slice(0, 4) + '-01-01';
    if (filter.period === '1M') {const d = new Date(asOf + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() - 29); start = d.toISOString().slice(0, 10);}
    if (filter.period === 'MONTH') {
      start = filter.month + '-01';
      const d = new Date(start + 'T12:00:00Z'); d.setUTCMonth(d.getUTCMonth() + 1, 0);
      end = [asOf, d.toISOString().slice(0, 10)].sort()[0];
    }
    return {start, end};
  }
  function scope(rows, filter, asOf, first, branch) {
    const {start, end} = bounds(filter, asOf, first);
    return rows.filter(d => d.date >= start && d.date <= end && (branch === undefined || d.location === branch));
  }
  function totals(rows) {
    const t = {sales:0, cost:0, profit:0, gross_sales:0, returns:0, invoices:0, return_docs:0, loss_invoices:0, zero_cost_invoices:0};
    for (const d of rows) {
      for (const key of ['sales','cost','profit']) t[key] += cents(d[key]);
      if (d.kind === 'Return') {t.return_docs++; t.returns -= cents(d.sales);}
      else {t.invoices++; t.gross_sales += cents(d.sales); if(d.profit < 0) t.loss_invoices++; if(!d.cost) t.zero_cost_invoices++;}
    }
    for (const key of ['sales','cost','profit','gross_sales','returns']) t[key] /= 100;
    t.customers = new Set(rows.map(d => d.customer)).size;
    t.margin_pct = t.sales > 0 ? 100 * t.profit / t.sales : null;
    t.return_rate = t.gross_sales > 0 ? 100 * t.returns / t.gross_sales : null;
    t.avg_invoice = t.invoices ? t.gross_sales / t.invoices : null;
    return t;
  }
  function group(rows, key) {
    const groups = new Map();
    for (const d of rows) {const name = d[key] || 'Unassigned'; if(!groups.has(name)) groups.set(name, []); groups.get(name).push(d);}
    return [...groups].map(([name, docs]) => ({name, ...totals(docs)})).sort((a,b) => b.sales - a.sales || a.name.localeCompare(b.name));
  }
  function trend(rows, filter, asOf, first) {
    const {start,end} = bounds(filter, asOf, first), grouped = new Map(group(rows.map(d => ({...d, month:d.date.slice(0,7)})), 'month').map(d => [d.name,d]));
    const result = [], date = new Date(start.slice(0,7) + '-01T12:00:00Z');
    while(date.toISOString().slice(0,7) <= end.slice(0,7)) {const month = date.toISOString().slice(0,7);result.push({name:month,...totals([]),...grouped.get(month)});date.setUTCMonth(date.getUTCMonth()+1);}
    return result;
  }
  function filter(rows, options) {
    const q = (options.search || '').trim().toLowerCase();
    return rows.filter(d => (!options.kind || options.kind === 'all' || d.kind === options.kind) && (!options.customer || d.customer === options.customer) && (!options.salesperson || d.salesperson === options.salesperson) && (!q || [d.sop,d.customer,d.salesperson].some(v => String(v).toLowerCase().includes(q))) && (!options.signal || options.signal === 'all' || (options.signal === 'loss' && d.kind === 'Invoice' && d.profit < 0) || (options.signal === 'zero' && d.kind === 'Invoice' && !d.cost) || (options.signal === 'screened' && options.exceptionKeys?.has(d.key))));
  }
  return {decode,bounds,scope,totals,group,trend,filter};
})();
if (typeof module !== 'undefined' && module.exports) module.exports = BranchModel;
if (typeof window !== 'undefined') {
  const $ = id => document.getElementById(id);
  const ui = {branch:null,page:0,customer:'',salesperson:'',source:null,rows:null};
  const percent = n => n == null ? '—' : pct(n);
  const amount = n => `<span class="${n<0?'negative':''}">${invoiceMoney(n)}</span>`;
  const headers = labels => `<thead><tr>${labels.map((x,i) => `<th${i?' class="num"':''}>${x}</th>`).join('')}</tr></thead>`;
  const table = (labels,body) => `<div class="table-wrap"><table>${headers(labels)}<tbody>${body}</tbody></table></div>`;
  function documents() {
    if(ui.source !== state.data) {ui.source = state.data;ui.rows = BranchModel.decode(state.data.invoice_drilldown);}
    return ui.rows;
  }
  function selectedRows(branch) {return BranchModel.scope(documents() || [], filterForView('branches'), state.data.as_of, state.data.invoice_drilldown?.start || '2024-01-01', branch);}
  function ensureLayout() {
    if($('branchDetailPanel'))return;
    $('branches').insertAdjacentHTML('beforeend', `<div class="panel" id="branchDetailPanel" hidden><div class="panel-head"><div><span class="panel-title" id="branchDetailTitle"></span><div class="panel-note" id="branchDetailPeriod"></div></div><button type="button" class="drawer-close" id="branchDetailClose" aria-label="Close branch detail">×</button></div><div class="panel-body"><div id="branchDetailKpis" class="drawer-kpis"></div><p id="branchDetailBridge" class="panel-note"></p><div class="panel"><div class="panel-head"><span class="panel-title">Monthly net sales & profit</span><span class="panel-note">Selected period · partial months retained</span></div><div class="panel-body"><div class="chart-wrap"><canvas id="branchTrendChart"></canvas></div></div></div><div class="grid"><div class="panel"><div class="panel-head"><span class="panel-title">Customers in this branch</span></div><div class="panel-body" id="branchCustomers"></div></div><div class="panel"><div class="panel-head"><span class="panel-title">Salespeople in this branch</span></div><div class="panel-body" id="branchSalespeople"></div></div></div><div class="panel"><div class="panel-head"><span class="panel-title">Posted invoices & returns</span><span class="panel-note">Expand a document for every source item</span></div><div class="panel-body"><p id="branchSignals" class="panel-note"></p><div class="report-filter"><label>Documents<select id="branchDocKind"><option value="all">Invoices + returns</option><option value="Invoice">Invoices only</option><option value="Return">Returns only</option></select></label><label>Attention<select id="branchDocSignal"><option value="all">All documents</option><option value="loss">Loss-making invoices (header)</option><option value="zero">Zero-cost invoices (header)</option><option value="screened">Margin Exceptions matches</option></select></label><label>Sort<select id="branchDocSort"><option value="date">Newest first</option><option value="profit">Lowest profit first</option><option value="sales">Largest net sales first</option></select></label><label>Search<input id="branchDocSearch" placeholder="Invoice, customer or salesperson"></label></div><div id="branchDocScope" class="panel-note"></div><button id="branchClearScope" type="button" class="order-expand" hidden>Show all branch customers & salespeople</button><div class="table-wrap"><table>${headers(['Date / document','Customer / salesperson','Net sales','Cost','Profit','Margin / attention'])}<tbody id="branchDocuments"></tbody></table></div><div class="report-filter"><button type="button" id="branchDocPrev" class="order-expand">Previous</button><span id="branchDocPage" class="panel-note"></span><button type="button" id="branchDocNext" class="order-expand">Next</button></div></div></div></div></div>`);
    $('branchesBody').closest('table').querySelector('thead').innerHTML = headers(['Branch · click to explore','Net sales','vs. prior','Profit','Margin','Returns','Invoices','Customers']).replace(/<\/?thead>/g,'');
    const note = document.createElement('p'); note.className='panel-note'; note.textContent='Branch = GP document Location Code (fulfillment location), not customer city or territory. Net sales = posted invoices less returns; click a branch for its activity.';
    $('branches').querySelector('.report-filter').after(note);
    $('branchesBody').addEventListener('click', e => {const b=e.target.closest('[data-branch]');if(b)openBranch(b.dataset.branch);});
    $('branchDetailClose').onclick=()=>{ui.branch=null;$('branchDetailPanel').hidden=true;};
    for(const id of ['branchDocKind','branchDocSignal','branchDocSort','branchDocSearch'])$(id).addEventListener(id==='branchDocSearch'?'input':'change',()=>{ui.page=0;renderDocuments();});
    $('branchDocPrev').onclick=()=>{ui.page--;renderDocuments();};$('branchDocNext').onclick=()=>{ui.page++;renderDocuments();};
    $('branchClearScope').onclick=()=>{ui.customer='';ui.salesperson='';ui.page=0;renderDocuments();};
    for(const [id,key] of [['branchCustomers','customer'],['branchSalespeople','salesperson']])$(id).onclick=e=>{const b=e.target.closest('[data-member]');if(b){ui.customer='';ui.salesperson='';ui[key]=b.dataset.member;ui.page=0;$('branchDocKind').value='all';$('branchDocSignal').value='all';$('branchDocSearch').value='';renderDocuments();$('branchDocuments').scrollIntoView({block:'nearest',behavior:'smooth'});}};
    $('branchDocuments').onclick=e=>{const b=e.target.closest('[data-branch-document]');if(!b)return;const i=Number(b.dataset.branchDocument),row=$('branch-lines-'+i);if(row.hidden)row.firstElementChild.innerHTML=renderInvoiceLines(ui.visible[i]);row.hidden=!row.hidden;b.setAttribute('aria-expanded',String(!row.hidden));b.textContent=`${row.hidden?'+':'−'} ${ui.visible[i].sop}`;};
  }
  window.renderBranchOverview = function() {
    ensureLayout();
    const s=selection('branches'),current=s.rankings.branches,prior=s.priorRankings?.branches||[],names=[...new Set([...current,...prior].map(d=>d.name))];
    $('branchesBody').innerHTML=names.map(name=>{const c=current.find(d=>d.name===name)||{sales:0,profit:0,returns:0,invoices:0,customers:0},p=prior.find(d=>d.name===name);return `<tr><td><button type="button" class="order-expand" data-branch="${esc(name)}">${esc(name)}</button></td><td class="num">${amount(c.sales)}</td><td class="num">${p?customerDollarChange(c.sales,p.sales):'No prior activity'}</td><td class="num">${amount(c.profit)}</td><td class="num">${percent(c.sales>0?100*c.profit/c.sales:null)}</td><td class="num">${amount(c.returns)}</td><td class="num">${number(c.invoices)}</td><td class="num">${number(c.customers)}</td></tr>`;}).join('');
    if(ui.branch) {ui.page=0;renderDetail();}
  };
  function openBranch(name) {
    ui.branch=name;ui.page=0;ui.customer='';ui.salesperson='';$('branchDocSearch').value='';$('branchDocKind').value='all';$('branchDocSignal').value='all';$('branchDocSort').value='date';
    renderDetail();$('branchDetailPanel').scrollIntoView({behavior:'smooth',block:'start'});
  }
  function renderDetail() {
    const rows=selectedRows(ui.branch),t=BranchModel.totals(rows),s=selection('branches'),report=s.rankings.branches.find(d=>d.name===ui.branch),prior=s.priorRankings?.branches?.find(d=>d.name===ui.branch),available=documents()!==null;
    $('branchDetailPanel').hidden=false;$('branchDetailTitle').textContent=ui.branch+' · Branch detail';
    $('branchDetailPeriod').textContent=periodName('branches')+' · document date · net of returns';
    const match=available&&['sales','cost','profit','invoices','return_docs'].every(k=>Math.abs(t[k]-(report?.[k]||0))<.011);
    const card=(label,value,note='')=>`<div class="card kpi"><div class="k-label">${label}</div><div class="k-value">${value}</div><div class="panel-note">${note}</div></div>`;
    $('branchDetailKpis').innerHTML=available?[
      card('Net sales',money(t.sales),prior?compareText(t.sales,prior.sales,false,'branches'):'No prior activity'),card('Profit',money(t.profit),`Cost ${money(t.cost)} · margin ${percent(t.margin_pct)}`),
      card('Returns',money(t.returns),`${number(t.return_docs)} documents · ${percent(t.return_rate)} of gross sales`),card('Posted invoices',number(t.invoices),`Average ${t.avg_invoice==null?'—':money(t.avg_invoice)} · before returns`),
      card('Active customers',number(t.customers),`${BranchModel.group(rows,'salesperson').length} salespeople`),
      card('Open orders now',money(state.data.open_orders.branches.find(d=>d.name===ui.branch)?.amount||0),`${number(state.data.open_orders.branches.find(d=>d.name===ui.branch)?.orders||0)} orders · not period sales`)
    ].join(''):'';
    $('branchDetailBridge').textContent=!available?'Posted document detail unavailable in this snapshot. Branch overview totals remain available. Refresh after the next data update.':`${match?'Document totals match this branch report.':'Document totals differ from the branch report; overview remains unchanged.'} Gross invoices ${invoiceMoney(t.gross_sales)} less returns ${invoiceMoney(t.returns)} = net ${invoiceMoney(t.sales)}. Profit uses signed absolute GP header cost; zero / missing cost stays zero. Item detail discloses header less line differences.`;
    for(const panel of $('branchDetailPanel').querySelectorAll('.panel-body > .panel, .panel-body > .grid')) panel.hidden=!available;
    if(!available)return;
    const trend=BranchModel.trend(rows,filterForView('branches'),state.data.as_of,state.data.invoice_drilldown?.start||'2024-01-01');
    chart('branchTrendChart',{type:'bar',data:{labels:trend.map(d=>d.name),datasets:[{label:'Net sales',data:trend.map(d=>d.sales),backgroundColor:'#2E6FD9'},{label:'Profit',data:trend.map(d=>d.profit),backgroundColor:'#233B61'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{ticks:{callback:v=>money(v)}}}}});
    for(const [id,key] of [['branchCustomers','customer'],['branchSalespeople','salesperson']]) {
      const groups=BranchModel.group(rows,key);
      $(id).innerHTML=`<p class="panel-note">${groups.length} total · top 15 by net sales · click to filter documents</p>`+table([key==='customer'?'Customer':'Salesperson','Net sales','Profit','Returns'],groups.slice(0,15).map(d=>`<tr><td><button type="button" class="order-expand" data-member="${esc(d.name)}">${esc(d.name)}</button></td><td class="num">${amount(d.sales)}</td><td class="num">${amount(d.profit)}</td><td class="num">${amount(d.returns)}</td></tr>`).join('')||'<tr><td colspan="4">No posted activity in this period.</td></tr>');
    }
    ui.branchRows=rows;ui.exceptions=new Map((state.data.margin_exceptions?.invoices||[]).filter(d=>d.location===ui.branch).map(d=>['Invoice:'+d.sop,d]));
    const matches=rows.filter(d=>ui.exceptions.has(d.key)).length;
    $('branchSignals').textContent=`${number(t.loss_invoices)} loss-making invoices · ${number(t.zero_cost_invoices)} zero-cost invoices (header checks, not exclusions). ${number(matches)} matched Margin Exceptions. Screening covers only the latest ${state.data.margin_exceptions?.window_days||'available'} days by posted date, with existing line exclusions; older documents are not screened here. All sales and costs remain unchanged.`;
    renderDocuments();
  }
  function renderDocuments() {
    const rows=BranchModel.filter(ui.branchRows||[],{kind:$('branchDocKind').value,search:$('branchDocSearch').value,signal:$('branchDocSignal').value,customer:ui.customer,salesperson:ui.salesperson,exceptionKeys:new Set(ui.exceptions?.keys())});
    const sort=$('branchDocSort').value;rows.sort((a,b)=>(sort==='profit'?a.profit-b.profit:sort==='sales'?b.sales-a.sales:0)||b.date.localeCompare(a.date)||a.key.localeCompare(b.key));
    const pages=Math.max(1,Math.ceil(rows.length/50));ui.page=Math.max(0,Math.min(ui.page,pages-1));ui.visible=rows.slice(ui.page*50,(ui.page+1)*50);
    $('branchDocScope').textContent=[ui.customer&&'Customer: '+ui.customer,ui.salesperson&&'Salesperson: '+ui.salesperson].filter(Boolean).join(' · ')||'All branch customers & salespeople';$('branchClearScope').hidden=!ui.customer&&!ui.salesperson;
    $('branchDocuments').innerHTML=ui.visible.map((d,i)=>{const ex=ui.exceptions.get(d.key),flags=[d.kind==='Invoice'&&d.profit<0?'Header loss':'',d.kind==='Invoice'&&!d.cost?'Zero header cost':'',...(ex?.reason_codes||[]).map(reasonLabel)].filter(Boolean);return `<tr><td>${esc(d.date)}<br><button type="button" class="order-expand" data-branch-document="${i}" aria-expanded="false" aria-controls="branch-lines-${i}">+ ${esc(d.sop)}</button><div class="panel-note">${esc(d.kind)}</div></td><td>${esc(d.customer)}<div class="panel-note">${esc(d.salesperson)}</div></td>${['sales','cost','profit'].map(k=>`<td class="num">${amount(d[k])}</td>`).join('')}<td class="num">${percent(d.margin_pct)}${flags.map(f=>`<div class="margin-reason">${esc(f)}</div>`).join('')}</td></tr><tr id="branch-lines-${i}" hidden><td colspan="6"></td></tr>`;}).join('')||'<tr><td colspan="6">No matching posted documents.</td></tr>';
    $('branchDocPage').textContent=`${number(rows.length)} documents · page ${ui.page+1} of ${pages} · 50 per page`;$('branchDocPrev').disabled=ui.page===0;$('branchDocNext').disabled=ui.page>=pages-1;
  }
}
