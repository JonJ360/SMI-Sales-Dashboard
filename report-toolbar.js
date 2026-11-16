/* Presentation only: move original controls, retaining their identity and handlers. */
(() => {
  'use strict';
  const controls=document.querySelector('.controls');
  const button=document.createElement('button');
  button.id='reportMenuButton';button.type='button';button.textContent='☰';
  button.setAttribute('aria-label','Report controls');button.setAttribute('aria-expanded','false');button.setAttribute('aria-controls','reportMenuPanel');button.setAttribute('aria-haspopup','dialog');
  const panel=document.createElement('div');panel.id='reportMenuPanel';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-label','Report controls');
  const heading=document.createElement('div');heading.className='report-menu-heading';heading.textContent='Reports';panel.append(heading);
  // Move, never clone: original month selection, disabled state and event listeners survive.
  [...controls.children].forEach(node=>panel.append(node));
  controls.append(button,panel);
  function close(returnFocus=false){panel.hidden=true;button.setAttribute('aria-expanded','false');if(returnFocus)button.focus();}
  button.addEventListener('click',()=>{if(!panel.hidden){close();return;}panel.hidden=false;button.setAttribute('aria-expanded','true');panel.querySelector('select:not(:disabled),button:not(:disabled)')?.focus();});
  document.addEventListener('pointerdown',e=>{if(!panel.hidden&&!panel.contains(e.target)&&!button.contains(e.target))close();});
  document.addEventListener('keydown',e=>{
    if(panel.hidden)return;
    if(e.key==='Escape'){e.preventDefault();close(true);return;}
    if(e.key==='Tab'){
      const items=[button,...panel.querySelectorAll('button:not(:disabled),select:not(:disabled)')].filter(e=>e.getClientRects().length);
      const index=items.indexOf(document.activeElement);
      if(e.shiftKey&&index===0){e.preventDefault();items.at(-1).focus();}
      else if(!e.shiftKey&&index===items.length-1){e.preventDefault();button.focus();}
    }
  });
  window.addEventListener('resize',()=>close());
  // Currency formatting is presentation-only; source values and calculations are untouched.
  const currency=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2});
  let queued=false;
  function fit(){
    queued=false;
    if(state.data){const totals=selection('overview').totals;for(const [id,value] of Object.entries({salesKpi:totals.sales,profitKpi:totals.profit,returnsKpi:totals.returns,orderKpi:state.data.open_orders.amount})){const e=document.getElementById(id),text=currency.format(value||0);if(e.textContent!==text)e.textContent=text;}}
    document.querySelectorAll('#overview .kpi > *').forEach(e=>{
      if(!e.getClientRects().length)return;
      e.style.removeProperty('font-size');
      const max=parseFloat(getComputedStyle(e).fontSize),range=document.createRange();range.selectNodeContents(e);
      const available=e.clientWidth;
      let size=max;
      while(range.getBoundingClientRect().width>available+.25&&size>8){size-=.5;e.style.fontSize=size+'px';}
    });
  }
  function schedule(){if(!queued){queued=true;requestAnimationFrame(fit);}}
  new MutationObserver(schedule).observe(document.getElementById('overview'),{subtree:true,childList:true,characterData:true});
  new ResizeObserver(schedule).observe(document.querySelector('.content'));
  window.addEventListener('resize',schedule);document.fonts.ready.then(schedule);schedule();
})();
