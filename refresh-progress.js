/* Estimated overall progress: bounded waiting, anchored bytes, ready only after paint. */
(()=>{'use strict';
const button=document.getElementById('refreshBtn'),bar=document.createElement('div');
bar.id='refreshProgress';bar.hidden=true;bar.setAttribute('role','progressbar');bar.setAttribute('aria-label','Loading sales data');bar.setAttribute('aria-valuemin','0');bar.setAttribute('aria-valuemax','100');
const caption=document.createElement('div'),label=document.createElement('span'),percent=document.createElement('span'),track=document.createElement('div'),line=document.createElement('div');
caption.className='refresh-progress-caption';percent.className='refresh-progress-percent';caption.append(label);caption.append(percent);track.className='refresh-progress-track';line.className='refresh-progress-line';track.append(line);bar.append(caption);bar.append(track);document.body.append(bar);
let active=false,timer,waitTimer,completed=false,generation=0,shown=0;
const frame=()=>new Promise(resolve=>typeof requestAnimationFrame==='function'?requestAnimationFrame(resolve):setTimeout(resolve,0));
async function painted(){await frame();await frame();}
function display(phase,detail='',n=null){label.textContent=phase;percent.textContent=detail.replace(/\s+\(\d+ bytes\)$/,'');line.style.width=n===null?'0%':n+'%';bar.className=n===null?'loading indeterminate':'loading';if(n===null)bar.removeAttribute('aria-valuenow');else bar.setAttribute('aria-valuenow',String(n));bar.setAttribute('aria-valuetext',phase+(detail?' — '+detail:''));}
function estimate(n,detail=''){shown=Math.max(shown,Math.min(95,Math.floor(n)));display('Loading · estimated',detail?`${shown}% · ${detail}`:`${shown}%`,shown);}
function stopWaiting(){clearTimeout(waitTimer);waitTimer=null;}
function start(){clearTimeout(timer);stopWaiting();const run=++generation,began=performance.now();active=true;completed=false;shown=0;bar.hidden=false;estimate(0);const tick=()=>{if(run!==generation||!active)return;const t=Math.min(1,(performance.now()-began)/8000);estimate(25*t);if(t<1)waitTimer=setTimeout(tick,Math.min(100,8000-(performance.now()-began)));};waitTimer=setTimeout(tick,100);}
function fail(){clearTimeout(timer);stopWaiting();generation++;active=false;completed=false;bar.hidden=true;bar.className='';bar.removeAttribute('aria-valuenow');}
async function building(run=generation){if(run!==generation||!active)return;stopWaiting();estimate(95);await painted();}
function totalBytes(res){const get=k=>res.headers?.get(k),positive=v=>/^\d+$/.test(v||'')&&Number.isSafeInteger(Number(v))&&Number(v)>0?Number(v):null;const custom=positive(get('x-uncompressed-content-length'));if(custom)return custom;const encoding=get('content-encoding');return encoding==='identity'||(!encoding&&['basic','default'].includes(res.type))?positive(get('content-length')):null;}
async function readJson(res){const run=generation,anchor=shown;stopWaiting();if(!res.body?.getReader){const data=await res.json();if(run===generation)await building(run);return data;}const reader=res.body.getReader(),decoder=new TextDecoder('utf-8'),parts=[];let received=0,total=totalBytes(res);const report=()=>{if(run!==generation)return;if(total&&received>total)total=null;const n=total?anchor+(95-anchor)*received/total:shown;estimate(n,total?'':`${(received/1000000).toFixed(2)} MB received (${received} bytes)`);};report();try{for(;;){const {done,value}=await reader.read();if(done)break;received+=value.byteLength;parts.push(decoder.decode(value,{stream:true}));report();}parts.push(decoder.decode());}finally{reader.releaseLock?.();}if(run===generation)await building(run);return JSON.parse(parts.join(''));}
async function finish(){const run=generation;stopWaiting();await painted();if(run!==generation)return;if(!active||document.querySelector('.content > .error')||document.getElementById('lock').classList.contains('show')){fail();return;}completed=true;active=false;display('Dashboard ready','100%',100);bar.className='complete';timer=setTimeout(()=>{if(run===generation&&!active)bar.hidden=true;},350);}
function sync(){if(button.disabled){if(!active&&!completed)start();}else if(active)fail();}
globalThis.SalesRefreshProgress={start,readJson,building,finish,fail};
new MutationObserver(sync).observe(button,{attributes:true,attributeFilter:['disabled']});sync();
})();
