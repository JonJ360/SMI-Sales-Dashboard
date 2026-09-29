/* Customer report: source-ranked name cohorts, never a re-sort of the other cohort. */
(function(root){
'use strict';
const iso=d=>d.toISOString().slice(0,10);
function shiftYear(value,years){
  const [y,m,d]=value.split('-').map(Number),last=new Date(Date.UTC(y-years,m,0)).getUTCDate();
  return iso(new Date(Date.UTC(y-years,m-1,Math.min(d,last))));
}
function dateRange(data,period,month){
  const end=data.as_of;
  let start=end.slice(0,4)+'-01-01',priorEnd=shiftYear(end,1),years=1;
  if(period==='1M'){const d=new Date(end+'T00:00:00Z');d.setUTCDate(d.getUTCDate()-29);start=iso(d)}
  if(period==='FULL'){const keys=Object.keys(data.years).map(Number);start=Math.min(...keys)+'-01-01';years=keys.length;priorEnd=shiftYear(end,years)}
  if(period==='MONTH'){
    const [y,m]=month.split('-').map(Number),monthEnd=iso(new Date(Date.UTC(y,m,0)));
    // Snapshot compares the whole prior month, even when current month is partial.
    return Object.freeze({current_start:month+'-01',current_end:monthEnd<end?monthEnd:end,prior_start:shiftYear(month+'-01',1),prior_end:iso(new Date(Date.UTC(y-1,m,0)))});
  }
  return Object.freeze({current_start:start,current_end:end,prior_start:shiftYear(start,years),prior_end:priorEnd});
}
function build(data,options={}){
  const {period='YTD',month='',cohort='current',search=''}=options;
  const selected=period==='MONTH'?data.months[month]:data.comparisons[period];
  const rankings=period==='MONTH'?selected.rankings:data.rankings[period];
  const source=cohort==='prior'?selected.customer_comparison:rankings.customers;
  const rows=source.slice(0,25).map((x,i)=>{
    const current=cohort==='prior'?x.current_sales:x.sales,prior=x.prior_sales;
    const change=(Math.round(current*100)-Math.round(prior*100))/100;
    return Object.freeze({rank:i+1,name:x.name,current_sales:current,prior_sales:prior,dollar_change:change,percent_change:prior===0?null:change/Math.abs(prior)});
  }).filter(x=>x.name.toLowerCase().includes(search.toLowerCase()));
  return Object.freeze({period,month,cohort,search,rows:Object.freeze(rows),cohort_count:Math.min(25,source.length),dates:dateRange(data,period,month),data_asof:data.as_of,source:data.source,source_sha256:data.sha256||'Unavailable',refresh_heartbeat:data.refreshed_at||'Unavailable'});
}
function workbook(report,XLSX,exportedAt=new Date().toISOString()){
  const wb=XLSX.utils.book_new(),rank=report.cohort==='prior'?'Prior rank':'Current rank';
  const ws=XLSX.utils.aoa_to_sheet([[rank,'Customer name','Prior net sales (USD)','Current net sales (USD)','Dollar change (USD)','Percent change'],...report.rows.map(x=>[x.rank,x.name,x.prior_sales,x.current_sales,x.dollar_change,x.percent_change===null?'N/A':x.percent_change])]);
  // AOA strings are explicit string cells, never formulas, even for = + - @ prefixes.
  for(let i=2;i<=report.rows.length+1;i++){
    for(const col of ['C','D','E'])ws[col+i].z='$#,##0.00;[Red]-$#,##0.00';
    if(ws['F'+i].t==='n')ws['F'+i].z='0.0%;[Red]-0.0%';
  }
  ws['!cols']=[{wch:14},{wch:48},{wch:24},{wch:24},{wch:24},{wch:20}];
  ws['!autofilter']={ref:ws['!ref']};
  XLSX.utils.book_append_sheet(wb,ws,'Customer Comparison');
  const date=value=>({t:'n',v:(Date.parse(value+'T00:00:00Z')-Date.UTC(1899,11,30))/86400000,z:'yyyy-mm-dd'});
  const info=[['Field','Value'],['Report','SMI Sales Dashboard — Customer Comparison'],['App version','1.21'],['Period',report.period],['Selected month',report.period==='MONTH'?report.month:'Not applicable'],['Ranking cohort',report.cohort==='prior'?'Prior-period Top 25':'Current-period Top 25'],['Search (case-insensitive substring)',report.search],['Exported row count',report.rows.length],['Cohort row count before search',report.cohort_count],['Current start',date(report.dates.current_start)],['Current end',date(report.dates.current_end)],['Prior start',date(report.dates.prior_start)],['Prior end',date(report.dates.prior_end)],['Data as of',date(report.data_asof)],['Source',report.source],['Source snapshot SHA-256',report.source_sha256],['Refresh / publication heartbeat (UTC)',report.refresh_heartbeat],['Exported at (UTC)',exportedAt],['Metric','Posted normal invoices less returns; document date; net sales in USD'],['Grouping','Customer name, not customer ID; no IDs available in aggregation'],['Population','Selected top-25 cohort only; search filters that cohort, not all customers; rank remains original cohort rank'],['Percent change','(Current - Prior) / ABS(Prior); N/A when prior is zero; negative net sales can reflect returns'],['Month comparison','Specific month uses whole prior calendar month; current month ends at data as-of'],['Freshness','Data as-of/source hash identify business snapshot; refresh/publication heartbeat is separate and may advance without new source data']];
  const meta=XLSX.utils.aoa_to_sheet(info);meta['!cols']=[{wch:42},{wch:110}];
  XLSX.utils.book_append_sheet(wb,meta,'Report Info');return wb;
}
const api={build,workbook};
if(typeof module==='object'&&module.exports)module.exports=api;else root.CustomerReport=api;
})(typeof globalThis==='object'?globalThis:this);
