"""Frozen-real-data local toolbar/KPI regression. Never refreshes GP or publishes."""
import argparse, hashlib, json, threading
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
WIDTHS = [320,360,390,430,760,820,1024,1440]
MEASURE = """() => [...document.querySelectorAll('#overview .kpi > *')].filter(e=>e.getClientRects().length).map(e=>{const r=document.createRange();r.selectNodeContents(e);const b=r.getBoundingClientRect(),c=e.closest('.kpi').getBoundingClientRect();return {id:e.id,text:e.textContent,left:b.left,right:b.right,cardLeft:c.left,cardRight:c.right,ok:b.left>=c.left-1&&b.right<=c.right+1}})"""
def run(snapshot, output, phase):
    output.mkdir(parents=True,exist_ok=True)
    raw=snapshot.read_bytes(); data=json.loads(raw)
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            if self.path.split('?')[0]=='/data/sales.json':
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
            else: super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    result={'phase':phase,'sha256':hashlib.sha256(raw).hexdigest(),'as_of':data.get('as_of'),'checks':[],'failures':[]}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
            page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle');page.wait_for_function('!!state.data && !refreshBtn.disabled')
            page.evaluate('window.realSnapshotBefore=JSON.stringify(state.data)')
            page.evaluate("window.originalNodes=Object.fromEntries(['refreshBtn','exportView','monthlyReportMonth','monthlyReportPdf','monthlyReportDownload'].map(id=>[id,{node:document.getElementById(id),handler:document.getElementById(id).onclick}]))")
            for width in WIDTHS:
                page.set_viewport_size({'width':width,'height':1000});page.wait_for_timeout(140)
                rows=page.evaluate(MEASURE)
                result['checks'].append({'width':width,'kind':'real','rows':rows})
                result['failures'] += [{'width':width,'kind':'real','overflow':r} for r in rows if not r['ok']]
                page.screenshot(path=str(output/f'{phase}-{width}.png'))
            if not page.locator('#reportMenuButton').count(): result['failures'].append('Top-right hamburger missing')
            else:
                for width in WIDTHS+[390,1440,320,820,390,1440]:
                    page.set_viewport_size({'width':width,'height':1000});page.wait_for_timeout(100)
                    b=page.locator('#reportMenuButton');assert b.get_attribute('aria-expanded')=='false'
                    b.click();panel=page.locator('#reportMenuPanel');assert panel.is_visible()
                    rect=panel.bounding_box();assert rect['x']>=0 and rect['x']+rect['width']<=width+1
                    for id in ['refreshBtn','exportView','monthlyReportMonth','monthlyReportPdf','monthlyReportDownload']:
                        assert page.locator('#'+id).count()==1
                        assert page.locator('#reportMenuPanel #'+id).is_visible()
                    assert page.evaluate('Object.entries(originalNodes).every(([id,x])=>document.getElementById(id)===x.node&&x.node.onclick===x.handler)')
                    page.keyboard.press('Escape');assert b.get_attribute('aria-expanded')=='false';assert b.evaluate('e=>e===document.activeElement')
                b.focus();page.keyboard.press('Enter');assert b.get_attribute('aria-expanded')=='true';page.keyboard.press('Escape')
                # Actual original Refresh handler reads the frozen local file exactly once.
                reads=[]
                page.on('request',lambda request: reads.append(request.url) if '/data/sales.json' in request.url else None)
                b.click();page.locator('#refreshBtn').click();page.wait_for_function('!refreshBtn.disabled');page.wait_for_timeout(200)
                assert len(reads)==1,reads
                assert page.evaluate('refreshBtn.onclick===load && exportView.onclick===ReportExport.exportView')
                result['checks'].append({'kind':'original-refresh-handler','frozen_snapshot_requests':len(reads)})
                page.keyboard.press('Escape')
                for width in [390,1440]:
                    page.set_viewport_size({'width':width,'height':1000});page.wait_for_timeout(150);b.click()
                    page.screenshot(path=str(output/f'after-menu-{width}.png'));page.keyboard.press('Escape')
                b.click();page.locator('#monthlyReportMonth').select_option('2026-10');page.keyboard.press('Escape');b.click();assert page.locator('#monthlyReportMonth').input_value()=='2026-10'
                # Keyboard focus containment and outside dismissal.
                page.locator('#refreshBtn').focus();page.keyboard.press('Tab');assert page.locator('#monthlyReportMonth').evaluate('e=>e===document.activeElement')
                page.locator('#monthlyReportDownload').focus();page.keyboard.press('Tab');assert b.evaluate('e=>e===document.activeElement')
                page.keyboard.press('Escape');b.click();page.locator('#viewTitle').click();assert b.get_attribute('aria-expanded')=='false'
                # Existing loading/export guard still blocks output while Refresh is disabled.
                b.click();page.evaluate('refreshBtn.disabled=true')
                messages=[]
                page.once('dialog',lambda d:(messages.append(d.message),d.accept()))
                page.locator('#exportView').click();assert messages==['Wait for the report to finish loading before exporting.'],messages
                page.evaluate('refreshBtn.disabled=false');page.keyboard.press('Escape')
                result['checks'].append({'kind':'original-loading-guard','messages':messages})
                downloads=[];popups=[]
                page.on('download',lambda item:downloads.append(item))
                page.on('popup',lambda item:popups.append(item))
                for month in ['2026-10','2026-09']:
                    b.click();page.locator('#monthlyReportMonth').select_option(month)
                    with page.expect_download(timeout=60000) as pending: page.locator('#monthlyReportDownload').click()
                    download=pending.value;download.save_as(str(output/download.suggested_filename))
                    assert len(downloads)==len([c for c in result['checks'] if c['kind']=='native-download'])+1
                    result['checks'].append({'kind':'native-download','month':month,'filename':download.suggested_filename})
                    if b.get_attribute('aria-expanded')=='true':page.keyboard.press('Escape')
                for id in ['monthlyReportPdf','exportView']:
                    b.click()
                    with page.expect_popup() as opened:page.locator('#'+id).click()
                    popup=opened.value;popup.wait_for_load_state();assert popup.locator('body').inner_text().strip();popup.close()
                    result['checks'].append({'kind':'original-popup-handler','id':id,'popup_count':len(popups)})
                    if b.get_attribute('aria-expanded')=='true':page.keyboard.press('Escape')
                assert len(popups)==2 and len(downloads)==2
                assert page.evaluate('JSON.stringify(state.data)===realSnapshotBefore')
                # Synthetic browser-only edge values exercise layout, never persisted financial data.
                for width in WIDTHS:
                    page.set_viewport_size({'width':width,'height':1000})
                    for text in ['$123,456,789.12','-$123,456,789.12','$0.01']:
                        page.evaluate('''(text)=>{const value=Number(text.replace(/[$,]/g,'')),t=selection('overview').totals;t.sales=value;t.profit=value;t.returns=value;state.data.open_orders.amount=value;renderKpis();document.querySelectorAll('#overview .k-value:not(#salesKpi):not(#profitKpi):not(#returnsKpi):not(#orderKpi)').forEach(e=>e.textContent=text)}''',text);page.wait_for_timeout(100)
                        assert page.locator('#salesKpi').inner_text()==text
                        rows=page.evaluate(MEASURE);result['checks'].append({'width':width,'kind':'synthetic-edge','text':text,'rows':rows})
                        result['failures'] += [{'width':width,'kind':'synthetic-edge','overflow':r} for r in rows if not r['ok']]
            browser.close()
    finally:
        server.shutdown();(output/f'{phase}-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'phase':phase,'cases':len(result['checks']),'failures':len(result['failures']),'first_failures':result['failures'][:5]}))
    assert not result['failures'],result['failures'][:5]
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',default='after');a=p.parse_args();run(a.snapshot,a.output,a.phase)
