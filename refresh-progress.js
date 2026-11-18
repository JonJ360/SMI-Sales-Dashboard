/* Stage milestones are completed loader phases, not a download/time estimate. */
(()=>{'use strict';
const button=document.getElementById('refreshBtn'),bar=document.createElement('div');
bar.id='refreshProgress';bar.hidden=true;bar.setAttribute('role','progressbar');bar.setAttribute('aria-label','Loading sales data');bar.setAttribute('aria-valuemin','0');bar.setAttribute('aria-valuemax','100');
const caption=document.createElement('div'),label=document.createElement('span'),percent=document.createElement('span'),track=document.createElement('div'),line=document.createElement('div');
caption.className='refresh-progress-caption';label.textContent='LOADING SALES DATA';percent.className='refresh-progress-percent';caption.append(label);caption.append(percent);track.className='refresh-progress-track';line.className='refresh-progress-line';track.append(line);bar.append(caption);bar.append(track);document.body.append(bar);
let active=false,timer,value=0,completed=false;
function paint(n,phase){value=n;line.style.width=n+'%';percent.textContent=n+'%';bar.setAttribute('aria-valuenow',String(n));bar.setAttribute('aria-valuetext',`Stage-based progress: ${n}% — ${phase}`);}
function start(){clearTimeout(timer);active=true;completed=false;bar.hidden=false;bar.className='loading';paint(0,'Request started');}
function stage(n){if(!active)return;const phases={25:'Response headers received',75:'Sales JSON and metadata parsed',90:'Report filters prepared'};if(phases[n]&&n>value)paint(n,phases[n]);}
function fail(){clearTimeout(timer);active=false;completed=false;bar.hidden=true;bar.className='';bar.removeAttribute('aria-valuenow');}
function finish(){if(!active||document.querySelector('.content > .error')||document.getElementById('lock').classList.contains('show')){fail();return;}completed=true;active=false;bar.className='complete';paint(100,'Report rendered');timer=setTimeout(()=>{if(!active)bar.hidden=true;},350);}
function sync(){if(button.disabled){if(!active&&!completed)start();}else if(active)fail();}
globalThis.SalesRefreshProgress={start,stage,finish,fail};
new MutationObserver(sync).observe(button,{attributes:true,attributeFilter:['disabled']});sync();
})();
