"""Bounded localhost held-header/body/build proof. Synthetic; never live evidence."""
import argparse, json, threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
RAW=json.dumps({'name':'é','padding':'x'*64000},ensure_ascii=False).encode()
RAW+=b' '*(-len(RAW)%4)
def run(output):
    output.mkdir(parents=True,exist_ok=True)
    headers=threading.Event();gates=[threading.Event() for _ in range(4)]
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_): pass
        def do_GET(self):
            self.send_response(200);self.end_headers();self.wfile.write(b'<button id="refreshBtn">Refresh</button><div id="lock"></div><main class="content">Local estimated overall progress proof</main>')
        def do_POST(self):
            requests.append({'path':self.path,'accept':self.headers.get('Accept')})
            headers.wait(20)
            self.send_response(200);self.send_header('Content-Type','application/json')
            if self.path!='/unknown':self.send_header('X-Uncompressed-Content-Length',str(len(RAW)))
            self.end_headers();self.wfile.flush()
            for i,gate in enumerate(gates):
                gate.wait(20);self.wfile.write(RAW[i*len(RAW)//4:(i+1)*len(RAW)//4]);self.wfile.flush()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    result={'synthetic_only':True,'contract':'estimated overall, not literal byte percentage','runs':[],'screenshots':[]}
    snapshot="""() => {const b=refreshProgress,t=b.querySelector('.refresh-progress-track'),f=b.querySelector('.refresh-progress-line'),c=b.querySelector('.refresh-progress-caption'),label=c.firstElementChild,detail=c.lastElementChild;return {n:Number(b.getAttribute('aria-valuenow')),hidden:b.hidden,text:c.innerText,fill:f.getBoundingClientRect().width,track:t.clientWidth-6,animation:getComputedStyle(f).animationName,transition:getComputedStyle(f).transitionDuration,captionFits:label.getBoundingClientRect().right<=detail.getBoundingClientRect().left,overflow:document.documentElement.scrollWidth>innerWidth}}"""
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':390,'height':700})
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.add_style_tag(content=(ROOT/'report-toolbar.css').read_text())
            page.add_script_tag(content=(ROOT/'refresh-progress.js').read_text())
            for width,delay in [(320,450),(390,4700),(1024,450)]:
                page.set_viewport_size({'width':width,'height':700})
                headers.clear()
                for gate in gates:gate.clear()
                page.evaluate("""() => {SalesRefreshProgress.start();window.pending=fetch('/raw',{method:'POST',headers:{Accept:'application/octet-stream'},body:'{}'}).then(r=>SalesRefreshProgress.readJson(r));} """)
                a=page.evaluate(snapshot);page.wait_for_timeout(delay);b=page.evaluate(snapshot)
                assert 0<=a['n']<b['n']<=15,(a,b)
                if delay>4500:assert b['n']==15
                shot=output/f'waiting-{width}.png';page.screenshot(path=str(shot));result['screenshots'].append(str(shot))
                headers.set();page.wait_for_timeout(150);anchor=page.evaluate(snapshot)['n']
                values=[b['n'],anchor]
                for i in range(3):
                    gates[i].set();page.wait_for_function('(prior)=>Number(refreshProgress.getAttribute("aria-valuenow"))>prior',arg=values[-1])
                    s=page.evaluate(snapshot);values.append(s['n'])
                    assert s['n']==int(anchor+(95-anchor)*(i+1)/4),s
                    assert abs(s['fill']/s['track']*100-s['n'])<.1,s
                    assert s['captionFits'] and not s['overflow'] and not s['hidden'],s
                    assert 'estimated' in s['text'] and s['animation']=='none' and s['transition']=='0s',s
                shot=output/f'body-{width}.png';page.screenshot(path=str(shot));result['screenshots'].append(str(shot))
                gates[3].set();parsed=page.evaluate('pending');assert parsed['name']=='é' and len(parsed['padding'])==64000
                page.wait_for_timeout(450);build=page.evaluate(snapshot)
                assert build['n']==95 and not build['hidden'] and abs(build['fill']/build['track']-.95)<.001,build
                shot=output/f'building-{width}.png';page.screenshot(path=str(shot));result['screenshots'].append(str(shot))
                values.append(build['n']);assert values==sorted(values),values
                page.evaluate('window.done=SalesRefreshProgress.finish()');page.evaluate('done')
                assert page.evaluate(snapshot)['n']==100
                page.wait_for_function('refreshProgress.hidden')
                result['runs'].append({'viewport':width,'waiting':[a,b],'anchor':anchor,'monotonic':values,'building':build})
            # Unknown totals retain estimated anchor plus MB, not bogus measured ratio.
            headers.clear()
            page.set_viewport_size({'width':320,'height':700})
            for gate in gates:gate.clear()
            page.evaluate("() => {SalesRefreshProgress.start();window.pending=fetch('/unknown',{method:'POST',body:'{}'}).then(r=>SalesRefreshProgress.readJson(r));}")
            page.wait_for_timeout(450);headers.set();page.wait_for_timeout(150);anchor=page.evaluate(snapshot)['n'];gates[0].set()
            page.wait_for_function('refreshProgress.getAttribute("aria-valuetext").includes("MB received")')
            unknown=page.evaluate(snapshot);assert unknown['n']==anchor
            assert unknown['captionFits'] and not unknown['overflow'],unknown
            page.screenshot(path=str(output/'unknown-320.png'))
            for gate in gates:gate.set()
            page.evaluate('pending');assert page.evaluate(snapshot)['n']==95
            page.evaluate('SalesRefreshProgress.fail()');assert page.locator('#refreshProgress').is_hidden()
            # Reduced motion permits numeric estimates but no interpolated CSS motion.
            page.emulate_media(reduced_motion='reduce');page.evaluate('SalesRefreshProgress.start()');page.wait_for_timeout(450)
            reduced=page.evaluate(snapshot);assert 0<reduced['n']<=15 and reduced['animation']=='none' and reduced['transition']=='0s'
            page.emulate_media(media='print');assert page.locator('#refreshProgress').is_hidden()
            page.emulate_media(media='screen');page.evaluate('SalesRefreshProgress.fail()');page.wait_for_timeout(450);assert page.locator('#refreshProgress').is_hidden()
            # Immediate restart must survive the prior completion hide deadline.
            page.evaluate('SalesRefreshProgress.start();SalesRefreshProgress.building()');page.evaluate('SalesRefreshProgress.finish()');page.evaluate('SalesRefreshProgress.start()');page.wait_for_timeout(450)
            assert page.locator('#refreshProgress').is_visible();page.evaluate('SalesRefreshProgress.fail()')
            result.update(unknown_anchor_held=True,reduced_motion=reduced,print_hidden=True,error_hidden=True,restart_visible=True,requests=requests)
            browser.close()
        (output/'estimated-browser-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'runs':len(result['runs']),'screenshots':len(result['screenshots']),'output':str(output)}))
    finally:
        headers.set()
        for gate in gates:gate.set()
        server.shutdown();server.server_close()
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);run(ap.parse_args().output)
