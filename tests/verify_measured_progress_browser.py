"""Bounded real-browser byte stream proof; synthetic data, no production network."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
def run(output):
    output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1024,'height':600})
        page.set_content('<button id="refreshBtn">Refresh</button><div id="lock"></div><main class="content"><h1>SMI measured refresh — local stream proof</h1></main>')
        page.add_style_tag(content=(ROOT/'report-toolbar.css').read_text())
        page.add_script_tag(content=(ROOT/'refresh-progress.js').read_text())
        page.evaluate("""() => {window.results=[];window.begin=(known)=>{SalesRefreshProgress.start();const raw=new TextEncoder().encode('{"name":"é"}');window.raw=raw;let controller;const body=new ReadableStream({start(c){controller=c}});window.chunk=()=>controller.enqueue(raw.slice(0,6));window.end=()=>{controller.enqueue(raw.slice(6));controller.close()};const res=new Response(body,{headers:known?{'X-Uncompressed-Content-Length':String(raw.length)}:{}});window.pending=SalesRefreshProgress.readJson(res).then(x=>{results.push(x);return x});};} """)
        page.evaluate('SalesRefreshProgress.start()')
        assert page.locator('.refresh-progress-caption').inner_text()=='Loading sales data'
        assert page.locator('#refreshProgress').get_attribute('aria-valuenow') is None
        page.screenshot(path=str(output/'preparing.png'))
        for known in [True,False]:
            page.evaluate('(known)=>begin(known)',known)
            assert page.locator('.refresh-progress-caption').inner_text().startswith('Downloading')
            page.evaluate('chunk()')
            page.wait_for_function("refreshProgress.getAttribute('aria-valuetext').includes('46%')" if known else "refreshProgress.getAttribute('aria-valuetext').includes('MB received')")
            assert page.locator('#refreshProgress').get_attribute('aria-valuenow')==('46' if known else None)
            page.screenshot(path=str(output/('known-bytes.png' if known else 'unknown-bytes.png')))
            page.evaluate('end()')
            page.evaluate('pending')
            assert page.locator('.refresh-progress-caption').inner_text()=='Building dashboard'
            page.screenshot(path=str(output/'building.png'))
            page.evaluate('SalesRefreshProgress.finish()')
            assert page.locator('#refreshProgress').get_attribute('aria-valuenow')=='100'
        assert page.evaluate('results.every(x=>x.name==="é")')
        page.evaluate('SalesRefreshProgress.start();SalesRefreshProgress.fail()')
        assert page.locator('#refreshProgress').is_hidden()
        browser.close()
    (output/'browser-results.json').write_text(json.dumps({'known_percent':46,'unknown_percent':None,'unicode_equal':True,'building_no_percent':True,'success_after_await':True,'failure_hidden':True},indent=2))
if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);run(ap.parse_args().output)
