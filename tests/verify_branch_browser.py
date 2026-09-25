"""Read-only browser verification. Run explicitly with URL and private evidence directory.
Uses local snapshot only on localhost. Hosted URL requires an existing signed-in
session or --payload with a separately verified, unchanged serving snapshot; the
latter is explicitly split verification, not a signed-in browser test.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def run(url, output, payload=None):
    output.mkdir(parents=True, exist_ok=True)
    result = {'url': url, 'mode': 'production HTML + separately read serving payload' if payload else 'localhost real snapshot', 'checks': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel='msedge')
        page = browser.new_page(viewport={'width':1440,'height':1000})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url, wait_until='networkidle')
        if payload:
            # Do not impersonate a login or alter auth. Render verified data in this isolated test page.
            page.evaluate("data=>{state.data=data;populateViewFilters();populateWeeks();render();lock.classList.remove('show')}",json.loads(payload.read_text(encoding='utf-8')))
        page.wait_for_function('!!state.data && !!document.querySelector("[data-branch]")')
        assert page.locator('.version').inner_text() == 'VERSION 1.19'
        page.locator('[data-view=branches]').click()
        names=page.locator('[data-branch]').evaluate_all('(els)=>els.map(e=>e.dataset.branch)')
        for name in names:
            page.get_by_role('button',name=name,exact=True).click()
            assert ' '.join(name.split()) in page.locator('#branchDetailTitle').inner_text()
            assert 'totals match' in page.locator('#branchDetailBridge').inner_text()
        result['checks'].append(f'{len(names)} branch opens and reconciliations')
        page.locator('[data-branch=FARGO]').click()
        assert page.locator('#branchMonthlyChart').is_visible()
        assert page.locator('#branchItemsChart').is_visible()
        charts=page.evaluate("""()=>({monthly:state.charts.branchMonthlyChart.data,trend:state.charts.branchTrendChart.config.type,items:state.charts.branchItemsChart.data})""")
        assert len(charts['monthly']['labels'])==12
        assert charts['trend']=='line'
        assert len(charts['items']['labels'])==10
        assert page.locator('#branchTopItems tbody tr').count()==10
        assert 'Header less all lines' in page.locator('#branchItemsNote').inner_text()
        result['checks'].append('monthly year comparison, profit/margin line chart, top 10 source-line gross items')
        page.wait_for_timeout(350)
        page.screenshot(path=str(output/'branch-desktop.png'))
        for chart_id in ['branchMonthlyChart','branchTrendChart','branchItemsChart']:
            page.locator('#'+chart_id).locator('xpath=ancestor::div[contains(@class,"panel")][2]').screenshot(path=str(output/(chart_id+'-desktop.png')),style='.top { visibility:hidden; }')
        first=page.locator('[data-branch-document]').first.inner_text()
        page.locator('#branchDocNext').click()
        assert 'page 2' in page.locator('#branchDocPage').inner_text()
        assert page.locator('[data-branch-document]').first.inner_text()!=first
        page.locator('#branchDocPrev').click()
        assert page.locator('[data-branch-document]').first.inner_text()==first
        page.locator('#branchDocKind').select_option('Return')
        page.locator('[data-branch-document]').first.click()
        assert 'Header less lines' in page.locator('#branch-lines-0').inner_text()
        assert page.locator('#branch-lines-0 .order-lines tbody tr').count()>0
        result['checks'].append('pagination, returns, actual item lines and header/line residual')
        page.locator('#branchCustomers [data-member]').first.click()
        assert 'Customer:' in page.locator('#branchDocScope').inner_text()
        page.locator('#branchClearScope').click()
        page.locator('#branchSalespeople [data-member]').first.click()
        assert 'Salesperson:' in page.locator('#branchDocScope').inner_text()
        page.locator('#branchClearScope').click()
        for signal in ['loss','zero','screened']:
            page.locator('#branchDocSignal').select_option(signal)
            assert page.locator('[data-branch-document]').count()>0
        page.locator('#branchDocSignal').select_option('all')
        page.locator('#branchDocSearch').fill('does-not-exist-XYZ')
        assert 'No matching' in page.locator('#branchDocuments').inner_text()
        page.locator('#branchDocSearch').fill('')
        result['checks'].append('customer/salesperson branch-scoped filters, loss/zero/screened filters, empty search')
        for period in ['1M','FULL','MONTH','YTD']:
            page.locator('#branchesPeriod').select_option(period)
            assert 'totals match' in page.locator('#branchDetailBridge').inner_text()
        page.locator('#branchesPeriod').select_option('MONTH')
        page.locator('#branchesMonth').select_option('2024-01')
        assert 'totals match' in page.locator('#branchDetailBridge').inner_text()
        assert page.locator('#overviewPeriod').input_value()=='YTD'
        result['checks'].append('YTD/30-day/FULL/historical month and independent tab filters')
        page.locator('#branchesPeriod').select_option('YTD')
        # Existing salesperson invoice, customer, weekly and margin screens remain usable.
        page.locator('[data-view=salespeople]').click()
        page.locator('#salespeopleBody tr').first.click()
        page.locator('[data-invoice-index]').first.click()
        assert 'Header less lines' in page.locator('#invoice-lines-0').inner_text()
        page.locator('#drawerClose').click()
        for tab in ['customers','orders','weekly','margins','overview','branches']:
            page.locator(f'[data-view={tab}]').click()
            assert page.locator(f'#{tab}').is_visible()
        result['checks'].append('other tabs and existing salesperson invoice expansion')
        page.set_viewport_size({'width':390,'height':844})
        page.locator('[data-branch=BIS]').click()
        page.wait_for_timeout(350)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'page-wide mobile overflow'
        page.screenshot(path=str(output/'branch-mobile.png'))
        page.locator('[data-branch-document]').first.click()
        page.locator('#branch-lines-0').scroll_into_view_if_needed()
        assert page.locator('#branch-lines-0').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'item expansion mobile overflow'
        page.screenshot(path=str(output/'branch-mobile-items.png'))
        result['checks'].append('390px mobile layout and item expansion without page overflow')
        # An older detail payload without start retains the existing historical fallback.
        page.evaluate('()=>{delete state.data.invoice_drilldown.start;renderBranchOverview()}')
        assert page.locator('#branchMonthlyChart').is_visible()
        assert page.locator('[data-branch-document]').count()>0
        result['checks'].append('legacy missing start-date fallback')
        # Legacy snapshot simulation never reports unavailable detail as zero activity.
        page.evaluate('()=>{state.data={...state.data,invoice_drilldown:undefined};renderBranchOverview()}')
        assert 'unavailable' in page.locator('#branchDetailBridge').inner_text()
        assert not page.locator('#branchTrendChart').is_visible()
        assert not page.locator('#branchDocuments').is_visible()
        result['checks'].append('legacy detail unavailable fallback')
        assert not errors, errors
        result['page_errors']=errors
        browser.close()
    (output/'browser-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    args=argparse.ArgumentParser()
    args.add_argument('--url',default='http://127.0.0.1:8768')
    args.add_argument('--output',type=Path,required=True)
    args.add_argument('--payload',type=Path)
    a=args.parse_args()
    run(a.url,a.output,a.payload)
