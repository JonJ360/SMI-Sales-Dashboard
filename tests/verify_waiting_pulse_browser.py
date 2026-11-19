"""Bounded local synthetic stream; no authenticated or production requests."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]

def run(output):
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width':390,'height':700})
        page.set_content('<button id="refreshBtn">Refresh</button><div id="lock"></div><main class="content">Local waiting pulse proof</main>')
        page.add_style_tag(content=(ROOT/'report-toolbar.css').read_text())
        page.add_script_tag(content=(ROOT/'refresh-progress.js').read_text())
        page.evaluate('SalesRefreshProgress.start()')
        snapshot = """() => {const t=document.querySelector('.refresh-progress-track'),f=document.querySelector('.refresh-progress-line'),s=getComputedStyle(t,'::before');return {opacity:Number(s.opacity),animation:s.animationName,content:s.content,background:s.backgroundImage,fill:f.getBoundingClientRect().width,text:refreshProgress.innerText,now:refreshProgress.getAttribute('aria-valuenow'),left:t.getBoundingClientRect().left,position:s.backgroundPosition}}"""
        a=page.evaluate(snapshot)
        page.screenshot(path=str(output/'waiting-390-a.png'))
        page.wait_for_timeout(450)
        b=page.evaluate(snapshot)
        page.screenshot(path=str(output/'waiting-390-b.png'))
        assert abs(a['opacity']-b['opacity'])>.05, (a,b)
        assert a['fill']==b['fill']==0 and a['now'] is None and b['now'] is None
        assert a['text']==b['text']=='Loading sales data' and '%' not in a['text']
        assert a['left']==b['left'] and a['position']==b['position']
        assert 'fill%3D%27none' in a['background'] or "fill='none'" in a['background']
        page.emulate_media(reduced_motion='reduce')
        reduced=page.evaluate(snapshot)
        assert reduced['animation']=='none' and reduced['fill']==0
        page.wait_for_timeout(100)
        assert page.evaluate(snapshot)['opacity']==reduced['opacity']
        page.emulate_media(reduced_motion='no-preference')
        page.evaluate("""() => {const raw=new TextEncoder().encode('{"ok":1}');let c;const body=new ReadableStream({start(x){c=x}});window.end=()=>{c.enqueue(raw.slice(4));c.close()};window.pending=SalesRefreshProgress.readJson(new Response(body,{headers:{'X-Uncompressed-Content-Length':String(raw.length)}}));c.enqueue(raw.slice(0,4));}""")
        page.wait_for_function('refreshProgress.getAttribute("aria-valuenow")==="50"')
        measured=page.evaluate(snapshot)
        assert measured['animation']=='none' and measured['content']=='none'
        geometry=page.evaluate("""() => {const t=document.querySelector('.refresh-progress-track'),f=document.querySelector('.refresh-progress-line');return {track:t.getBoundingClientRect().width-10,fill:f.getBoundingClientRect().width}}""")
        assert abs(geometry['fill']/geometry['track']-.5)<.001
        page.screenshot(path=str(output/'measured-390-50.png'))
        page.evaluate('end();pending')
        assert page.locator('.refresh-progress-caption').inner_text()=='Building dashboard'
        page.evaluate('SalesRefreshProgress.finish()')
        assert page.locator('#refreshProgress').get_attribute('aria-valuenow')=='100'
        page.wait_for_timeout(400)
        assert page.locator('#refreshProgress').is_hidden()
        page.evaluate('SalesRefreshProgress.start()')
        page.emulate_media(media='print')
        assert page.locator('#refreshProgress').is_hidden()
        page.emulate_media(media='screen')
        page.evaluate('SalesRefreshProgress.fail()')
        assert page.locator('#refreshProgress').is_hidden()
        browser.close()
    (output/'waiting-browser-results.json').write_text(json.dumps({'synthetic_only':True,'waiting_frames':[a,b],'reduced':reduced,'measured':measured,'geometry':geometry,'completion_hidden':True,'print_hidden':True,'failure_hidden':True},indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
