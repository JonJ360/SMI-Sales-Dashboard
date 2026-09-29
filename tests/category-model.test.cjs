const {test}=require('node:test');
const assert=require('node:assert/strict');
const M=require('../item-categories.js');
const B=require('../branch-drilldown.js');
const doc=(key,date='2026-09-01',sales=100,extra={})=>({key,date,sales,kind:'Invoice',customer:'C',salesperson:'P',...extra});
const cats={source:'SMI.dbo.IV00101',fields:['item_class','category_1'],items:{a:['STEEL','50'],b:['TOOLS',''],c:['REBAR',''],d:['STEEL','51']}};
const detail={start:'2024-01-01',document_fields:[],documents:[doc('i'),doc('r','2026-09-01',-20,{kind:'Return'}),doc('other','2026-09-01',99,{customer:'X',salesperson:'X'}),doc('old','2024-01-01'),doc('future','2026-10-01')],line_fields:['item','sales'],lines:{i:[['a',40],['b',30],['c',10],['unknown',5],['b',-2]],r:[['a',-20]],other:[['d',99]],old:[['d',100]],future:[['b',1000]]}};
const data={as_of:'2026-09-29',invoice_drilldown:detail,item_categories:cats};
test('exact source types, reviewed Rebar rule; no SKU/description guessing',()=>{
 assert.equal(M.category(['STEEL','50']),'REBAR');assert.equal(M.category(['STEEL','51']),'STEEL');
 assert.equal(M.category(['TOOLS','']),'TOOLS');assert.equal(M.category(['','REBAR']),'Unclassified');
});
test('gross invoice dollars not returns or quantities; scoped entities and dates, cents and residual',()=>{
 const r=M.summarize(data,'customer','C',{period:'YTD'});
 assert.deepEqual(r.categories,[{name:'REBAR',sales:50},{name:'TOOLS',sales:28},{name:'Unclassified',sales:5}]);
 assert.equal(r.line_sales,83);assert.equal(r.header_sales,100);assert.equal(r.difference,17);
 assert.equal(r.unclassified_sales,5);assert.equal(r.missing_documents,0);
 assert.deepEqual(M.summarize(data,'salesperson','P',{period:'YTD'}),r);
 assert.equal(M.summarize(data,'customer','X',{period:'YTD'}).header_sales,99);
 assert.equal(M.summarize(data,'customer','C',{period:'MONTH',month:'2024-01'}).line_sales,100);
 assert.equal(M.summarize(data,'customer','C',{period:'1M'}).line_sales,83);
 assert.equal(M.summarize(data,'customer','C',{period:'FULL'}).line_sales,183);
 assert.equal(M.summarize(data,'customer','C',{period:'MONTH',month:'2026-10'}).header_sales,0);
});
test('five categories not five SKUs, deterministic ties, all lines reconcile, signed adjustments kept',()=>{
 const d={...data,invoice_drilldown:{...detail,documents:[doc('i',undefined,11)],lines:{i:Array.from({length:8},(_,i)=>({item:''+i,sales:i===7?-1:2}))}},item_categories:{...cats,items:Object.fromEntries(Array.from({length:8},(_,i)=>[''+i,['Type'+i,'']]))}};
 const r=M.summarize(d,'customer','C',{period:'YTD'});assert.equal(r.categories.length,5);assert.equal(r.category_count,8);assert.equal(r.line_sales,13);assert.equal(r.difference,-2);assert.equal(r.other_sales,3);assert.equal(r.categories[0].name,'Type0');
});
test('missing and legacy data distinct from zero; no fabricated categories',()=>{
 assert.equal(M.summarize({...data,item_categories:undefined},'customer','C',{period:'YTD'}),null);
 assert.equal(M.summarize({...data,invoice_drilldown:undefined},'customer','C',{period:'YTD'}),null);
 const r=M.summarize({...data,invoice_drilldown:{...detail,lines:{}}},'customer','C',{period:'YTD'});
 assert.equal(r.missing_documents,1);assert.equal(r.difference,100);assert.deepEqual(r.categories,[]);
 assert.deepEqual(M.summarize(data,'customer','absent',{period:'YTD'}).categories,[]);
});
test('columnar documents and prototype-like item IDs are safe',()=>{
 const d={...data,item_categories:{...cats,items:{}},invoice_drilldown:{...detail,document_fields:['key','date','sales','kind','customer','salesperson'],documents:[['i','2026-09-01',1,'Invoice','C','P']],lines:{i:[['__proto__',1]]}}};
 assert.deepEqual(M.summarize(d,'customer','C',{period:'YTD'}).categories,[{name:'Unclassified',sales:1}]);
});
