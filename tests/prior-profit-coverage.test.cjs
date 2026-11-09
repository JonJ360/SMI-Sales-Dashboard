const {test}=require('node:test');const assert=require('node:assert/strict');const E=require('../monthly-report.js');
function fixture(){return {as_of:'2026-02-28',months:Object.fromEntries(['01','02'].map(mm=>[`2026-${mm}`,{current:{sales:100,profit:20},rankings:{salespeople:[{name:'A',sales:100,profit:20}]},prior:{sales:80,profit:10},prior_rankings:{salespeople:[{name:'A',sales:80,profit:10}]}}]))};}
test('fallback prior profit requires independent raw coverage while sales remains available',()=>{
 for(const kind of ['aggregate missing','aggregate null','individual missing','individual null','YTD month']){
 const s=fixture(),month=kind==='YTD month'?'01':'02';
 if(kind.startsWith('aggregate')||kind==='YTD month'){delete s.months[`2026-${month}`].prior.profit;if(kind==='aggregate null')s.months['2026-02'].prior.profit=null;}
 else {delete s.months['2026-02'].prior_rankings.salespeople[0].profit;if(kind==='individual null')s.months['2026-02'].prior_rankings.salespeople[0].profit=null;}
 const m=E.build(s,'2026-02',{retained:['A']});
 for(const row of kind==='YTD month'?m.comparison:[...m.comparison,...m.monthlyComparison]){assert.equal(row.prior_profit,null,kind);assert.equal(row.change_profit,null,kind);assert.equal(row.profit_pct,'Unavailable',kind);assert.notEqual(row.prior_sales,null,kind);assert.notEqual(row.change_sales,null,kind);}
 if(kind==='YTD month')assert.equal(m.monthlyComparison[0].prior_profit,10);
 }
 const s=fixture();for(const m of Object.values(s.months)){m.prior.profit=0;m.prior_rankings.salespeople[0].profit=0;}const m=E.build(s,'2026-02',{retained:['A']});assert.equal(m.monthlyComparison[0].prior_profit,0);assert.equal(m.monthlyComparison[0].profit_pct,'New');assert.equal(m.comparison[0].prior_profit,0);
});
