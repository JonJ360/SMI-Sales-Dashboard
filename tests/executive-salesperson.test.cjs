const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const root=path.join(__dirname,'..');
test('Executive Profile is scoped, accessible and keeps the existing model and export renderer',()=>{
 const js=fs.readFileSync(path.join(root,'executive-salesperson.js'),'utf8');const css=fs.readFileSync(path.join(root,'executive-salesperson.css'),'utf8');const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
 assert.match(html,/executive-salesperson\.js\?v=1\.42/);assert.match(html,/executive-salesperson\.css\?v=1\.42/);
 for(const token of ['tablist','tabpanel','aria-selected','ArrowRight','ArrowLeft','Home','End','Escape','Accounting notes','Monthly and YTD history'])assert.ok(js.includes(token),token);
 assert.match(css,/#salespersonDrawer/);assert.ok(!js.includes('SalespersonComparison.build'));assert.ok(!js.includes('innerHTML = name'));
 const exp=fs.readFileSync(path.join(root,'report-export.js'),'utf8');assert.ok(exp.includes('salespersonComparisonHTML(captured.model)'));assert.ok(exp.includes('completeComparison'));
});
