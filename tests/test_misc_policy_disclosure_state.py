from pathlib import Path
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1]
class Details(HTMLParser):
    def __init__(self): super().__init__();self.notes={}
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='details':self.notes[attrs.get('id')]=attrs

def test_miscellaneous_policy_starts_collapsed_without_removing_detail():
    html=(ROOT/'index.html').read_text(encoding='utf-8');p=Details();p.feed(html)
    assert 'miscPolicyNote' in p.notes,'Miscellaneous policy needs an identifiable closed disclosure'
    assert 'open' not in p.notes['miscPolicyNote']
    assert 'id="miscPolicyCounts"' in html
    assert 'id="miscPolicyStatus"' in html
    assert 'Management estimate, not supplier actual' in html
    assert 'Item 41393 (DO NOT USE) remains held.' in html
