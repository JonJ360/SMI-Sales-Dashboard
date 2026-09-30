"""Local-only PDF acceptance tests; explicit private frozen snapshot, no login/publication."""
import argparse
import hashlib
import json
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import threading
from playwright.sync_api import sync_playwright
import pymupdf
ROOT = Path(__file__).resolve().parents[1]

def run(payload, output):
    output.mkdir(parents=True, exist_ok=True)
    raw = payload.read_bytes(); data = json.loads(raw)
    errors, checks = [], []
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            if self.path.split('?')[0] == '/data/sales.json':
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(raw)
            else: super().do_GET()
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT)))
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel='msedge')
            page = browser.new_page(viewport={'width':1440, 'height':1000}, accept_downloads=True)
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}', wait_until='networkidle')
            page.wait_for_function('!!state.data')
            assert page.locator('#exportView').count() == 1, 'Export this view control is missing'

            def sample(name, button='#exportView', required=(), drawer=False):
                page.wait_for_timeout(200)
                before=page.evaluate('JSON.stringify({view:state.view,filters:state.viewFilters,weekly:state.weekly})')
                expected_rows=page.locator('.view.active tbody tr:visible,.drawer-shade.show tbody tr:visible').count()
                expected_charts=page.locator('.view.active canvas:visible,.drawer-shade.show canvas:visible').count()
                with page.expect_popup() as opened: page.locator(button).click()
                report=opened.value
                report.on('pageerror',lambda e:errors.append(str(e)))
                report.wait_for_function('document.documentElement.dataset.reportReady === "true"')
                assert report.locator('.view').count()==1
                assert report.locator('.report-detail').count()==int(drawer)
                assert report.locator('tbody tr').count()==expected_rows, name
                assert report.locator('canvas,script,input,select,[onclick]').count()==0
                assert report.locator('img').count()==expected_charts
                assert data['sha256'] in report.locator('body').inner_text()
                # Invoke the actual preview button with print intercepted, then exercise the same Chromium print renderer.
                report.evaluate('window.print=()=>window.printInvoked=true')
                report.get_by_role('button',name='Print / Save as PDF').click()
                assert report.evaluate('window.printInvoked===true')
                report.pdf(path=str(output/f'{name}.pdf'),print_background=True,prefer_css_page_size=True)
                doc=pymupdf.open(output/f'{name}.pdf');text=''.join(pg.get_text() for pg in doc)
                for value in ['Data as of','Source snapshot SHA-256',*required]:
                    assert ''.join(value.split()).casefold() in ''.join(text.split()).casefold(), (name,value)
                printed=''.join(text.split()).casefold()
                cells=report.locator('td:not(:has(table))').all_text_contents()
                missing=[cell for cell in cells if cell.strip() and ''.join(cell.split()).casefold() not in printed]
                assert not missing,(name,'PDF lost table cell text',missing[:3])
                assert sum(len(pg.get_images()) for pg in doc)>=expected_charts
                for i,pg in enumerate(doc):
                    assert pg.get_text().strip(),(name,'blank page',i)
                    for word in pg.get_text('words'):
                        assert word[0]>=0 and word[1]>=0 and word[2]<=pg.rect.width+1 and word[3]<=pg.rect.height+1,(name,'clipped text',word)
                    pg.get_pixmap(matrix=pymupdf.Matrix(1,1)).save(output/f'{name}-page-{i+1}.png')
                report.screenshot(path=str(output/f'{name}-preview.png'),full_page=True)
                checks.append({'name':name,'pages':len(doc),'rendered_rows':expected_rows,'charts':expected_charts})
                # A later dashboard search must not mutate the captured document.
                frozen=report.locator('body').inner_text()
                search=page.locator('.view.active input.search:visible').first
                original=search.input_value() if search.count() else None
                try:
                    if original is not None: search.evaluate("e=>{e.value='changed after capture';e.dispatchEvent(new Event('input',{bubbles:true}))}")
                    assert report.locator('body').inner_text()==frozen
                finally:
                    if original is not None: search.evaluate("(e,value)=>{e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}))}",original)
                if original is not None: assert search.input_value()==original
                assert page.evaluate('JSON.stringify({view:state.view,filters:state.viewFilters,weekly:state.weekly})')==before
                report.close()

            sample('overview',required=['Net Sales'])
            page.locator('#overviewPeriod').select_option('MONTH')
            page.locator('#overviewMonth').select_option('2024-01')
            sample('overview-month',required=['January 2024','2024-01-01','2024-01-31'])
            page.locator('[data-view=customers]').click()
            page.locator('#customersPeriod').select_option('1M')
            page.locator('#customerCohort').select_option('prior')
            name=page.locator('#customersBody tr.clickable td:nth-child(2)').first.inner_text()
            page.locator('#customerSearch').fill(name)
            sample('customer-filtered',required=[name,'Last 30 days'])
            page.locator('#customerSearch').fill(name)
            page.locator('#customersBody tr.clickable').first.click()
            sample('customer-detail','#customerDrawer [data-report-export]',required=[name,'Open detail'],drawer=True)
            # Stale open detail cannot be stamped with a new snapshot identity.
            page.evaluate("state.data.sha256='changed-snapshot'")
            def expect_alert(button, message):
                messages=[]
                def accept(dialog):
                    messages.append(dialog.message);dialog.accept()
                page.once('dialog',accept)
                page.locator(button).click()
                assert len(messages)==1 and message in messages[0],messages
            expect_alert('#customerDrawer [data-report-export]','Close and reopen')
            page.evaluate('(sha)=>state.data.sha256=sha',data['sha256'])
            page.locator('#customerDrawerClose').click()
            page.locator('#customerSearch').fill('no-match-zzzz')
            sample('customer-empty',required=['No customers'])
            page.locator('#customerSearch').fill('')
            page.set_viewport_size({'width':390,'height':844})
            assert page.locator('#exportView').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(output/'mobile-controls.png'),full_page=True)
            sample('mobile-customers')
            page.set_viewport_size({'width':1440,'height':1000})
            page.locator('[data-view=salespeople]').click()
            page.locator('#salespeopleBody tr.clickable').first.click()
            page.locator('[data-invoice-index]').first.click()
            sample('salesperson-expanded','#salespersonDrawer [data-report-export]',required=['Open detail','item lines'],drawer=True)
            page.locator('#drawerClose').click()
            page.locator('#salespeoplePeriod').select_option('FULL')
            longest=page.evaluate("()=>{const detail=state.data.invoice_drilldown;const d=decodeInvoiceRows(detail.document_fields,detail.documents).filter(x=>x.kind==='Invoice'&&state.data.salesperson_details[x.salesperson]).sort((a,b)=>(detail.lines[b.key]||[]).length-(detail.lines[a.key]||[]).length)[0];openSalesperson(encodeURIComponent(d.salesperson),'salespeople');return {sop:d.sop,count:detail.lines[d.key].length}}")
            assert longest['count']>20,longest
            page.locator('#invoiceSearch').fill(longest['sop'])
            page.locator('[data-invoice-index]').first.click()
            sample('long-invoice','#salespersonDrawer [data-report-export]',required=[str(longest['count'])+' item lines'],drawer=True)
            checks[-1]['expanded_line_count']=longest['count']
            page.locator('#drawerClose').click()
            page.locator('[data-view=branches]').click()
            page.locator('[data-branch]').first.click()
            page.locator('[data-branch-document]').first.click()
            sample('branch-expanded',required=['Branch detail','item lines'])
            page.locator('[data-view=weekly]').click()
            page.locator('[data-weekly-person]').first.click()
            page.locator('[data-weekly-order]').first.click()
            sample('weekly-expanded',required=['source lines','Orders written'])
            page.locator('[data-view=margins]').click()
            page.locator('#marginRange').select_option('week')
            sample('margin-exceptions')
            page.locator('[data-view=orders]').click()
            sample('open-orders')
            # Popup blocking and loading guards return an actionable message, not a broken tab.
            page.evaluate('window.savedOpen=window.open;window.open=()=>null')
            expect_alert('#exportView','Allow pop-ups')
            page.evaluate('window.open=window.savedOpen;refreshBtn.disabled=true')
            expect_alert('#exportView','finish loading')
            page.evaluate('refreshBtn.disabled=false')
            # Source text is inert; no copied event handlers or HTML interpretation.
            page.evaluate("()=>{const p=document.createElement('p');p.textContent='<img src=x onerror=alert(1)> & literal';document.querySelector('.view.active').append(p)}")
            sample('literal-text',required=['<img src=x onerror=alert(1)> & literal'])
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close();worker.join()
    result={'checks':checks,'page_errors':errors,'payload_sha256':hashlib.sha256(raw).hexdigest(),'source_sha256':data['sha256'],'data_as_of':data['as_of'],'heartbeat':data.get('refreshed_at'),'guards':['popup blocked','loading','stale drawer'],'mode':'local frozen snapshot; no authenticated live E2E'}
    (output/'pdf-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--payload',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();run(a.payload,a.output)
