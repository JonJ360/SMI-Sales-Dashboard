"""Local frozen-data real Refresh proof; no production RPC/auth/backend changes."""
import argparse, hashlib, json, threading
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
def run(snapshot, output):
    output.mkdir(parents=True,exist_ok=True)
    raw=snapshot.read_bytes();release=threading.Event();release.set()
    control={'mode':'ok','requests':0}
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            if self.path.split('?')[0]!='/data/sales.json': return super().do_GET()
            control['requests']+=1
            self.send_response(500 if control['mode']=='http-error' else 200)
            self.send_header('Content-Type','application/json');self.end_headers();self.wfile.flush()
            release.wait(20)
            self.wfile.write(b'{' if control['mode']=='bad-json' else raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    result={'fixture_sha256':hashlib.sha256(raw).hexdigest(),'checks':[],'bounds':[],'screenshots':[]}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000})
            page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle')
            page.wait_for_function('!!state.data && !refreshBtn.disabled')
            page.evaluate('window.fullPayloadBefore=JSON.stringify(state.data)');print('Initial real fixture loaded',flush=True)
            page.evaluate("""() => {window.progressEvents=[];for(const key of ['start','stage','finish','fail']){const original=SalesRefreshProgress[key];SalesRefreshProgress[key]=(...args)=>{original(...args);progressEvents.push({key,args,value:refreshProgress.getAttribute('aria-valuenow'),rendered:!!state.data&&!document.querySelector('.content>.error')});};}}""")
            release.clear();before=control['requests']
            page.evaluate('void load()')
            page.wait_for_function("refreshProgress.getAttribute('aria-valuenow')==='25'")
            assert control['requests']==before+1
            for width in [320,390,1024,1440]:
                page.set_viewport_size({'width':width,'height':1000})
                assert page.locator('#refreshProgress').is_visible()
                assert page.locator('.refresh-progress-caption').inner_text()=='LOADING SALES DATA\n25%'
                bounds=page.locator('#refreshProgress').bounding_box()
                assert bounds['x']==0 and bounds['width']==width and bounds['height']==64
                style=page.locator('.refresh-progress-line').evaluate('(e)=>({animation:getComputedStyle(e).animationName,background:getComputedStyle(e).backgroundImage,width:e.getBoundingClientRect().width,track:e.parentElement.clientWidth})')
                assert style['animation']=='none' and 'repeating-linear-gradient' in style['background']
                assert .20<style['width']/style['track']<.27
                result['bounds'].append({'viewport':width,'component':bounds,'style':style})
                shot=output/f'loading-25-percent-{width}.png';page.screenshot(path=str(shot));result['screenshots'].append(str(shot))
            page.emulate_media(reduced_motion='reduce')
            assert page.locator('.refresh-progress-line').evaluate('e=>getComputedStyle(e).animationName')=='none'
            page.emulate_media(media='print');assert not page.locator('#refreshProgress').is_visible()
            page.emulate_media(media='screen')
            page.wait_for_timeout(400)
            assert page.locator('#refreshProgress').get_attribute('aria-valuenow')=='25'
            release.set();page.wait_for_function('!refreshBtn.disabled')
            events=page.evaluate('progressEvents');result['completed_phases']=events
            assert [x['value'] for x in events if x['key']=='stage']==['25','75','90']
            assert events[-1]['key']=='finish' and events[-1]['value']=='100' and events[-1]['rendered']
            page.wait_for_function('refreshProgress.hidden')
            assert page.evaluate('JSON.stringify(state.data)===fullPayloadBefore')
            with page.expect_download() as download:
                page.evaluate("() => {const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(state.data)],{type:'application/json'}));a.download='after-real-refresh-full-payload.json';a.click();}")
            download.value.save_as(output/'after-real-refresh-full-payload.json')
            print('Four screenshots and exact full-payload refresh equality passed',flush=True)
            result['checks']+=['real local GET once','25/75/90 real completed phases;100 after render','no timer advancement','four viewport bounds and pixel skin','reduced motion static','hidden in print','full payload exact equality after actual Refresh']
            for mode in ['http-error','bad-json']:
                control['mode']=mode;page.evaluate('progressEvents=[];void load()');page.wait_for_function('!refreshBtn.disabled')
                assert page.locator('.content>.error').first.is_visible()
                assert page.locator('#refreshProgress').is_hidden()
                assert not any(x['value']=='100' for x in page.evaluate('progressEvents'))
                result['checks'].append(mode+' never100')
            control['mode']='ok';page.evaluate('void load()');page.wait_for_function('!refreshBtn.disabled')
            assert page.locator('.content>.error').count()==0 and page.evaluate('JSON.stringify(state.data)===fullPayloadBefore')
            # Rapid restart cancels the prior successful completion's pending hide.
            release.clear();page.evaluate('void load()');page.wait_for_function("refreshProgress.getAttribute('aria-valuenow')==='25'")
            page.wait_for_timeout(450);assert page.locator('#refreshProgress').is_visible()
            release.set();page.wait_for_function('!refreshBtn.disabled');page.wait_for_function('refreshProgress.hidden')
            result['checks']+=['error recovery','rapid restart remains visible past previous hide deadline']
            browser.close()
        (output/'pixel-progress-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'checks':len(result['checks']),'screenshots':len(result['screenshots']),'result':str(output/'pixel-progress-results.json')}))
    finally:
        release.set();server.shutdown()
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();run(args.snapshot,args.output)
