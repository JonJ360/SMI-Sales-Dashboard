const test=require('node:test'),assert=require('node:assert/strict');
const report=require('../monthly-report.js');
test('Power BI pie geometry uses reference size and native ECharts guide lines',()=>{
 const rows=Array.from({length:47},(_,i)=>({name:'Person '+i,value:i===46?0:Math.pow(1.15,46-i)}));
 const layout=report.salespersonLayout(rows);
 assert.equal(layout.length,47);
 for(const r of layout){assert.equal(r.cx,315);assert.equal(r.cy,172.5);assert.equal(r.radius,129);if(r.cents>0){assert.equal(r.points.length,r.showLabel?3:0);assert.ok(Number.isFinite(r.x)&&Number.isFinite(r.y));}else assert.equal(r.points.length,0);}
 assert.ok(new Set(layout.filter(r=>r.points.length).map(r=>r.points[1][0].toFixed(2))).size>10,'no shared vertical wiring rails');
});
