/* Local document rendering only: no fetch, accounting recalculation or data publication. */
(function(root){
'use strict';
const PRINT_CSS = `
@page { size: A4 landscape; margin: 12mm; }
html,body{background:#fff!important;color:#222A33;margin:0;min-height:0}
body{padding:20px;font-size:12px}
.report-toolbar{padding:12px;background:#E8F0FD;border:1px solid #B9D0F2;margin-bottom:16px}
.report-toolbar button{margin-right:12px;padding:8px 14px;cursor:pointer}
.report-heading{border-bottom:2px solid #233B61;margin-bottom:14px;padding-bottom:12px}
.report-heading h1{font-size:22px;margin:0 0 8px}
.report-meta{font-size:10px;line-height:1.6;overflow-wrap:anywhere}
.report-scope{font-size:11px;line-height:1.5;margin-top:8px}
.view{display:block!important}.report-detail{break-before:page;margin-top:18px}
.drawer{position:static!important;display:block!important;width:100%!important;height:auto!important;padding:0;box-shadow:none;background:white;overflow:visible!important}
.grid,.split,.drawer-grid,.drawer-pies,#branches>.grid{display:block!important}
.panel{margin:12px 0;overflow:visible!important;box-shadow:none;break-inside:auto}
.panel-head{break-after:avoid}.panel-body{padding:10px}
.kpis,.weekly-kpis,.margin-kpis,.drawer-kpis{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important}
.daily-kpis{grid-template-columns:repeat(2,minmax(0,1fr))!important}
.kpi{min-width:0;break-inside:avoid}.k-value{font-size:21px!important;overflow-wrap:anywhere}
.table-wrap,.order-line-detail{overflow:visible!important;max-height:none!important;height:auto!important}
table{width:100%!important;min-width:0!important;table-layout:fixed;font-size:10px}
thead{display:table-header-group}tr{break-inside:avoid}th,td{position:static!important;padding:7px 5px!important;white-space:normal!important;overflow-wrap:anywhere}
.chart-wrap,.chart-sm,.drawer-chart,.drawer-pie{height:auto!important;break-inside:avoid}
.report-chart{display:block;max-width:100%;max-height:78mm;width:auto;height:auto;margin:auto;object-fit:contain;break-inside:avoid}
.report-control{display:inline-block;font-size:11px;padding:4px 6px;white-space:normal;overflow-wrap:anywhere}
.table-tools,.report-filter,.margin-controls{flex-wrap:wrap!important;break-inside:avoid}
[hidden]{display:none!important}.bar{max-width:100%}
@media print{body{padding:0}.report-toolbar{display:none!important}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}.report-detail{margin-top:0}}
`;
function visible(node){
  const style=root.getComputedStyle(node);
  return !node.hidden && style.display!=='none' && style.visibility!=='hidden';
}
// Walk source and clone together; off-screen scroll content is included, hidden tabs/details are not.
function copyVisible(node,doc){
  if(node.nodeType===3)return doc.createTextNode(node.textContent);
  if(node.nodeType!==1||(!visible(node)&&!node.matches('.person-comparison thead'))||node.matches('script,style,.drawer-close,[data-report-export],#customerExport'))return null;
  if(node.tagName==='CANVAS'){
    const chart=root.Chart?.getChart(node);
    if(chart){chart.stop();chart.update('none')}
    const img=doc.createElement('img');img.className='report-chart';img.alt=node.id+' chart';img.src=node.toDataURL('image/png');
    return img;
  }
  if(node.matches('input,select,textarea')){
    const span=doc.createElement('span');span.className='report-control';
    const value=node.tagName==='SELECT'?node.selectedOptions[0]?.textContent:node.value;
    const label=node.getAttribute('aria-label')||node.getAttribute('placeholder')||'';
    span.textContent=(label?label+': ':'')+(value||'(none)');return span;
  }
  const clone=doc.createElement(node.tagName==='BUTTON'?'div':node.tagName.toLowerCase());
  for(const attr of node.attributes){
    if(['class','id','colspan','rowspan','open'].includes(attr.name))clone.setAttribute(attr.name,attr.value);
  }
  // Preserve intentional spacing but not fixed widths, clipping, positioning or event handlers.
  if(node.style.marginTop)clone.style.marginTop=node.style.marginTop;
  if(node.matches('.person-comparison td[data-label]'))clone.setAttribute('data-label',node.getAttribute('data-label'));
  if(node.classList.contains('pc-bar'))clone.style.width=node.style.width;
  const children=node.tagName==='DETAILS'&&!node.open?[node.querySelector('summary')]:node.childNodes;
  for(const child of children){if(child){const copied=copyVisible(child,doc);if(copied)clone.append(copied)}}
  return clone;
}
function appendText(doc,parent,tag,text,className){
  const el=doc.createElement(tag);el.textContent=text;if(className)el.className=className;parent.append(el);return el;
}
function createDocument(target,context){
  const doc=target.document;
  doc.open();doc.write('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body></body></html>');doc.close();
  doc.title='SMI - '+context.title+' - '+context.asOf;
  const style=doc.createElement('style');style.textContent=[...document.querySelectorAll('head style')].map(x=>x.textContent).join('\n')+'\n'+PRINT_CSS;doc.head.append(style);
  const toolbar=appendText(doc,doc.body,'div','','report-toolbar');
  const print=appendText(doc,toolbar,'button','Print / Save as PDF');print.type='button';print.disabled=true;
  print.onclick=()=>target.print();
  appendText(doc,toolbar,'span','Choose “Save as PDF” in the print dialog. Landscape recommended. Close this tab to return; the dashboard is unchanged.');
  const header=appendText(doc,doc.body,'header','','report-heading');
  appendText(doc,header,'h1','SMI Sales Intelligence — '+context.title);
  appendText(doc,header,'div',context.period,'report-scope');
  if(context.dates){const d=context.dates;appendText(doc,header,'div',`Selected document dates: ${d.current_start} through ${d.current_end} | Comparison: ${d.prior_start} through ${d.prior_end}`,'report-meta')}
  for(const line of [
    'Data as of: '+context.asOf+' | Export captured (UTC): '+context.capturedAt,
    'Source snapshot SHA-256: '+context.sha,
    'Refresh / publication heartbeat (not source-data timestamp): '+context.heartbeat,
    'Application: '+context.version
  ])appendText(doc,header,'div',line,'report-meta');
  appendText(doc,header,'div',context.scope||'Scope: active report and any open detail below; includes the currently rendered rows, search, page and expanded items only. Hidden tabs, other pages and collapsed item detail are not added. Charts retain their displayed date scope; history/YTD charts may differ from the selected period. Values retain dashboard rounding and existing source-cost policy, not GL net income.','report-scope');
  for(const source of context.sources){const copied=copyVisible(source,doc);if(copied)doc.body.append(copied)}
  for(const source of context.drawers){
    const section=appendText(doc,doc.body,'section','','report-detail');
    appendText(doc,section,'h2','Open detail');section.append(copyVisible(source,doc));
  }
  Promise.all([...doc.images].map(img=>img.decode())).then(()=>doc.fonts.ready).then(()=>{
    print.disabled=false;doc.documentElement.dataset.reportReady='true';
  }).catch(()=>appendText(doc,toolbar,'p','A chart could not be prepared. Close this preview and try again; do not print an incomplete report.'));
  return doc;
}
function exportView(){
  if(document.querySelector('#salespersonDrawer.show'))return exportSalesperson();
  if(!state.data||document.getElementById('refreshBtn').disabled||document.querySelector('#lock.show')){
    root.alert('Wait for the report to finish loading before exporting.');return;
  }
  const active=document.querySelector('.view.active');
  const drawers=[...document.querySelectorAll('.drawer-shade.show .drawer')];
  if(drawers.some(x=>x.dataset.reportSha!==String(state.data.sha256||''))){
    root.alert('The source snapshot changed. Close and reopen the detail before exporting.');return;
  }
  // Capture synchronously before image decoding: later filter/refresh changes cannot mix this document.
  const context={title:document.getElementById('viewTitle').textContent,period:document.getElementById('periodLabel').textContent,
    asOf:state.data.as_of||'Unavailable',sha:state.data.sha256||'Unavailable',heartbeat:state.data.refreshed_at||'Unavailable',
    capturedAt:new Date().toISOString(),version:document.querySelector('.version').textContent,
    dates:PERIOD_VIEWS.includes(state.view)?CustomerReport.build(state.data,filterForView(state.view)).dates:null,
    sources:[...document.querySelectorAll('.content>.error,.notice.show'),active],drawers};
  const target=root.open('about:blank','_blank');
  if(!target){root.alert('Allow pop-ups for this dashboard to open the PDF preview.');return}
  try{createDocument(target,context)}catch(error){target.close();root.alert('The report could not be prepared. Please try again.');}
}
function exportSalesperson(){
  const captured=root.salespersonReportCapture;
  if(!state.data||document.getElementById('refreshBtn').disabled||document.querySelector('#lock.show')){
    root.alert('Wait for the report to finish loading before exporting.');return;
  }
  if(!captured||captured.sha!==String(state.data.sha256||'')||!document.querySelector('#salespersonDrawer.show')){
    root.alert('The source snapshot changed. Close and reopen the detail before exporting.');return;
  }
  // Deliberate allowlist: never capture the active company view or the entire drawer.
  const context={title:captured.model.name+' — Individual Sales Report',period:'Selected period compared with the same elapsed period one year earlier',
    asOf:captured.asOf,sha:captured.sha||'Unavailable',heartbeat:captured.heartbeat||'Unavailable',capturedAt:new Date().toISOString(),
    version:document.querySelector('.version').textContent,dates:captured.model.dates,
    scope:'Scope: '+captured.model.name+' only. Complete selected-period category comparison, not a company dashboard. Net sales include returns; categories are gross invoice-line sales before returns.',
    sources:[document.getElementById('salespersonComparison')],drawers:[]};
  const target=root.open('about:blank','_blank');
  if(!target){root.alert('Allow pop-ups for this dashboard to open the PDF preview.');return;}
  try{createDocument(target,context)}catch(error){target.close();root.alert('The report could not be prepared. Please try again.');}
}
function install(){
  const main=document.createElement('button');main.id='exportView';main.className='refresh';main.textContent='Export this view';main.dataset.reportExport='';main.title='Open a printable preview, then save as PDF';main.onclick=exportView;
  document.querySelector('.controls').prepend(main);
  for(const head of document.querySelectorAll('.drawer-head')){
    const button=main.cloneNode(true);button.removeAttribute('id');button.onclick=exportView;
    if(head.closest('#salespersonDrawer')){button.textContent='Export salesperson report';button.onclick=exportSalesperson;}
    head.insertBefore(button,head.lastElementChild);
  }
}
root.ReportExport={copyVisible,createDocument,exportView,exportSalesperson};
install();
})(window);
