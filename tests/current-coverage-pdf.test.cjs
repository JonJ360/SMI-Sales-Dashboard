const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const engine=require('../monthly-report.js');
function snapshot(start){return {as_of:'2026-10-31',months:{'2026-10':{current:{sales:150,profit:30}}},invoice_drilldown:{start,document_fields:['date','sales','profit','salesperson','kind'],documents:[['2026-10-01',150,30,'A','Invoice']]}};}
test('current gross comparison requires declared full YTD coverage, not first observed invoices',()=>{
 for(const start of ['2026-10-01',undefined,'invalid']){
 const m=engine.build(snapshot(start),'2026-10',{}),r=m.comparison[0];
 assert.equal(r.sales,null,`gross sales coverage ${start}`);assert.equal(r.profit,null);
 assert.equal(r.sales_delta,null);assert.equal(r.profit_delta,null);
 assert.equal(r.sales_change,'Unavailable');assert.equal(r.profit_change,'Unavailable');
 }
 const r=engine.build(snapshot('2024-01-02'),'2026-10',{}).comparison[0];
 assert.equal(r.sales,150);assert.equal(r.profit,30);assert.equal(r.prior_sales,0);assert.equal(r.prior_profit,0);
});
function pdfTexts(status){
 const texts=[];const mix={textContent:status,querySelector:()=>({textContent:'Gross sales by year'}),querySelectorAll:()=>[]};
 const section={classList:{contains:c=>c==='comparison-page'},querySelector:s=>s==='main'?{querySelector:q=>q==='table'?{querySelectorAll:s=>s==='tr'?[{children:Array.from({length:5},()=>({textContent:''}))}]:[]}:null}:{textContent:'Comparison'},querySelectorAll:s=>s==='.sales-mix'?[mix]:[]};
 class Parser{parseFromString(){return {querySelectorAll:()=>[section]};}}
 const pdf=new Proxy({text:t=>texts.push(t),splitTextToSize:t=>[t]}, {get:(o,k)=>k in o?o[k]:()=>{}});
 const context={window:{MonthlyReport:{capitalizeWords:require('../monthly-report.js').capitalizeWords,displayModel:m=>m,render:()=>''},jspdf:{jsPDF:function(){return pdf;}}},DOMParser:Parser};
 vm.runInNewContext(fs.readFileSync(require.resolve('../assets/monthly-report-arial-black-pdf.js'),'utf8'),context);vm.runInNewContext(fs.readFileSync(require.resolve('../monthly-report-pdf.js'),'utf8'),context)
 context.window.MonthlyReportPDF.create({month:'2026-10',asOf:'2026-10-31',sha256:'test',comparison:[{name:'A',sales:0,prior_sales:0,profit:0,prior_profit:0}],config:{company:'Test'}});
 return texts.join('\n');
}
test('native PDF preserves incomplete coverage status rather than claiming zero activity',()=>{
 const text=pdfTexts('Gross sales by year Unavailable — incomplete invoice coverage.');
 assert.match(text,/Unavailable.*Incomplete Invoice Coverage/);assert.doesNotMatch(text,/No Positive Activity/);
});
test('native PDF legitimate all-zero chart retains no positive activity status',()=>{
 assert.match(pdfTexts('Gross sales by year'),/No Positive Activity/);
});
