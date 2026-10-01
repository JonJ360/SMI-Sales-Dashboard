"""Frozen real-data annual-category/browser reconciliation. No production writes."""
import argparse,json,threading
from pathlib import Path
from decimal import Decimal
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
def expected(data,year):
    detail=data['invoice_drilldown']; master=data['item_categories']['items']; groups={}; header=total=returns=missing=0
    for raw in detail['documents']:
        d=dict(zip(detail['document_fields'],raw)) if isinstance(raw,list) else raw
        if not (detail.get('start','2024-01-01')<=d['date']<=data['as_of']) or int(d['date'][:4])!=year: continue
        amount=lambda v:int((Decimal(str(v))*100).quantize(Decimal('1')))
        if d['kind']=='Return': returns+=amount(d['sales']);continue
        if d['kind']!='Invoice': continue
        header+=amount(d['sales']); lines=detail['lines'].get(d['key'],[])
        if not lines: missing+=1
        for rawline in lines:
            line=dict(zip(detail['line_fields'],rawline)) if isinstance(rawline,list) else rawline
            cls,sub=master.get(line['item'],['','']); cls=cls.strip();sub=sub.strip()
            label='REBAR' if cls.upper()=='REBAR' or (cls.upper()=='STEEL' and sub=='50') else cls or 'Unclassified'
            values=groups.setdefault(label,[0]*12);v=amount(line['sales']);values[int(d['date'][5:7])-1]+=v;total+=v
    return dict(groups=groups,header=header,total=total,returns=returns,missing=missing)
def run(payload,output):
    output.mkdir(parents=True,exist_ok=True);data=json.loads(payload.read_text()); checks=[];errors=[]
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            if self.path.split('?')[0]=='/data/sales.json':
                b=payload.read_bytes();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
            else:super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT)));threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle');page.wait_for_function('!!state.data')
            assert page.locator('[data-view=categories]').count()==1,'Dedicated Product Categories navigation missing'
            page.locator('[data-view=categories]').click()
            years=page.locator('#categoryYear option').evaluate_all('(es)=>es.map(e=>Number(e.value))')
            for year in years:
                page.locator('#categoryYear').select_option(str(year)); exp=expected(data,year)
                actual=page.evaluate('y=>ItemCategoryModel.annual(state.data,y)',year)
                assert page.locator('#categoryYear').is_visible() and page.locator('#categoryChoice').is_visible()
                money=lambda v:('-' if v<0 else '')+'$'+format(abs(v),',.2f')
                assert page.locator('#categoryComparisonTable tbody tr').all_text_contents()==[c['name']+money(c['sales']) for c in actual['categories']]
                assert page.evaluate('state.charts.categoryCompareChart.data.datasets[0].data')==[c['sales'] for c in actual['categories'][:8]]
                for name,values in exp['groups'].items():
                    row=next(c for c in actual['categories'] if c['name']==name)
                    assert round(row['sales']*100)==sum(values)
                    for i,v in enumerate(values):
                        assert row['months'][i] is None if actual['months'][i]['status'] in ['Future','Unavailable'] else round(row['months'][i]*100)==v
                assert round(actual['line_sales']*100)==exp['total']
                assert round(actual['header_sales']*100)==exp['header']
                assert round(actual['difference']*100)==exp['header']-exp['total']
                assert round(actual['return_sales']*100)==exp['returns'];assert actual['missing_documents']==exp['missing']
                assert page.locator('#categoryComparisonTable tbody tr').count()==len(exp['groups'])
                checks.append(actual)
            page.locator('#categoryYear').select_option(data['as_of'][:4])
            for label in ['REBAR','TOOLS']:
                page.locator('#categoryChoice').select_option(label)
                assert page.locator('#categoryMonthlyTable tbody tr').count()==12
                assert page.evaluate('state.charts.categoryTrendChart.data.datasets[0].label')==label
            for width,name in [(1440,'desktop'),(390,'mobile'),(320,'narrow-mobile')]:
                page.set_viewport_size({'width':width,'height':1000});page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(1200)
                chart_sizes=page.evaluate("() => ['categoryTrendChart','categoryCompareChart'].map(id=>{const c=document.getElementById(id);return {id,width:c.width,height:c.height,pixels:c.getContext('2d').getImageData(0,0,c.width,c.height).data.filter((v,i)=>i%4===3&&v>0).length}})")
                assert all(c['pixels']>1000 for c in chart_sizes),chart_sizes
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                for id in ['categoryMonthlyTable','categoryComparisonTable']:
                    assert page.locator('#'+id).evaluate('(e)=>e.scrollWidth<=e.clientWidth'),id
                page.screenshot(path=str(output/(name+'.png')),full_page=True)
            page.evaluate('()=>{state.data.item_categories=undefined;renderCategoryTrends()}')
            assert 'unavailable' in page.locator('#categoryCoverage').inner_text()
            assert not page.locator('#categoryTrendChart').is_visible()
            assert not errors,errors
            browser.close()
    finally: server.shutdown();server.server_close()
    result=dict(years=checks,page_errors=errors,component_overflow=False,source_sha256=data['sha256'],as_of=data['as_of'],mode='Local rendered production code + frozen current real snapshot; not authenticated live E2E')
    (output/'browser-validation.json').write_text(json.dumps(result,indent=2));print(json.dumps({'years':len(checks),'errors':errors,'output':str(output)}))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--payload',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();run(a.payload,a.output)
