/* Selected-salesperson comparison. Read-only snapshot model; no new source/auth calls. */
const SalespersonComparison = (() => {
  const B=typeof module!=='undefined'&&module.exports?require('./branch-drilldown.js'):BranchModel;
  const C=typeof module!=='undefined'&&module.exports?require('./item-categories.js'):ItemCategoryModel;
  const cents=v=>Math.round(Number(v||0)*100);
  function priorDate(value){const [y,m,d]=value.split('-').map(Number),last=new Date(Date.UTC(y-1,m,0)).getUTCDate();return `${y-1}-${String(m).padStart(2,'0')}-${String(Math.min(d,last)).padStart(2,'0')}`;}
  function dates(data,filter){const b=B.bounds(filter,data.as_of,data.invoice_drilldown?.start||'2024-01-01');return{current_start:b.start,current_end:b.end,prior_start:priorDate(b.start),prior_end:priorDate(b.end)};}
  function change(current,prior){if(current==null||prior==null)return{delta:null,pct:null,label:'Unavailable'};const delta=(cents(current)-cents(prior))/100;return{delta,pct:prior===0?null:100*delta/Math.abs(prior),label:prior===0?(current>0?'New':'N/A'):null};}
  function build(data,name,filter){
    const d=dates(data,filter),detail=data.invoice_drilldown,docs=B.decode(detail),first=detail?.start||'2024-01-01',last=detail?.end||data.as_of,master=data.item_categories;
    const categoryReady=!!detail?.lines&&master?.source==='SMI.dbo.IV00101'&&!!master.items;
    function summarize(start,end){
      if(!docs||start<first||end>last||start>end)return null;
      let gross=0,returns=0,invoices=0,return_docs=0,line_sales=0,missing=0;const groups=new Map();
      for(const doc of docs){if(doc.salesperson!==name||doc.date<start||doc.date>end)continue;
        if(doc.kind==='Return'){returns-=cents(doc.sales);return_docs++;continue;}
        if(doc.kind!=='Invoice')continue;
        gross+=cents(doc.sales);invoices++;
        if(!categoryReady)continue;
        const lines=detail.lines[doc.key];if(!lines?.length){missing++;continue;}
        for(const raw of lines){const line=Array.isArray(raw)?Object.fromEntries(detail.line_fields.map((k,i)=>[k,raw[i]])):raw,item=String(line.item||''),cat=C.category(Object.hasOwn(master.items,item)?master.items[item]:null),amount=cents(line.sales);groups.set(cat,(groups.get(cat)||0)+amount);line_sales+=amount;}
      }
      return{gross:gross/100,returns:returns/100,net:(gross-returns)/100,invoices,return_docs,line_sales:categoryReady?line_sales/100:null,residual:categoryReady?(gross-line_sales)/100:null,missing:categoryReady?missing:null,categories:Object.fromEntries([...groups].map(([k,v])=>[k,v/100]))};
    }
    const current=summarize(d.current_start,d.current_end),prior=summarize(d.prior_start,d.prior_end);
    const names=new Set([...Object.keys(current?.categories||{}),...Object.keys(prior?.categories||{})]);
    const rows=[...names].map(name=>{const a=current&&categoryReady?(Object.hasOwn(current.categories,name)?current.categories[name]:0):null,b=prior&&categoryReady?(Object.hasOwn(prior.categories,name)?prior.categories[name]:0):null;return{name,current:a,prior:b,...change(a,b)};}).sort((a,b)=>(b.current||0)-(a.current||0)||(b.prior||0)-(a.prior||0)||a.name.localeCompare(b.name));
    return{name,dates:d,current,prior,rows,coverage_start:first,coverage_end:last,categoryReady,returns_included:!!data.returns_included};
  }
  return{dates,change,build};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=SalespersonComparison;
if(typeof window!=='undefined'){
  const money=value=>value==null?'Unavailable':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2}).format(value);
  const pct=row=>row.label||(row.pct>=0?'+':'')+row.pct.toFixed(1)+'%';
  const delta=row=>row.delta==null?'Unavailable':(row.delta>0?'+':'')+money(row.delta);
  const css=`.person-comparison{color:#233B61}.person-comparison h3{font-size:17px;margin:20px 0 8px}.person-comparison .pc-sub{color:#5a6575;font-size:12px;line-height:1.6;margin:8px 0}.person-comparison table{width:100%;min-width:610px;border-collapse:collapse;font-size:12px}.person-comparison th{text-align:right;background:#edf2fa;font-size:10px;letter-spacing:.03em}.person-comparison th:first-child,.person-comparison td:first-child{text-align:left}.person-comparison td{text-align:right;padding:10px 7px;font-variant-numeric:tabular-nums}.person-comparison .pc-category{width:28%}.person-comparison .pc-bar{display:block;height:5px;max-width:100%;background:#2e6fd9;border-radius:2px;margin-top:4px;min-width:0}.person-comparison .pc-prior{background:#9baabe}.person-comparison .pc-negative{background:repeating-linear-gradient(45deg,#bd554e,#bd554e 3px,#efd5d3 3px,#efd5d3 5px)}.person-comparison .pc-key{display:inline-block;width:12px;height:7px;margin:0 4px 0 12px;background:#2e6fd9}.person-comparison .pc-key.prior{background:#9baabe}.person-comparison .pc-total{font-weight:700;background:#edf2fa}.person-comparison .pc-notes{font-size:10px;line-height:1.6;color:#596777;border-top:1px solid #d9e1ec;margin-top:16px;padding-top:10px}.person-comparison .pc-table-wrap{overflow-x:auto}.person-comparison .pc-warn{color:#8a4932;font-size:12px}#salespersonDrawer .drawer-head{flex-wrap:wrap}#salespersonDrawer .drawer-head [data-report-export]{max-width:180px;white-space:normal}#salespersonDrawer .drawer-head .drawer-close{flex-shrink:0}@media screen and (max-width:600px){.person-comparison table,.person-comparison tbody{display:block;min-width:0;width:100%}.person-comparison thead{display:none}.person-comparison tr{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid #d9e1ec;padding:8px 0}.person-comparison td{display:block;text-align:left;border:0;white-space:normal;padding:6px!important}.person-comparison .pc-category{grid-column:1/-1;width:100%;font-weight:700}.person-comparison td[data-label]::before{content:attr(data-label);display:block;color:#667389;font-size:10px;margin-bottom:3px}.person-comparison .pc-table-wrap{overflow:visible}}@media print{.person-comparison table{min-width:0!important;table-layout:auto;font-size:10px}.person-comparison .pc-table-wrap{overflow:visible}.person-comparison tr{break-inside:avoid}.person-comparison h3{break-after:avoid}.person-comparison .pc-bar{height:4px}.person-comparison td{padding:7px!important}.person-comparison .pc-notes{break-inside:avoid}}`;
  const style=document.createElement('style');style.textContent=css;document.head.append(style);
  function heading(){return '<thead><tr><th>Measure / category</th><th>Current</th><th>Prior year</th><th>Change $</th><th>Change %</th></tr></thead>';}
  function row(label,a,b,extra='',cls=''){const c=SalespersonComparison.change(a,b);return `<tr class="${cls}"><td class="pc-category">${esc(label)}${extra}</td><td data-label="Current">${money(a)}</td><td data-label="Prior year">${money(b)}</td><td data-label="Change $">${delta(c)}</td><td data-label="Change %">${pct(c)}</td></tr>`;}
  window.salespersonComparisonHTML=function(r){
    const d=r.dates,max=Math.max(1,...r.rows.flatMap(x=>[Math.abs(x.current||0),Math.abs(x.prior||0)]));
    const bars=x=>[x.current,x.prior].map((v,i)=>v==null?'':`<span aria-hidden="true" class="pc-bar ${i?'pc-prior':''} ${v<0?'pc-negative':''}" style="width:${100*Math.abs(v)/max}%"></span>`).join('');
    return `<p class="pc-sub"><b>Current:</b> ${esc(d.current_start)} – ${esc(d.current_end)}<br><b>Prior year:</b> ${esc(d.prior_start)} – ${esc(d.prior_end)} · same elapsed period, document date</p>${!r.current||!r.prior?`<p class="pc-warn">Comparison unavailable where dates fall outside snapshot detail (${esc(r.coverage_start)} – ${esc(r.coverage_end)}). Unavailable is not zero. Full-history comparisons require an earlier year of detail.</p>`:''}${!r.returns_included?'<p class="pc-warn">Returns are unavailable in this snapshot; net sales are incomplete.</p>':''}
      <h3>Sales summary <small>· net of returns</small></h3><div class="pc-table-wrap"><table>${heading()}<tbody>${row('Net sales',r.current?.net??null,r.prior?.net??null,'','pc-total')}${row('Gross invoices',r.current?.gross??null,r.prior?.gross??null)}${row('Returns deducted',r.current?.returns??null,r.prior?.returns??null)}</tbody></table></div>
      <h3>Category comparison <small>· before returns</small></h3><p class="pc-sub">All categories · paired bars share one dollar scale.<span class="pc-key"></span>Current<span class="pc-key prior"></span>Prior year<br>Negative values use striped bars showing magnitude; signs remain in the dollar columns.</p>
      <div class="pc-table-wrap"><table>${heading()}<tbody>${r.rows.map(x=>row(x.name,x.current,x.prior,bars(x))).join('')}${row('All category lines',r.current?.line_sales??null,r.prior?.line_sales??null,'','pc-total')}</tbody></table></div>${!r.categoryReady?'<p class="pc-warn">Category detail unavailable in this snapshot.</p>':''}
      <div class="pc-notes"><b>Reading this report.</b> Gross category sales include all signed invoice source lines/components; returns are excluded. Current GP item classifications are applied to both years, not historical classifications. REBAR includes STEEL / category 50; unmatched items remain Unclassified. Prior-only categories are retained. Percentage change uses the absolute prior base; zero prior is New for positive current sales, otherwise N/A.<br><b>Reconciliation — current / prior:</b> invoice header less category lines ${money(r.current?.residual??null)} / ${money(r.prior?.residual??null)} (not allocated); invoices missing lines ${r.current?.missing??'Unavailable'} / ${r.prior?.missing??'Unavailable'}. Invoice count ${r.current?.invoices??'Unavailable'} / ${r.prior?.invoices??'Unavailable'}; return count ${r.current?.return_docs??'Unavailable'} / ${r.prior?.return_docs??'Unavailable'}. No open orders, customer lists or other salespeople are included in the individual export.</div>`;
  };
  window.renderSalespersonComparison=function(name,view){
    const r=SalespersonComparison.build(state.data,name,filterForView(view)),drawer=document.querySelector('#salespersonDrawer .drawer');
    let panel=document.getElementById('salespersonComparison');if(!panel){panel=document.createElement('section');panel.id='salespersonComparison';panel.className='panel person-comparison';drawer.querySelector('.drawer-kpis').after(panel);}
    panel.innerHTML='<div class="panel-head"><span class="panel-title">Selected-period performance</span></div><div class="panel-body">'+salespersonComparisonHTML(r)+'</div>';
    drawer.dataset.person=name;drawer.dataset.personView=view;
    // Existing monthly YTD pies deliberately keep their historical/full-month scope.
    drawer.querySelectorAll('.drawer-pies .panel-note').forEach(n=>n.textContent='YTD by calendar month · full prior months, not same-day comparison');
    window.salespersonReportCapture={model:r,sha:String(state.data.sha256||''),asOf:state.data.as_of,heartbeat:state.data.refreshed_at};
    const c=SalespersonComparison.change(r.current?.net??null,r.prior?.net??null);
    document.getElementById('drawerPeriod').textContent=periodName(view)+' · net sales '+delta(c)+' / '+pct(c)+' vs same elapsed prior-year period';
  };
}
