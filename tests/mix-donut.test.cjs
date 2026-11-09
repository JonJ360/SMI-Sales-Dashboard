const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const engine=require('../monthly-report.js');
function model(){return engine.build({as_of:'2026-10-31',months:{'2026-10':{current:{sales:100,profit:20}}},invoice_drilldown:{start:'2024-01-01',document_fields:['date','sales','profit','salesperson','kind'],documents:Array.from({length:31},(_,i)=>['2026-10-01',31-i+.01,1,i===30?'Other / excluded activity':'Person '+i,'Invoice'])}},'2026-10',{});}
function donut(m){return engine.render(m).match(/<svg class="salespeople-pie"[\s\S]*?<\/svg>/)?.[0];}
test('full pie retains all 31 individual names, zero legend and cent-exact values without grouping',()=>{
 const m=model();m.comparison[29].sales=0;const before=JSON.stringify(m.comparison),svg=donut(m);assert.ok(svg,'dedicated full pie exists');
 const groups=[...svg.matchAll(/data-value="([^"]+)" data-label="([^"]+)"/g)].map(r=>({value:Number(r[1]),name:r[2]}));
 assert.equal(groups.length,31);assert.deepEqual(groups.map(r=>r.name).sort(),m.comparison.map(r=>r.name).sort());
 assert.equal(Math.round(groups.reduce((n,r)=>n+r.value,0)*100),m.comparison.reduce((n,r)=>n+Math.round(r.sales*100),0));
 assert.match(svg,/0\.0%/);assert.equal((svg.match(/class="mix-legend-name"/g)||[]).length,31);
 assert.doesNotMatch(svg,/Remaining salespeople|<line|fill="#FFFFFF"/);
 assert.equal(JSON.stringify(m.comparison),before);assert.equal((engine.render(m).match(/<section/g)||[]).length,(engine.render({...m,comparison:[]}).match(/<section/g)||[]).length);
});
function native(shapes){
 const calls=[];const mixes=[{textContent:'year',querySelector:()=>({textContent:'Year'}),querySelectorAll:()=>[]},{textContent:'Sales mix',querySelector:s=>s==='svg.salespeople-pie'?{}:{textContent:'Salesperson mix'},querySelectorAll:s=>s==='[data-value]'?shapes:[]}];
 const section={classList:{contains:c=>c==='comparison-page'},querySelector:s=>s==='main'?{querySelector:()=>null}:{textContent:'Comparison'},querySelectorAll:()=>mixes};
 const pdf=new Proxy({splitTextToSize:t=>[t],getTextWidth:t=>t.length*4}, {get:(o,k)=>k in o?o[k]:(...args)=>calls.push([k,...args])});
 class Parser{parseFromString(){return {querySelectorAll:()=>[section]};}}
 const context={window:{MonthlyReport:{render:()=>''},jspdf:{jsPDF:function(){return pdf;}}},DOMParser:Parser};vm.runInNewContext(fs.readFileSync(require.resolve('../monthly-report-pdf.js'),'utf8'),context);context.window.MonthlyReportPDF.create({month:'2026-10',config:{company:'Test'}});return calls;
}
test('unknown chart values stay unavailable; zero and one-positive cohorts remain explicit',()=>{
 for(const value of [null,undefined,NaN]){const m=model();m.comparison[0].sales=value;const html=engine.render(m);assert.equal(donut(m),undefined);assert.match(html,/Unavailable — incomplete invoice coverage/);}
 const m=model();m.comparison.forEach(r=>r.sales=0);assert.match(donut(m),/No positive activity/);m.comparison[0].sales=12.34;assert.match(donut(m),/<circle cx="106" cy="127" r="92"/);assert.match(donut(m),/100.0%/);
 const calls=native([{dataset:{value:null,label:'Unknown'},getAttribute:()=> '#568AC4'}]);assert.ok(calls.some(c=>c[0]==='text'&&/Unavailable/.test(c[1])));assert.ok(!calls.some(c=>c[0]==='path'));
});
test('native full pie uses every typed name in two columns, zero percent, no hole or lines',()=>{
 const rows=Array.from({length:31},(_,i)=>({dataset:{value:i===30?'0':'1',label:i===30?'TYLERG':'Person '+i},getAttribute:()=> '#568AC4'}));const calls=native(rows);
 for(const row of rows)assert.ok(calls.some(c=>c[0]==='text'&&c[1]===row.dataset.label),row.dataset.label);
 const names=calls.filter(c=>c[0]==='text'&&rows.some(r=>r.dataset.label===c[1]));assert.deepEqual([...new Set(names.map(c=>c[2]))],[686,818]);assert.ok(names.every(c=>c[3]>=432&&c[3]<=620));
 assert.ok(calls.some(c=>c[0]==='text'&&c[1]==='0.0%'));assert.ok(!calls.some(c=>c[0]==='line'||c[0]==='circle'));
});
