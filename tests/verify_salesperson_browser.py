"""Real snapshot acceptance, independent Decimal reconciliation and individual PDF isolation."""
import argparse,json,hashlib,threading,re
from decimal import Decimal
from functools import partial
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
import pymupdf
ROOT=Path(__file__).resolve().parents[1]
def run(payload,output):
 output.mkdir(parents=True,exist_ok=True);raw=payload.read_bytes();data=json.loads(raw);detail=data['invoice_drilldown'];errors=[];checks=[]
 docs=[dict(zip(detail['document_fields'],r)) if isinstance(r,list) else r for r in detail['documents']]
 people=sorted(set(d['salesperson'] for d in docs if d['salesperson']))
 def independent(model):
  for side in ['current','prior']:
   got=model[side];start=model['dates'][side+'_start'];end=model['dates'][side+'_end']
   if start<detail['start']:assert got is None;continue
   scope=[d for d in docs if d['salesperson']==model['name'] and start<=d['date']<=end]
   gross=sum((Decimal(str(d['sales'])) for d in scope if d['kind']=='Invoice'),Decimal(0));returns=-sum((Decimal(str(d['sales'])) for d in scope if d['kind']=='Return'),Decimal(0));groups={};missing=0
   for d in scope:
    if d['kind']!='Invoice':continue
    lines=detail['lines'].get(d['key'],[])
    if not lines:missing+=1
    for rawline in lines:
     line=dict(zip(detail['line_fields'],rawline)) if isinstance(rawline,list) else rawline
     cls,sub=data['item_categories']['items'].get(line['item'],['','']);cls=cls.strip();sub=sub.strip()
     cat='REBAR' if cls.upper()=='REBAR' or (cls.upper()=='STEEL' and sub=='50') else cls or 'Unclassified'
     groups[cat]=groups.get(cat,Decimal(0))+Decimal(str(line['sales']))
   total=sum(groups.values(),Decimal(0))
   for key,val in [('gross',gross),('returns',returns),('net',gross-returns),('line_sales',total),('residual',gross-total)]:assert Decimal(str(got[key]))==val,(side,key,got[key],val)
   assert got['missing']==missing
   assert {k:Decimal(str(v)) for k,v in got['categories'].items()}==groups
 class Handler(SimpleHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_GET(self):
   if self.path.split('?')[0]=='/data/sales.json':self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
   else:super().do_GET()
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT)));worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True,channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle');page.wait_for_function('!!state.data')
   page.locator('[data-view=salespeople]').click();page.evaluate("openSalesperson('DYLAN','salespeople')")
   model=page.evaluate('salespersonReportCapture.model');independent(model);(output/'dylan-model.json').write_text(json.dumps(model,indent=2))
   page.screenshot(path=str(output/'desktop.png'),full_page=False)
   page.locator('#salespersonComparison').screenshot(path=str(output/'desktop-comparison.png'))
   for size,label in [({'width':390,'height':844},'mobile'),({'width':820,'height':1180},'tablet')]:
    page.set_viewport_size(size);page.evaluate("document.querySelector('#salespersonDrawer .drawer').scrollTop=0");page.screenshot(path=str(output/(label+'.png')),full_page=False)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert page.locator('#salespersonDrawer [data-report-export]').is_visible()
   page.set_viewport_size({'width':1440,'height':1000})
   def pdf(name,main=False):
    with page.expect_popup() as opened:
     if main:page.evaluate('ReportExport.exportView()')
     else:page.locator('#salespersonDrawer [data-report-export]').click()
    report=opened.value;report.wait_for_function('document.documentElement.dataset.reportReady === "true"')
    assert report.locator('.view,.drawer,.report-detail,canvas,script,input,select,[onclick]').count()==0
    assert report.locator('#salespersonComparison').count()==1
    assert report.locator('#salespersonComparison thead').count()==2
    assert report.locator('#salespersonComparison td[data-label]').count()==page.locator('#salespersonComparison td[data-label]').count()
    assert report.locator('.pc-bar').count()==page.locator('#salespersonComparison .pc-bar').count()
    assert report.locator('.pc-bar').evaluate_all('(xs)=>xs.every(x=>x.style.width!=="")')
    text=report.locator('body').inner_text();assert data['sha256'] in text
    for rep in people:
     if rep!='DYLAN' and len(rep)>2:assert not re.search(r'(?<!\w)'+re.escape(rep)+r'(?!\w)',text),('other salesperson leaked',rep)
    assert 'Top Customers' not in text and 'Sales Overview' not in text and 'Posted invoices →' not in text
    report.evaluate('window.print=()=>window.printInvoked=true');report.get_by_role('button',name='Print / Save as PDF').click();assert report.evaluate('window.printInvoked===true')
    path=output/(name+'.pdf');report.pdf(path=str(path),print_background=True,prefer_css_page_size=True)
    doc=pymupdf.open(path);printed=''.join(''.join(pg.get_text().split()) for pg in doc)
    for cell in report.locator('td').all_text_contents():assert ''.join(cell.split()) in printed,cell
    for i,pg in enumerate(doc):
     assert pg.get_text().strip()
     for word in pg.get_text('words'):assert word[0]>=0 and word[1]>=0 and word[2]<=pg.rect.width+1 and word[3]<=pg.rect.height+1,word
     pg.get_pixmap(matrix=pymupdf.Matrix(1.3,1.3)).save(output/f'{name} page {i+1}.png')
    frozen=text;page.evaluate("document.querySelector('#salespeopleSearch')?.setAttribute('value','changed')");assert report.locator('body').inner_text()==frozen
    checks.append({'name':name,'pages':len(doc),'pdf_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'other_salespeople_checked':len([x for x in people if x!='DYLAN' and len(x)>2]),'table_cells_verified':report.locator('td').count()});report.close()
   pdf('Dylan Sales Comparison October 8 2026');pdf('Main export individual scope',True)
   page.set_viewport_size({'width':390,'height':844});pdf('Mobile individual export')
   page.locator('#salespersonComparison h3').nth(1).scroll_into_view_if_needed();page.screenshot(path=str(output/'mobile-categories.png'))
   assert page.locator('#salespersonComparison').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
   page.set_viewport_size({'width':1440,'height':1000})
   other=next(p for p in people if p!='DYLAN' and p in data['salesperson_details'])
   switched=page.evaluate("n=>{openSalesperson(encodeURIComponent(n),'salespeople');return salespersonReportCapture.model}",other);independent(switched)
   assert switched['name']==other
   page.evaluate("openSalesperson('DYLAN','salespeople')")
   page.evaluate("()=>{window.savedCategories=state.data.item_categories;state.data.item_categories={...savedCategories,items:Object.fromEntries(Object.keys(savedCategories.items).map(k=>[k,['<img src=x onerror=alert(1)>','']]))};renderSalespersonComparison('DYLAN','salespeople')}")
   assert page.locator('#salespersonComparison img').count()==0 and '<img' in page.locator('#salespersonComparison').inner_text()
   page.evaluate("state.data.item_categories=savedCategories;renderSalespersonComparison('DYLAN','salespeople')")
   for filter in [{'period':'1M'},{'period':'MONTH','month':'2026-10'},{'period':'MONTH','month':'2025-02'},{'period':'MONTH','month':'2024-01'},{'period':'FULL'}]:
    model=page.evaluate("f=>{state.viewFilters.salespeople={...state.viewFilters.salespeople,...f};openSalesperson('DYLAN','salespeople');return salespersonReportCapture.model}",filter);independent(model);checks.append({'filter':filter,'prior_available':model['prior'] is not None,'independent_decimal_match':True})
   pdf('Unavailable prior comparison')
   def alert_guard(setup,expected):
    page.evaluate(setup);messages=[];page.once('dialog',lambda d:(messages.append(d.message),d.accept()));page.locator('#salespersonDrawer [data-report-export]').click();assert len(messages)==1 and expected in messages[0],messages
   alert_guard("state.data.sha256='changed'",'Close and reopen');page.evaluate('(v)=>state.data.sha256=v',data['sha256'])
   alert_guard('refreshBtn.disabled=true','finish loading');page.evaluate('refreshBtn.disabled=false')
   alert_guard('window.savedOpen=window.open;window.open=()=>null','Allow pop-ups');page.evaluate('window.open=window.savedOpen')
   page.evaluate("closeSalesperson();state.viewFilters.salespeople.period='YTD'")
   with page.expect_popup() as opened:page.locator('#exportView').click()
   report=opened.value;report.wait_for_function('document.documentElement.dataset.reportReady === "true"');assert report.locator('.view').count()==1;report.close()
   assert not errors,errors;browser.close()
 finally:server.shutdown();server.server_close();worker.join()
 result={'mode':'Edge/Chromium local frozen authenticated-serving payload; not signed-in hosted E2E or native Safari print','checks':checks,'page_errors':errors,'source_sha256':data['sha256'],'payload_sha256':hashlib.sha256(raw).hexdigest(),'as_of':data['as_of'],'guards':['stale snapshot','loading','blocked popup'],'summary':{'current_net':model['current']['net'],'note':'Last exercised scope is FULL; Dylan YTD in dylan-model.json'}}
 (output/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--payload',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();run(a.payload,a.output)
