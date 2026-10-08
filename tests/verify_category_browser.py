"""Local-only real-snapshot browser/category reconciliation; no auth or publication."""
import argparse
import datetime as dt
from decimal import Decimal
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

def expected(data,entity,name,period,month):
    detail=data['invoice_drilldown']; master=data['item_categories']['items']
    end=data['as_of']; start=detail['start']
    if period=='YTD': start=end[:4]+'-01-01'
    if period=='1M': start=(dt.date.fromisoformat(end)-dt.timedelta(days=29)).isoformat()
    groups={}; header=total=missing=0
    for raw in detail['documents']:
        d=dict(zip(detail['document_fields'],raw))
        if d[entity]!=name or d['kind']!='Invoice' or d['date']>end: continue
        if period=='MONTH':
            if d['date'][:7]!=month: continue
        elif d['date']<start: continue
        header+=round(Decimal(str(d['sales']))*100)
        lines=detail['lines'].get(d['key'],[])
        if not lines: missing+=1
        for rawline in lines:
            line=dict(zip(detail['line_fields'],rawline))
            cls,sub=master.get(line['item'],['',''])
            label='REBAR' if cls.upper()=='REBAR' or (cls.upper()=='STEEL' and sub=='50') else cls or 'Unclassified'
            amount=round(Decimal(str(line['sales']))*100)
            groups[label]=groups.get(label,0)+amount;total+=amount
    all_rows=sorted(groups.items(),key=lambda kv:(-kv[1],kv[0]))
    top=[dict(name=k,sales=v/100) for k,v in all_rows[:5]]
    return dict(categories=top,category_count=len(groups),line_sales=total/100,header_sales=header/100,
                difference=(header-total)/100,missing_documents=missing,
                unclassified_sales=groups.get('Unclassified',0)/100,
                other_sales=sum(v for _,v in all_rows[5:])/100)


