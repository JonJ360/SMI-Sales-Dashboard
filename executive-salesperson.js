/* Approved Executive Profile: decorate existing nodes; never recompute business values. */
(function(){
'use strict';
const shade=document.getElementById('salespersonDrawer'),drawer=shade.querySelector('.drawer');
let returnFocus=null;
const tabs=['Overview','Customers','Invoices'];
const nav=document.createElement('div');nav.className='ep-tabs';nav.setAttribute('role','tablist');nav.setAttribute('aria-label','Salesperson detail');
tabs.forEach((label,i)=>{const b=document.createElement('button');b.type='button';b.id='ep-tab-'+i;b.textContent=label;b.setAttribute('role','tab');b.setAttribute('aria-controls','ep-panel-'+i);b.onclick=()=>select(i,true);nav.append(b)});
drawer.querySelector('.drawer-kpis').after(nav);
function select(index,focus=false){
 drawer.dataset.executiveTab=String(index);
 [...nav.children].forEach((b,i)=>{b.setAttribute('aria-selected',String(i===index));b.tabIndex=i===index?0:-1});
 drawer.querySelectorAll('[data-ep-panel]').forEach(p=>{p.hidden=Number(p.dataset.epPanel)!==index});
 if(focus)nav.children[index].focus();
}
nav.onkeydown=e=>{const i=[...nav.children].indexOf(document.activeElement);let next=null;if(e.key==='ArrowRight')next=(i+1)%3;if(e.key==='ArrowLeft')next=(i+2)%3;if(e.key==='Home')next=0;if(e.key==='End')next=2;if(next!==null){e.preventDefault();select(next,true)}};
function panel(node,index){node.dataset.epPanel=String(index);node.id=node.id||'ep-panel-'+index;node.setAttribute('role','tabpanel');node.setAttribute('aria-labelledby','ep-tab-'+index);return node}
function disclosure(title,className){const d=document.createElement('details');d.className=className;const s=document.createElement('summary');s.textContent=title;d.append(s);return d}
const history=disclosure('Monthly and YTD history','ep-history');panel(history,0);history.id='ep-history';
[drawer.querySelector('.drawer-grid'),drawer.querySelector('.drawer-pies')].filter(Boolean).forEach(n=>history.append(n));drawer.append(history);
history.addEventListener('toggle',()=>{if(history.open)requestAnimationFrame(()=>Object.values(state.charts).forEach(c=>c.resize()))});
const invoices=drawer.querySelector('#invoiceDrilldown');panel(invoices,2);invoices.setAttribute('aria-labelledby','ep-tab-2');
function decorate(){
 const comparison=document.getElementById('salespersonComparison');if(!comparison)return;
 const body=comparison.querySelector('.panel-body'),overview=panel(document.createElement('section'),0),customers=panel(document.createElement('section'),1);
 overview.id='ep-panel-0';customers.id='ep-panel-1';invoices.id='invoiceDrilldown';nav.children[2].setAttribute('aria-controls','invoiceDrilldown');
 const children=[...body.children];let customer=false;
 for(const node of children){
  if(node.tagName==='H3'&&node.textContent.startsWith('Top 10 customers'))customer=true;
  if(node.classList.contains('pc-notes')){const notes=disclosure('Accounting notes and reconciliation','ep-notes');notes.append(node);overview.append(notes)}
  else (customer?customers:overview).append(node);
 }
 body.append(overview,customers);comparison.querySelector('.panel-title').textContent='Performance comparison';
 // Keep the original management policy wording accessible without adding duplicate calculations.
 let note=drawer.querySelector('.ep-profit-note');if(!note){note=document.createElement('div');note.className='ep-profit-note';note.textContent='Management contribution · not GL net income';document.getElementById('drawerProfit').after(note)}
 history.open=false;select(0);drawer.scrollTop=0;
}
const originalComparison=window.renderSalespersonComparison;
window.renderSalespersonComparison=function(...args){originalComparison(...args);decorate()};
const originalOpen=window.openSalesperson;
window.openSalesperson=function(...args){if(!shade.classList.contains('show'))returnFocus=document.activeElement;originalOpen(...args);if(shade.classList.contains('show')){document.body.classList.add('ep-detail-open');document.getElementById('drawerClose').focus()}};
const originalClose=window.closeSalesperson;
window.closeSalesperson=function(){const wasOpen=shade.classList.contains('show');originalClose();document.body.classList.remove('ep-detail-open');if(wasOpen&&returnFocus?.isConnected)returnFocus.focus()};
document.getElementById('drawerClose').onclick=()=>window.closeSalesperson();
shade.onclick=e=>{if(e.target===shade)window.closeSalesperson()};
document.addEventListener('keydown',e=>{
 if(!shade.classList.contains('show'))return;
 if(e.key==='Escape'){e.preventDefault();window.closeSalesperson();return}
 if(e.key!=='Tab')return;
 const focusable=[...drawer.querySelectorAll('button,a[href],input,select,textarea,summary,[tabindex]')].filter(n=>n.tabIndex>=0&&!n.disabled&&n.getClientRects().length);
 const first=focusable[0],last=focusable[focusable.length-1];
 if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}
},true);
})();
