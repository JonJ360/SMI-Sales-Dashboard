const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
test('PDF and HTML print use a blue-led palette, not green primary colors',()=>{
 const root=path.resolve(__dirname,'..');const html=fs.readFileSync(path.join(root,'monthly-report.js'),'utf8');const pdf=fs.readFileSync(path.join(root,'monthly-report-pdf.js'),'utf8');
 assert.match(html,/background:#DCEAF7/);assert.match(html,/background:#F1F6FC/);assert.match(pdf,/'#F1F6FC':'#DCEAF7'/);
 for(const source of [html,pdf]){assert.match(source,/'#568AC4'/);assert.doesNotMatch(source,/#76B65B|#DCEBD5|#DBEBD5|#F0F5ED/);}
 assert.match(pdf,/\+' blue'/);assert.doesNotMatch(pdf,/\+' green'/);
});
