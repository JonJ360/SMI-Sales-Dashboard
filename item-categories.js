/* Current GP item-master classification; posted amounts/attribution remain unchanged. */
const ItemCategoryModel = (() => {
  const branch = typeof module !== 'undefined' && module.exports ? require('./branch-drilldown.js') : BranchModel;
  const cents = value => Math.round(Number(value || 0) * 100);
  function category(value) {
    const cls=String(value?.[0] || '').trim(), sub=String(value?.[1] || '').trim();
    // Same reviewed SMI Rebar rule used by the existing margin screen. No exclusions here.
    return cls.toUpperCase()==='REBAR'||(cls.toUpperCase()==='STEEL'&&sub==='50')?'REBAR':cls||'Unclassified';
  }
  function summarize(data,entity,name,filter) {
    const detail=data.invoice_drilldown, master=data.item_categories;
    if(!detail?.lines || !master?.items || master.source!=='SMI.dbo.IV00101')return null;
    const docs=branch.decode(detail);
    if(!docs)return null;
    const rows=branch.scope(docs,filter,data.as_of,detail.start||'2024-01-01')
      .filter(d=>d[entity]===name && d.kind==='Invoice');
    const groups=new Map();let header=0,total=0,missing=0,unclassified=0;
    for(const doc of rows) {
      header+=cents(doc.sales);
      const lines=detail.lines[doc.key];
      if(!lines?.length){missing++;continue;}
      for(const raw of lines) {
        const line=Array.isArray(raw)?Object.fromEntries(detail.line_fields.map((key,i)=>[key,raw[i]])):raw;
        const item=String(line.item||''), value=Object.hasOwn(master.items,item)?master.items[item]:null;
        const label=category(value), amount=cents(line.sales);
        groups.set(label,(groups.get(label)||0)+amount);total+=amount;
        if(label==='Unclassified')unclassified+=amount;
      }
    }
    const all=[...groups].map(([name,sales])=>({name,sales:sales/100}))
      .sort((a,b)=>b.sales-a.sales||a.name.localeCompare(b.name));
    const top=all.slice(0,5),topTotal=top.reduce((sum,d)=>sum+cents(d.sales),0);
    return {categories:top,category_count:all.length,line_sales:total/100,header_sales:header/100,
      difference:(header-total)/100,missing_documents:missing,unclassified_sales:unclassified/100,
      other_sales:(total-topTotal)/100};
  }
  return {category,summarize};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=ItemCategoryModel;
if(typeof window!=='undefined') {
  window.renderItemCategories=function(entity,name,view) {
    const id=entity+'Categories',drawer=document.querySelector('#'+entity+'Drawer .drawer');
    let panel=document.getElementById(id);
    if(!panel) {
      panel=document.createElement('section');panel.className='panel';panel.id=id;
      panel.innerHTML=`<div class="panel-head"><span class="panel-title">Top 5 item categories by gross sales</span></div><div class="panel-body"><p class="panel-note" id="${id}Scope"></p><div class="chart-wrap" style="height:260px"><canvas id="${id}Chart" role="img" aria-label="Top five item categories by gross invoice line sales"></canvas></div><div id="${id}Table" class="table-wrap"></div><p class="panel-note" id="${id}Note"></p></div>`;
      drawer.querySelector('.drawer-kpis').after(panel);
    }
    const result=ItemCategoryModel.summarize(state.data,entity,name,filterForView(view)),top=result?.categories||[];
    document.getElementById(id+'Scope').textContent=periodName(view)+' · document date · before returns';
    document.getElementById(id+'Chart').parentElement.hidden=!top.length;
    document.getElementById(id+'Table').innerHTML=top.length?`<table style="min-width:0;width:100%"><thead><tr><th>Category</th><th class="num">Gross sales</th></tr></thead><tbody>${top.map(d=>`<tr><td>${esc(d.name)}</td><td class="num ${d.sales<0?'negative':''}">${invoiceMoney(d.sales)}</td></tr>`).join('')}</tbody></table>`:'';
    document.getElementById(id+'Note').textContent=!result?'Category detail unavailable in this snapshot. Requires GP item-master categories from an updated extract; report totals remain unchanged.':
      `${top.length?'':'No invoice source lines in this selection. '}Current GP item class (not historical classification); REBAR includes STEEL / category 50. No description-based guesses. Returns excluded; all invoice source line types/components and signed adjustments retained. ${result.category_count} categories including Unclassified where needed. All line sales ${invoiceMoney(result.line_sales)}; other categories outside top five ${invoiceMoney(result.other_sales)}. Unclassified ${invoiceMoney(result.unclassified_sales)}. Header less all lines ${invoiceMoney(result.difference)}; not allocated. ${result.missing_documents} invoices without source lines. Header gross sales ${invoiceMoney(result.header_sales)}; net report totals unchanged.`;
    if(state.charts[id+'Chart']){state.charts[id+'Chart'].destroy();delete state.charts[id+'Chart'];}
    if(top.length)chart(id+'Chart',{type:'bar',data:{labels:top.map(d=>d.name),datasets:[{label:'Gross invoice line sales',data:top.map(d=>d.sales),backgroundColor:'#2E6FD9',borderRadius:3}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>invoiceMoney(c.parsed.x)}}},scales:{x:{beginAtZero:true,ticks:{maxTicksLimit:4,callback:v=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',notation:'compact',maximumFractionDigits:1}).format(v)}},y:{ticks:{autoSkip:false}}}}});
  };
}
