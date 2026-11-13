const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const report=require('../monthly-report.js');
test('monthly report basename uses selected full month/year without dashes',()=>{
 const months=['January','February','March','April','May','June','July','August','September','October','November','December'];
 months.forEach((name,i)=>assert.equal(report.reportFilename(`2026-${String(i+1).padStart(2,'0')}`),`SMI Salesperson Report ${name} 2026`));
 assert.equal(report.reportFilename('2025-12'),'SMI Salesperson Report December 2025');
 const source=fs.readFileSync(require.resolve('../monthly-report.js'),'utf8');
 assert.ok(source.includes(".save(reportFilename(model.month)+'.pdf')"));
 assert.ok(source.includes('<title>${esc(reportFilename(m.month))}</title>'));
 assert.ok(source.includes('thead th{text-align:center!important;vertical-align:middle}'));
});
test('native table headers share horizontally and vertically centered wrapping',()=>{
 const source=fs.readFileSync(require.resolve('../monthly-report-pdf.js'),'utf8');
 assert.ok(source.includes('function tableHeader('));
 assert.ok(source.includes("align:'center',baseline:'middle',maxWidth:w-8"));
 assert.ok(source.includes('pdf.splitTextToSize(valueText,w-8)'));
 assert.ok(source.includes('tableHeader(c.textContent,xx,y,ws[j],h,'));
 assert.ok(source.includes('tableHeader(cell.textContent,xx,y,widths[j],h,z)'));
});
