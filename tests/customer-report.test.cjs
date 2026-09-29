const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const model=fs.existsSync(require('node:path').join(__dirname,'../customer-report.js'))?require('../customer-report.js'):{};
const sample=()=>({as_of:'2026-09-29',source:'Dynamics GP SQL',sha256:'source-hash',refreshed_at:'2026-09-29T18:00:00Z',years:{2024:{},2025:{},2026:{}},rankings:{YTD:{customers:[{name:'New leader',sales:123.45,prior_sales:20.01},{name:'Shared',sales:42,prior_sales:0}]}},comparisons:{YTD:{customer_comparison:[{name:'Old leader',current_sales:0,prior_sales:400}]}}});
test('default YTD selects actual current cohort, not sorted prior watchlist; filter retains source rank and frozen values',()=>{
 assert.equal(typeof model.build,'function','customer report builder required');
 const data=sample(),report=model.build(data);
 assert.equal(report.period,'YTD');assert.equal(report.cohort,'current');assert.deepEqual(report.rows.map(x=>x.name),['New leader','Shared']);
 assert.equal(report.rows[0].current_sales,123.45);assert.equal(report.rows[0].dollar_change,103.44);
 assert.equal(model.build(data,{cohort:'prior'}).rows[0].name,'Old leader');
 assert.equal(model.build(data,{search:'SHARED'}).rows[0].rank,2);
 data.rankings.YTD.customers[0].sales=999;assert.equal(report.rows[0].current_sales,123.45);assert.ok(Object.isFrozen(report.rows[0]));
});
test('signed change uses absolute prior, zero is N/A; date endpoints match snapshot builder including full prior month',()=>{
 const d=sample();d.rankings.YTD.customers=[{name:'Returns',sales:-50.25,prior_sales:-100.5},{name:'Zero',sales:10,prior_sales:0}];
 const r=model.build(d);assert.equal(r.rows[0].percent_change,.5);assert.equal(r.rows[1].percent_change,null);
 assert.deepEqual(r.dates,{current_start:'2026-01-01',current_end:'2026-09-29',prior_start:'2025-01-01',prior_end:'2025-09-29'});
 d.rankings['1M']=d.rankings.YTD;d.comparisons['1M']=d.comparisons.YTD;assert.equal(model.build(d,{period:'1M'}).dates.current_start,'2026-08-31');
 d.rankings.FULL=d.rankings.YTD;d.comparisons.FULL=d.comparisons.YTD;assert.deepEqual(model.build(d,{period:'FULL'}).dates,{current_start:'2024-01-01',current_end:'2026-09-29',prior_start:'2021-01-01',prior_end:'2023-09-29'});
 d.months={'2026-09':{rankings:d.rankings.YTD,...d.comparisons.YTD}};
 assert.deepEqual(model.build(d,{period:'MONTH',month:'2026-09'}).dates,{current_start:'2026-09-01',current_end:'2026-09-29',prior_start:'2025-09-01',prior_end:'2025-09-30'});
 d.as_of='2024-02-29';assert.equal(model.build(d).dates.prior_end,'2023-02-28');
 assert.equal(r.source_sha256,'source-hash');assert.equal(r.data_asof,'2026-09-29');assert.equal(r.refresh_heartbeat,'2026-09-29T18:00:00Z');
});
test('real XLSX round trip: numbers, percent/date styles, safe literal text and snapshot metadata',()=>{
 assert.equal(typeof model.workbook,'function','workbook export required');
 const XLSX=require('../vendor/xlsx-0.20.3.min.js'),d=sample();
 d.rankings.YTD.customers[0].name='=HYPERLINK("https://invalid","x")';
 const r=model.build(d,{search:'='}),wb=model.workbook(r,XLSX,'2026-09-29T19:00:00Z');
 const decoded=XLSX.read(XLSX.write(wb,{type:'buffer',bookType:'xlsx'}),{type:'buffer',cellDates:true,cellNF:true});
 assert.deepEqual(decoded.SheetNames,['Customer Comparison','Report Info']);const s=decoded.Sheets['Customer Comparison'];
 assert.equal(s.B2.t,'s');assert.equal(s.B2.v,d.rankings.YTD.customers[0].name);assert.equal(s.B2.f,undefined);
 assert.equal(s.C2.v,20.01);assert.equal(s.D2.v,123.45);assert.equal(s.E2.v,103.44);assert.equal(s.F2.v,r.rows[0].percent_change);assert.equal(s.F2.z,'0.0%;[Red]-0.0%');assert.match(s.C2.z,/0\.00/);
 const info=Object.fromEntries(XLSX.utils.sheet_to_json(decoded.Sheets['Report Info'],{header:1}).slice(1));
 assert.equal(info['Source snapshot SHA-256'],'source-hash');assert.equal(info['Search (case-insensitive substring)'],'=');assert.equal(info['Exported row count'],1);assert.equal(info['Cohort row count before search'],2);
 assert.equal(info['Current start'].toISOString().slice(0,10),'2026-01-01');assert.equal(info['Current end'].toISOString().slice(0,10),'2026-09-29');
 assert.equal(info['Refresh / publication heartbeat (UTC)'],'2026-09-29T18:00:00Z');
});
test('real snapshot: every selectable period/cohort/export matches source cents and details',()=>{
 const payload=process.env.SMI_TEST_PAYLOAD||require('node:path').join(__dirname,'../data/sales.json');
 const d=JSON.parse(fs.readFileSync(payload,'utf8')),XLSX=require('../vendor/xlsx-0.20.3.min.js');
 const scopes=[{period:'YTD'},{period:'1M'},{period:'FULL'},...Object.keys(d.months).filter(m=>m<=d.as_of.slice(0,7)).map(month=>({period:'MONTH',month}))];
 let count=0;
 for(const scope of scopes)for(const cohort of ['current','prior']){
   const r=model.build(d,{...scope,cohort}),selected=scope.period==='MONTH'?d.months[scope.month]:d.comparisons[scope.period];
   const source=cohort==='prior'?selected.customer_comparison:(scope.period==='MONTH'?selected.rankings:d.rankings[scope.period]).customers;
   const out=XLSX.read(XLSX.write(model.workbook(r,XLSX),{type:'buffer',bookType:'xlsx'}),{type:'buffer'});
   const rows=XLSX.utils.sheet_to_json(out.Sheets['Customer Comparison'],{header:1}).slice(1);
   assert.equal(rows.length,source.length);
   source.forEach((x,i)=>{assert.deepEqual(rows[i].slice(0,4),[i+1,x.name,x.prior_sales,cohort==='prior'?x.current_sales:x.sales]);assert.ok(d.customer_details[x.name]);assert.equal(Math.round(rows[i][4]*100),Math.round(rows[i][3]*100)-Math.round(rows[i][2]*100));});count++;
 }
 console.log(`Verified ${count} frozen customer period/cohort workbooks against source`);
});
module.exports={sample};
