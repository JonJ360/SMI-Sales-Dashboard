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
 assert.match(svg,/\(0\)/);assert.equal((svg.match(/class="mix-callout-name"/g)||[]).length,31);
 assert.doesNotMatch(svg,/Remaining salespeople|mix-legend-name|fill="#FFFFFF"/);
 assert.equal(JSON.stringify(m.comparison),before);assert.equal((engine.render(m).match(/<section/g)||[]).length,(engine.render({...m,comparison:[]}).match(/<section/g)||[]).length);
});
function native(shapes){
 const calls=[];const mixes=[{textContent:'year',querySelector:()=>({textContent:'Year'}),querySelectorAll:()=>[]},{textContent:'Sales mix',querySelector:s=>s==='svg.salespeople-pie'?{}:{textContent:'Salesperson mix'},querySelectorAll:s=>s==='[data-value]'?shapes:[]}];
 const section={classList:{contains:c=>c==='comparison-page'},querySelector:s=>s==='main'?{querySelector:()=>null}:{textContent:'Comparison'},querySelectorAll:()=>mixes};
 const pdf=new Proxy({splitTextToSize:t=>[t],getTextWidth:t=>t.length*4}, {get:(o,k)=>k in o?o[k]:(...args)=>calls.push([k,...args])});
 class Parser{parseFromString(){return {querySelectorAll:()=>[section]};}}
 const context={window:{MonthlyReport:{render:()=>'',salespersonLayout:engine.salespersonLayout},jspdf:{jsPDF:function(){return pdf;}}},DOMParser:Parser};vm.runInNewContext(fs.readFileSync(require.resolve('../monthly-report-pdf.js'),'utf8'),context);context.window.MonthlyReportPDF.create({month:'2026-10',config:{company:'Test'}});return calls;
}
test('unknown chart values stay unavailable; zero and one-positive cohorts remain explicit',()=>{
 for(const value of [null,undefined,NaN]){const m=model();m.comparison[0].sales=value;const html=engine.render(m);assert.equal(donut(m),undefined);assert.match(html,/Unavailable — incomplete invoice coverage/);}
 const m=model();m.comparison.forEach(r=>r.sales=0);assert.match(donut(m),/No positive activity/);m.comparison[0].sales=12.34;assert.match(donut(m),/<circle cx="245" cy="145" r="92"/);assert.equal((donut(m).match(/<polyline/g)||[]).length,1);
 const calls=native([{dataset:{value:null,label:'Unknown'},getAttribute:()=> '#568AC4'}]);assert.ok(calls.some(c=>c[0]==='text'&&/Unavailable/.test(c[1])));assert.ok(!calls.some(c=>c[0]==='path'));
});
test('native full pie preserves every name and routes leaders strictly outside the circle',()=>{
 const rows=Array.from({length:31},(_,i)=>({dataset:{value:i===30?'0':'1',label:i===30?'TYLERG':'Person '+i},getAttribute:()=> '#568AC4'}));const calls=native(rows);
 for(const row of rows)assert.ok(calls.some(c=>c[0]==='text'&&c[1]===row.dataset.label+(row.dataset.value==='0'?' (0)':'')),row.dataset.label);
 const lines=calls.filter(c=>c[0]==='line');assert.equal(lines.length,90);
 for(const [,ax,ay,bx,by] of lines){const dx=bx-ax,dy=by-ay,t=Math.max(0,Math.min(1,((711-ax)*dx+(529-ay)*dy)/(dx*dx+dy*dy)||0));assert.ok(Math.hypot(ax+t*dx-711,ay+t*dy-529)>=92-1e-7);}
 const expected=engine.salespersonLayout(rows.map(r=>({name:r.dataset.label,value:Number(r.dataset.value)})));for(const r of expected)assert.ok(calls.some(c=>c[0]==='text'&&c[2]===466+r.x&&c[3]===384+r.y+3));
});
