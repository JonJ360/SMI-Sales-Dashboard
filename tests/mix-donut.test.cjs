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
 assert.ok(groups.some(r=>r.value===0),'zero remains typed without an invented wedge');assert.equal((svg.match(/class="mix-callout-name"/g)||[]).length,engine.salespersonLayout(groups.map(r=>({name:r.name,value:r.value}))).filter(r=>r.showLabel).length);assert.ok(engine.render(m).includes('<td>'+m.comparison[29].name+'</td>'),'zero salesperson remains in the comparison table');
 assert.doesNotMatch(svg,/Remaining salespeople|mix-legend-name|fill="#FFFFFF"/);
 assert.equal(JSON.stringify(m.comparison),before);assert.equal((engine.render(m).match(/<section/g)||[]).length,(engine.render({...m,comparison:[]}).match(/<section/g)||[]).length);
});
function native(shapes){
 const calls=[];const mixes=[{textContent:'year',querySelector:()=>({textContent:'Year'}),querySelectorAll:()=>[]},{textContent:'Sales mix',querySelector:s=>s==='svg.salespeople-pie'?{}:{textContent:'Salesperson mix'},querySelectorAll:s=>s==='[data-value]'?shapes:[]}];
 const section={classList:{contains:c=>c==='comparison-page'},querySelector:s=>s==='main'?{querySelector:q=>q==='table'?{querySelectorAll:s=>s==='tr'?[{children:Array.from({length:5},()=>({textContent:''}))}]:[]}:null}:{textContent:'Comparison'},querySelectorAll:()=>mixes};
 const pdf=new Proxy({splitTextToSize:t=>[t],getTextWidth:t=>t.length*4}, {get:(o,k)=>k in o?o[k]:(...args)=>calls.push([k,...args])});
 class Parser{parseFromString(){return {querySelectorAll:()=>[section]};}}
 const context={window:{MonthlyReport:{displayModel:m=>m,render:()=>'',salespersonLayout:engine.salespersonLayout},jspdf:{jsPDF:function(){return pdf;}}},DOMParser:Parser};vm.runInNewContext(fs.readFileSync(require.resolve('../assets/monthly-report-arial-black-pdf.js'),'utf8'),context);vm.runInNewContext(fs.readFileSync(require.resolve('../monthly-report-pdf.js'),'utf8'),context);context.window.MonthlyReportPDF.create({month:'2026-10',comparison:shapes.map(s=>({name:s.dataset.label,sales:s.dataset.value,prior_sales:0,profit:0,prior_profit:0})),config:{company:'Test'}});return calls;
}
test('unknown chart values stay unavailable; zero and one-positive cohorts remain explicit',()=>{
 for(const value of [null,undefined,NaN]){const m=model();m.comparison[0].sales=value;const html=engine.render(m);assert.equal(donut(m),undefined);assert.match(html,/Unavailable — incomplete invoice coverage/);}
 const m=model();m.comparison.forEach(r=>r.sales=0);assert.match(donut(m),/No positive activity/);m.comparison[0].sales=12.34;assert.match(donut(m),/<circle cx="315" cy="172.5" r="129"/);assert.equal((donut(m).match(/<polyline/g)||[]).length,1);
 const calls=native([{dataset:{value:null,label:'Unknown'},getAttribute:()=> '#568AC4'}]);assert.ok(calls.some(c=>c[0]==='text'&&/Unavailable/.test(c[1])));assert.ok(!calls.some(c=>c[0]==='path'));
});
test('native full pie labels every positive name and preserves engine guide-line coordinates',()=>{
 const rows=Array.from({length:31},(_,i)=>({dataset:{value:i===30?'0':'1',label:i===30?'TYLERG':'Person '+i},getAttribute:()=> '#568AC4'}));const calls=native(rows);
 const expected=engine.salespersonLayout(rows.map(r=>({name:r.dataset.label,value:Number(r.dataset.value)}))).filter(r=>r.cents>0&&r.showLabel);
 assert.equal(expected.length,30);
 for(const r of expected)assert.ok(calls.some(c=>c[0]==='text'&&c[1]===r.name&&c[2]===647+(r.x-315)*1.1&&c[3]===493+(r.y-172.5)*1.1+2.7),r.name);
 assert.ok(!calls.some(c=>c[0]==='text'&&/^TYLERG(?: \(0\))?$/.test(c[1])),'zero has no invented wedge or positive callout');
 const lines=calls.filter(c=>c[0]==='line');
 const expectedLines=expected.flatMap(r=>r.points.slice(1).map((p,i)=>['line',647+(r.points[i][0]-315)*1.1,493+(r.points[i][1]-172.5)*1.1,647+(p[0]-315)*1.1,493+(p[1]-172.5)*1.1]));
 assert.deepEqual(lines,expectedLines,'native leaders use the engine points, not shared rails');
 assert.equal(calls.filter(c=>c[0]==='path').length,30,'exactly one wedge per positive salesperson');
});
