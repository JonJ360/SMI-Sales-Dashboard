const test=require('node:test'),assert=require('node:assert/strict'),report=require('../monthly-report.js');
test('Power BI direct-label density suppresses only small labels, never slices or typed identities',()=>{
 const rows=[{name:'Large',value:99},{name:'Tiny person',value:.49},{name:'Visible person',value:.51}],layout=report.salespersonLayout(rows);
 assert.equal(layout.length,3);assert.equal(layout.reduce((n,r)=>n+r.cents,0),10000);
 assert.ok(layout.every(r=>r.end>r.start),'every positive person retains a real individual wedge');
 assert.equal(layout.find(r=>r.name==='Tiny person').showLabel,false);
 assert.equal(layout.find(r=>r.name==='Tiny person').points.length,0);
 assert.equal(layout.find(r=>r.name==='Visible person').showLabel,true);
 assert.equal(layout.find(r=>r.name==='Large').showLabel,true);
 assert.ok(layout.every(r=>Number.isFinite(r.x)&&Number.isFinite(r.y)),'ignored labels without engine transforms remain safe');
});
