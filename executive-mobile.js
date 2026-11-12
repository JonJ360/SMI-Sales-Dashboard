/* Executive mobile presentation only. Existing data, report and auth handlers remain owners. */
(() => {
  'use strict';
  const mq = matchMedia('(max-width:760px)'), nav = document.querySelector('.nav'), brand = document.querySelector('.brand'), controls = document.querySelector('.controls');
  const originalNav = [...nav.querySelectorAll('[data-view]')], reportControls = [...controls.children].filter(e => e.id !== 'refreshBtn');
  const refresh = document.getElementById('refreshBtn'), filter = document.querySelector('#overview > .report-filter');
  const anchors = new Map();
  function relocate(node, target) {
    if (!anchors.has(node)) { const anchor = document.createComment('executive restore'); node.before(anchor); anchors.set(node, anchor); }
    target.append(node);
  }
  const glyphs = {
    overview:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    salespeople:'<circle cx="9" cy="7" r="4"/><path d="M2 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2m3-17a4 4 0 0 1 0 8m3 9v-2a4 4 0 0 0-3-4"/>',
    branches:'<path d="M3 21h18M5 21V7l7-4 7 4v14M9 10h1m4 0h1m-6 4h1m4 0h1m-6 7v-4h6v4"/>',
    customers:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 5V3h8v2M3 11h18m-11 0v3h4v-3"/>',
    reports:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Zm0 0v6h6M8 13h8m-8 4h6"/>',
    more:'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>'
  };
  function icon(name) { return '<svg class="executive-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+glyphs[name]+'</svg>'; }
  function button(id, label, glyph) { const b = document.createElement('button'); b.type='button'; b.id=id; b.className='executive-control'; b.innerHTML=icon(glyph)+'<span>'+label+'</span>'; return b; }
  function dialog(id, title) {
    const d=document.createElement('dialog');d.id=id;d.className='executive-dialog';d.setAttribute('aria-label',title);
    const head=document.createElement('div');head.className='executive-dialog-head';const h=document.createElement('h2');h.textContent=title;
    const close=document.createElement('button');close.type='button';close.className='executive-close';close.textContent='×';close.setAttribute('aria-label','Close '+title);close.onclick=()=>d.close();head.append(h,close);d.append(head);
    d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}});
    document.body.append(d);return d;
  }
  const reports=button('executiveReports','Reports','reports'), more=button('executiveMore','More','more');
  const reportsDialog=dialog('executiveReportsDialog','Reports'), moreDialog=dialog('executiveMoreDialog','More reports');
  for(const [b,i] of originalNav.map((b,i)=>[b,i])) { if(i<4)b.insertAdjacentHTML('afterbegin',icon(b.dataset.view)); b.addEventListener('click',()=>{if(moreDialog.open)moreDialog.close();more.classList.toggle('active',originalNav.slice(4).includes(b));}); }
  reports.setAttribute('aria-haspopup','dialog');more.setAttribute('aria-haspopup','dialog');
  reports.onclick=()=>reportsDialog.showModal();more.onclick=()=>moreDialog.showModal();
  controls.append(reports);nav.append(more);refresh.setAttribute('aria-label','Refresh sales data');
  function apply() {
    if(mq.matches) {
      relocate(refresh,brand);relocate(filter,controls);controls.append(reports);
      reportControls.forEach(e=>relocate(e,reportsDialog));originalNav.slice(4).forEach(e=>relocate(e,moreDialog));
    } else {
      if(reportsDialog.open)reportsDialog.close();if(moreDialog.open)moreDialog.close();
      for(const [node,anchor] of anchors)anchor.after(node);
    }
  }
  mq.addEventListener('change',apply);apply();
})();