def run(payload,output,branch_regression=False):
    output.mkdir(parents=True,exist_ok=True)
    data=json.loads(payload.read_text(encoding='utf-8'))
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            if self.path.split('?')[0]=='/data/sales.json':
                body=payload.read_bytes();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            else: super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT)))
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    url=f'http://127.0.0.1:{server.server_port}'
    checks=[]; errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,channel='msedge')
            page=browser.new_page(viewport={'width':1440,'height':1000})
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url,wait_until='networkidle');page.wait_for_function('!!state.data')
            for entity,view,body,close,name_id in [('customer','customers','customersBody','customerDrawerClose','customerDrawerName')]:
                page.locator(f'[data-view={view}]').click()
                for period,month in [('YTD',''),('1M',''),('FULL',''),('MONTH','2024-01'),('MONTH',data['as_of'][:7])]:
                    page.locator('#'+view+'Period').select_option(period)
                    if month: page.locator('#'+view+'Month').select_option(month)
                    page.locator('#'+body+' tr.clickable').first.click()
                    name=page.locator('#'+name_id).inner_text()
                    actual=page.evaluate('a=>ItemCategoryModel.summarize(state.data,a.entity,a.name,filterForView(a.view))',dict(entity=entity,name=name,view=view))
                    assert actual==expected(data,entity,name,period,month),(entity,period,actual)
                    chart=page.evaluate("id=>({axis:state.charts[id].options.indexAxis,labels:state.charts[id].data.labels,values:state.charts[id].data.datasets[0].data})",entity+'CategoriesChart')
                    assert chart['axis']=='y'
                    assert chart['labels']==[d['name'] for d in actual['categories']]
                    assert chart['values']==[d['sales'] for d in actual['categories']]
                    assert page.locator('#'+entity+'CategoriesTable tbody tr').count()==len(actual['categories'])<=5
                    checks.append(dict(entity=entity,period=period,month=month,name=name,**actual))
                    if period=='YTD':
                        page.wait_for_timeout(400)
                        page.locator('#'+entity+'Drawer .drawer').screenshot(path=str(output/(entity+'-desktop.png')))
                        page.locator('#'+entity+'Categories').screenshot(path=str(output/(entity+'-categories-desktop.png')))
                        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(400)
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                        assert page.locator('#'+entity+'Drawer .drawer').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
                        assert page.locator('#'+entity+'CategoriesTable').evaluate('(e)=>e.scrollWidth<=e.clientWidth'), 'Category dollars must be visible without sideways scrolling'
                        page.locator('#'+entity+'Categories').screenshot(path=str(output/(entity+'-categories-mobile.png')))
                        page.set_viewport_size({'width':1440,'height':1000})
                    page.locator('#'+close).click()
                # Consecutive entity selection must not retain prior bars.
                page.locator('#'+body+' tr.clickable').nth(1).click()
                name=page.locator('#'+name_id).inner_text()
                actual=page.evaluate('a=>ItemCategoryModel.summarize(state.data,a.entity,a.name,filterForView(a.view))',dict(entity=entity,name=name,view=view))
                assert actual==expected(data,entity,name,'MONTH',data['as_of'][:7])
                page.locator('#'+close).click()
            # Overview entry points use overview filter, not other tabs' filters.
            page.locator('[data-view=overview]').click()
            page.locator('#overviewPeriod').select_option('1M')
            for entity,body,close,name_id in [('customer','overviewCustomers','customerDrawerClose','customerDrawerName'),('salesperson','overviewSalespeople','drawerClose','drawerName')]:
                page.locator('#'+body+' tr.clickable').first.click()
                name=page.locator('#'+name_id).inner_text()
                actual=page.evaluate('a=>ItemCategoryModel.summarize(state.data,a.entity,a.name,filterForView("overview"))',dict(entity=entity,name=name))
                assert actual==expected(data,entity,name,'1M','')
                if entity=='customer': assert 'Last 30 days' in page.locator('#customerCategoriesScope').inner_text()
                else: assert page.evaluate('salespersonReportCapture.model.dates.current_start') == (dt.date.fromisoformat(data['as_of'])-dt.timedelta(days=29)).isoformat()
                page.locator('#'+close).click()
            # XSS and legacy/empty fallbacks are explicit isolated test states.
            page.evaluate("()=>{window.savedMaster=state.data.item_categories;state.data.item_categories={...savedMaster,items:Object.fromEntries(Object.keys(savedMaster.items).map(k=>[k,['<img src=x onerror=alert(1)>','']]))}}")
            page.locator('#overviewCustomers tr.clickable').first.click()
            assert page.locator('#customerCategoriesTable img').count()==0
            assert '<img' in page.locator('#customerCategoriesTable').inner_text()
            page.locator('#customerDrawerClose').click()
            page.evaluate('()=>{state.data.item_categories=undefined}')
            for entity,body,close in [('customer','overviewCustomers','customerDrawerClose'),('salesperson','overviewSalespeople','drawerClose')]:
                page.locator('#'+body+' tr.clickable').first.click()
                if entity=='customer':
                    assert 'unavailable' in page.locator('#customerCategoriesNote').inner_text()
                    assert not page.locator('#customerCategoriesChart').is_visible()
                    assert page.locator('#customerCategoriesTable tbody tr').count()==0
                else:
                    assert 'Category detail unavailable' in page.locator('#salespersonComparison').inner_text()
                    assert page.evaluate('salespersonReportCapture.model.rows.length')==0
                page.locator('#'+close).click()
            assert not errors,errors
            browser.close()
        if branch_regression:
            from verify_branch_browser import run as branch_run
            branch_run(url,output/'branch-regression')
    finally:
        server.shutdown();server.server_close();worker.join()
    result=dict(mode='local HTML + frozen real sales + SELECT-only GP current item master',checks=checks,page_errors=errors,overview_filter_checks=True,second_entity_checks=True,mobile_overflow=False,xss_escaped=True,legacy_fallback_both=True)
    (output/'browser-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(reconciled_scopes=len(checks),page_errors=errors,output=str(output))))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--payload',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--branch-regression',action='store_true');a=ap.parse_args()
    run(a.payload,a.output,a.branch_regression)
