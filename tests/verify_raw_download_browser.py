"""Local raw RPC transport proof. Synthetic fixture; never production evidence."""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
RAW = json.dumps({'name': 'é', 'padding': 'x' * 64000}, ensure_ascii=False).encode()
RAW += b' ' * (-len(RAW) % 4)

def run(output):
    output.mkdir(parents=True, exist_ok=True)
    gates = [threading.Event() for _ in range(4)]
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            self.send_response(200); self.end_headers()
            self.wfile.write(b'<button id="refreshBtn">Refresh</button><div id="lock"></div><main class="content">Local raw download proof</main>')
        def do_POST(self):
            requests.append({'path': self.path, 'accept': self.headers.get('Accept'), 'body': self.rfile.read(int(self.headers['Content-Length'])).decode()})
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            if self.path != '/unknown':
                self.send_header('X-Uncompressed-Content-Length', str(len(RAW)))
                self.send_header('Access-Control-Expose-Headers', 'X-Uncompressed-Content-Length')
            self.end_headers()
            for i, gate in enumerate(gates):
                gate.wait(15)
                self.wfile.write(RAW[i * len(RAW)//4:(i+1)*len(RAW)//4]); self.wfile.flush()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page()
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.add_style_tag(content=(ROOT/'report-toolbar.css').read_text())
            page.add_script_tag(content=(ROOT/'refresh-progress.js').read_text())
            for width in [1024, 390, 320]:
                page.set_viewport_size({'width': width, 'height': 700})
                for gate in gates: gate.clear()
                page.evaluate("""() => {SalesRefreshProgress.start();window.pending=fetch('/rest/v1/rpc/smi_sales_download_snapshot',{method:'POST',headers:{Accept:'application/octet-stream','Content-Type':'application/json'},body:'{}'}).then(r=>SalesRefreshProgress.readJson(r));} """)
                for i, percent in enumerate([25, 50, 75]):
                    gates[i].set()
                    page.wait_for_function('(n)=>refreshProgress.getAttribute("aria-valuenow")===String(n)', arg=percent)
                    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                    geometry = page.evaluate("""() => {const b=refreshProgress.getBoundingClientRect(),t=document.querySelector('.refresh-progress-track').getBoundingClientRect(),f=document.querySelector('.refresh-progress-line').getBoundingClientRect();return {left:b.left,right:b.right,track:t.width-10,fill:f.width,percent:Number(refreshProgress.getAttribute('aria-valuenow')),overflow:document.documentElement.scrollWidth>innerWidth}}""")
                    assert abs(geometry['fill']/geometry['track']*100-percent) < 0.5, geometry
                    assert geometry['left'] >= 0 and geometry['right'] <= width and not geometry['overflow'], geometry
                    results.append({'viewport': width, **geometry})
                    page.screenshot(path=str(output/f'raw-{width}-{percent}.png'))
                gates[3].set()
                parsed = page.evaluate('pending')
                assert parsed['name'] == 'é' and len(parsed['padding']) == 64000
                assert page.locator('.refresh-progress-caption').inner_text() == 'Building dashboard'
                assert page.locator('#refreshProgress').get_attribute('aria-valuenow') is None
                page.evaluate('SalesRefreshProgress.finish()')
                assert page.locator('#refreshProgress').get_attribute('aria-valuenow') == '100'
            for gate in gates: gate.clear()
            page.evaluate("""() => {SalesRefreshProgress.start();window.pending=fetch('/unknown',{method:'POST',body:'{}'}).then(r=>SalesRefreshProgress.readJson(r));} """)
            gates[0].set()
            page.wait_for_function('refreshProgress.getAttribute("aria-valuetext").includes("MB received")')
            assert page.locator('#refreshProgress').get_attribute('aria-valuenow') is None
            assert page.locator('.refresh-progress-line').evaluate('(e)=>e.getBoundingClientRect().width') == 0
            for gate in gates: gate.set()
            page.evaluate('pending')
            browser.close()
        assert all(r['accept']=='application/octet-stream' and r['body']=='{}' for r in requests[:3])
        (output/'raw-browser-results.json').write_text(json.dumps({'synthetic_only': True, 'production_metadata_required_separately': True, 'measured': results, 'requests': requests, 'unknown_not_percentage_success': True, 'utf8_json_equal': True}, indent=2))
    finally:
        for gate in gates: gate.set()
        server.shutdown(); server.server_close()

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
