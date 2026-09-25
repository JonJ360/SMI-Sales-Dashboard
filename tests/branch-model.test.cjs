const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const B=require('../branch-drilldown.js');
const doc=(overrides={})=>({key:'Invoice:01',sop:'01',date:'2026-09-24',location:'BIS',customer:'Fargo customer',salesperson:'ONE',kind:'Invoice',sales:100,cost:150,profit:-50,...overrides});
const rows=[doc(),doc({key:'Return:01',kind:'Return',sales:-20,cost:-10,profit:-10}),doc({key:'Invoice:02',location:'FARGO',salesperson:'TWO'}),doc({key:'Invoice:03',date:'2026-08-25',cost:0,profit:100}),doc({key:'Invoice:04',date:'2026-08-26',customer:'Other',cost:0,profit:100}),doc({key:'Invoice:05',date:'2026-09-25'})];
test('branch uses header location, inclusive 30 days, no future documents',()=>{
 const got=B.scope(rows,{period:'1M'},'2026-09-24','2024-01-01','BIS');
 assert.deepEqual(got.map(d=>d.key),['Invoice:01','Return:01','Invoice:04']);
 const t=B.totals(got);assert.equal(t.sales,180);assert.equal(t.cost,140);assert.equal(t.profit,40);assert.equal(t.invoices,2);assert.equal(t.return_docs,1);assert.equal(t.customers,2);assert.equal(t.returns,20);assert.equal(t.gross_sales,200);assert.equal(t.loss_invoices,1);assert.equal(t.zero_cost_invoices,1);
});
test('specific month caps at as-of and unknown / return-only branches remain',()=>{
 assert.equal(B.scope(rows,{period:'MONTH',month:'2026-09'},'2026-09-24','2024-01-01','BIS').length,2);
 assert.equal(B.scope(rows,{period:'MONTH',month:'2026-10'},'2026-09-24','2024-01-01','BIS').length,0);
 const g=B.group([doc({location:'Unassigned',kind:'Return',sales:-20,cost:-10,profit:-10})],'location');
 assert.equal(g[0].name,'Unassigned');assert.equal(g[0].sales,-20);assert.equal(g[0].margin_pct,null);
});
test('cents preserved and missing detail is unavailable, never a zero result',()=>{
 assert.equal(B.totals([doc({sales:.1}),doc({sales:.2})]).sales,.3);
 assert.equal(B.decode(null),null);assert.deepEqual(B.decode({document_fields:[],documents:[]}),[]);
});
test('trend includes empty months and partial endpoint without inventing prior activity',()=>{
 const trend=B.trend([doc()],{period:'YTD'},'2026-09-24','2024-01-01');
 assert.equal(trend.length,9);assert.equal(trend[0].sales,0);assert.equal(trend[8].profit,-50);
});
test('group membership and filters preserve branch invoice / return identity',()=>{
 const selected=B.scope(rows,{period:'YTD'},'2026-09-24','2024-01-01','BIS');
 assert.equal(B.group(selected,'salesperson')[0].sales,280);
 assert.equal(B.filter(selected,{kind:'Return',search:'01'}).length,1);
 assert.equal(B.filter(selected,{kind:'all',signal:'loss'}).length,1);
 assert.equal(B.filter(selected,{kind:'all',customer:'Other'}).length,1);
});
test('monthly comparison tolerates legacy detail without start date',()=>{
 assert.equal(B.monthlyComparison([], '2026-09-24', undefined, 'FARGO').length,33);
});
test('monthly comparison fills elapsed months, not future months, and isolates branch',()=>{
 const got=B.monthlyComparison(rows,'2026-09-24','2024-01-01','BIS');
 assert.equal(got.length,33);
 assert.equal(got.find(d=>d.year===2026&&d.month===9).sales,80);
 assert.equal(got.find(d=>d.year===2024&&d.month===1).sales,0);
 assert.ok(!got.some(d=>d.year===2026&&d.month===10));
});
test('top items use scoped invoice source lines, exclude returns, preserve cents and disclose gaps',()=>{
 const docs=[doc(),doc({key:'Return:01',kind:'Return',sales:-20}),doc({key:'Invoice:missing',sales:30})];
 const detail={line_fields:['item','description','sales'],lines:{'Invoice:01':[['A','Alpha',.1],['A','Alpha',.2],['B','Beta',50],['','No ID',2]],'Return:01':[['A','Alpha',-20]],'Invoice:other':[['X','Other branch',9999]]}};
 const got=B.topItems(docs,detail);
 assert.deepEqual(got.items.map(i=>i.item),['B','','A']);
 assert.equal(got.items[2].gross_sales,.3);
 assert.equal(got.line_sales,52.3);assert.equal(got.header_sales,130);assert.equal(got.difference,77.7);
 assert.equal(got.missing_documents,1);
 assert.equal(B.topItems(docs,null),null);
 assert.equal(B.topItems(docs,{lines:{'Invoice:01':[{item:'Z',description:'Object row',sales:9}]}}).items[0].gross_sales,9);
 assert.equal(B.topItems([doc({kind:'Return'})],detail).items.length,0);
});
test('real snapshot: top ten items reconcile independently for all branch-period scopes',t=>{
 if(!fs.existsSync('data/sales.json'))return t.skip('Local snapshot not present');
 const data=JSON.parse(fs.readFileSync('data/sales.json','utf8')),detail=data.invoice_drilldown,decoded=B.decode(detail);
 const scopes=[...['YTD','1M','FULL'].map(period=>({period})),...Object.keys(data.months).filter(m=>m<=data.as_of.slice(0,7)).map(month=>({period:'MONTH',month}))];
 let verified=0;
 for(const f of scopes)for(const branch of new Set(decoded.map(d=>d.location))){
  const docs=B.scope(decoded,f,data.as_of,detail.start,branch),got=B.topItems(docs,detail),groups=new Map();let sum=0;
  for(const d of docs)if(d.kind==='Invoice')for(const raw of detail.lines[d.key]||[]){
   const line=Array.isArray(raw)?Object.fromEntries(detail.line_fields.map((k,i)=>[k,raw[i]])):raw;
   const key=String(line.item||''),n=Math.round(Number(line.sales||0)*100);groups.set(key,(groups.get(key)||0)+n);sum+=n;
  }
  const expected=[...groups].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).slice(0,10).map(([item,n])=>({item,gross_sales:n/100}));
  assert.deepEqual(got.items.map(({item,gross_sales})=>({item,gross_sales})),expected);
  assert.equal(got.line_sales,sum/100);verified++;
 }
 console.log(`Verified top items for ${verified} real branch-period scopes`);
});
test('real snapshot: every branch reconciles to every selectable report period',t=>{
 if(!fs.existsSync('data/sales.json'))return t.skip('Local snapshot not present in clean CI checkout');
 const data=JSON.parse(fs.readFileSync('data/sales.json','utf8'));const decoded=B.decode(data.invoice_drilldown);
 assert.ok(decoded?.length>0);
 const scopes=[...['YTD','1M','FULL'].map(period=>[{period},data.rankings[period].branches]),...Object.entries(data.months).filter(([m])=>m<=data.as_of.slice(0,7)).map(([month,v])=>[{period:'MONTH',month},v.rankings.branches])];
 let verified=0;
 for(const [f,rank] of scopes){
  const got=B.group(B.scope(decoded,f,data.as_of,data.invoice_drilldown.start),'location');
  assert.equal(got.length,rank.length,JSON.stringify(f));
  for(const expected of rank){const actual=got.find(x=>x.name===expected.name);assert.ok(actual,expected.name);
   for(const key of ['sales','cost','profit','gross_sales','returns','invoices','return_docs','customers'])assert.ok(Math.abs(actual[key]-expected[key])<.011,`${JSON.stringify(f)} ${expected.name} ${key}: ${actual[key]} != ${expected[key]}`);
   verified++;
  }
 }
 console.log(`Reconciled ${verified} real branch-period totals across ${scopes.length} scopes`);
});
