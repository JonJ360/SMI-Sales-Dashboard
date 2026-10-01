const {test}=require('node:test');
const assert=require('node:assert/strict');
const M=require('../item-categories.js');
const data={as_of:'2026-09-29',returns_included:true,item_categories:{source:'SMI.dbo.IV00101',items:{a:['STEEL','50'],b:['TOOLS','']}},invoice_drilldown:{start:'2024-01-01',documents:[{key:'i',date:'2026-01-02',kind:'Invoice',sales:100},{key:'r',date:'2026-01-03',kind:'Return',sales:-20},{key:'f',date:'2026-10-01',kind:'Invoice',sales:999},{key:'m',date:'2026-09-01',kind:'Invoice',sales:10}],line_fields:['item','sales'],lines:{i:[['a',50],['b',30],['unknown',5],['b',-2]],r:[['a',-20]],f:[['b',999]]}}};
test('annual categories reconcile every signed invoice line, exclude returns/future and disclose header residual',()=>{
 assert.equal(typeof M.annual,'function');
 const r=M.annual(data,2026);
 assert.deepEqual(r.categories.map(x=>[x.name,x.sales]),[['REBAR',50],['TOOLS',28],['Unclassified',5]]);
 assert.equal(r.line_sales,83);assert.equal(r.header_sales,110);assert.equal(r.difference,27);
 assert.equal(r.return_sales,-20);assert.equal(r.missing_documents,1);
 assert.equal(r.categories[0].months.length,12);assert.equal(r.categories[0].months[0],50);
 assert.equal(r.categories[0].months[8],0);assert.equal(r.categories[0].months[9],null);
 assert.equal(r.months[8].status,'Partial');assert.equal(r.months[9].status,'Future');
});
test('partial source-start month is not misrepresented as complete',()=>{
 const r=M.annual({...data,invoice_drilldown:{...data.invoice_drilldown,start:'2026-01-15'}},2026);
 assert.equal(r.months[0].status,'Partial');assert.equal(r.months[1].status,'Actual');
});
test('legacy missing dimensions remain unavailable; source start fallback and columnar documents work',()=>{
 assert.equal(M.annual({...data,item_categories:undefined},2026),null);
 assert.equal(M.annual({...data,invoice_drilldown:undefined},2026),null);
 const d={...data,invoice_drilldown:{...data.invoice_drilldown,start:undefined,document_fields:['key','date','kind','sales'],documents:[['i','2026-01-02','Invoice',100]]}};
 assert.equal(M.annual(d,2026).line_sales,83);
 assert.equal(M.annual(data,2025).line_sales,0);
 assert.equal(M.annual({...data,returns_included:false},2026).returns_included,false);
});
