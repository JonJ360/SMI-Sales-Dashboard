const {test}=require('node:test');
const assert=require('node:assert/strict');
const M=require('../salesperson-comparison.js');
const fixture=()=>({as_of:'2026-10-08',returns_included:true,sha256:'fixture',item_categories:{source:'SMI.dbo.IV00101',items:{a:['REBAR',''],b:['TOOLS',''],c:['PRIOR ONLY',''],d:['NEW','']}},invoice_drilldown:{start:'2024-01-01',end:'2026-10-08',line_fields:['item','sales'],documents:[
{key:'a',date:'2026-10-08',salesperson:'DYLAN',kind:'Invoice',sales:100},
{key:'r',date:'2026-10-08',salesperson:'DYLAN',kind:'Return',sales:-20},
{key:'b',date:'2025-10-08',salesperson:'DYLAN',kind:'Invoice',sales:50},
{key:'late',date:'2025-10-09',salesperson:'DYLAN',kind:'Invoice',sales:999},
{key:'other',date:'2026-10-08',salesperson:'OTHER REP',kind:'Invoice',sales:10000}],lines:{a:[['a',80],['b',10],['d',10]],b:[['a',30],['c',20]],other:[['a',10000]],late:[['a',999]],r:[['a',-20]]}}});
test('same elapsed YTD/month, rolling window and leap endpoints',()=>{
const f=fixture();assert.deepEqual(M.dates(f,{period:'YTD'}),{current_start:'2026-01-01',current_end:'2026-10-08',prior_start:'2025-01-01',prior_end:'2025-10-08'});
assert.equal(M.dates(f,{period:'MONTH',month:'2026-10'}).prior_end,'2025-10-08');
assert.equal(M.dates(f,{period:'MONTH',month:'2025-09'}).prior_end,'2024-09-30');
assert.equal(M.dates(f,{period:'1M'}).current_start,'2026-09-09');
assert.equal(M.dates({...f,as_of:'2024-02-29'},{period:'YTD'}).prior_end,'2023-02-28');
});
test('shared union retains prior-only/new, exact cents, gross/returns/net and identity',()=>{
const r=M.build(fixture(),'DYLAN',{period:'YTD'});
assert.equal(r.current.net,80);assert.equal(r.prior.net,50);assert.equal(r.current.gross,100);assert.equal(r.current.returns,20);assert.equal(r.current.line_sales,100);assert.equal(r.current.residual,0);
assert.equal(r.rows.find(x=>x.name==='PRIOR ONLY').current,0);assert.equal(r.rows.find(x=>x.name==='PRIOR ONLY').pct,-100);
assert.equal(r.rows.find(x=>x.name==='NEW').label,'New');assert.equal(r.rows.find(x=>x.name==='REBAR').delta,50);
assert.equal(r.current.invoices,1);assert.equal(r.current.missing,0);assert.ok(!JSON.stringify(r).includes('OTHER REP'));
});
test('history before coverage unavailable not zero; full history shift unavailable; absent categories unavailable',()=>{
const f=fixture();for(const filter of [{period:'MONTH',month:'2024-01'},{period:'FULL'}]){const r=M.build(f,'DYLAN',filter);assert.equal(r.prior,null);assert.ok(r.rows.every(x=>x.prior===null&&x.delta===null));}
assert.equal(M.build({...f,invoice_drilldown:undefined},'DYLAN',{period:'YTD'}).current,null);
const r=M.build({...f,item_categories:undefined},'DYLAN',{period:'YTD'});assert.equal(r.current.net,80);assert.equal(r.current.line_sales,null);assert.deepEqual(r.rows,[]);
});
test('zero, negative base, missing lines and signed adjustments remain explicit',()=>{
assert.deepEqual(M.change(0,0),{delta:0,pct:null,label:'N/A'});assert.equal(M.change(-5,0).label,'N/A');assert.equal(M.change(5,-5).pct,200);assert.equal(M.change(5,null).delta,null);
const f=fixture();f.invoice_drilldown.lines.a=[['a',100.01],['a',-.02]];const r=M.build(f,'DYLAN',{period:'YTD'});assert.equal(r.current.line_sales,99.99);assert.equal(r.current.residual,.01);
delete f.invoice_drilldown.lines.a;assert.equal(M.build(f,'DYLAN',{period:'YTD'}).current.missing,1);
});
test('prototype-like prior-only category is zero not inherited object',()=>{const f=fixture();f.item_categories.items.c=['constructor',''];const r=M.build(f,'DYLAN',{period:'YTD'}).rows.find(x=>x.name==='constructor');assert.equal(r.current,0);assert.equal(r.prior,20);assert.equal(r.pct,-100);});
test('columnar source and no mutations',()=>{const f=fixture(),before=JSON.stringify(f);const fields=Object.keys(f.invoice_drilldown.documents[0]);const g=structuredClone(f);g.invoice_drilldown.document_fields=fields;g.invoice_drilldown.documents=g.invoice_drilldown.documents.map(d=>fields.map(k=>d[k]));assert.deepEqual(M.build(g,'DYLAN',{period:'YTD'}),M.build(f,'DYLAN',{period:'YTD'}));assert.equal(JSON.stringify(f),before);});
