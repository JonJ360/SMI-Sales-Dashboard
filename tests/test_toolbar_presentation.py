"""Guard the presentation-only release's unchanged inline financial/auth handlers."""
import hashlib
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# Expected inline-script hashes are pinned to the reviewed v1.42 release.
EXPECTED_INLINE = ['f2e726745a182f7f3ed8357c947714db763ad7ea03074d33a80fb3a087d56ef9', 'a4d61f21d617ba5000b53ee9b66068cc250af515d85bf4194fcb173d14bd24e0']
def test_toolbar_uses_original_controls_and_has_no_financial_mutations():
    js=(ROOT/'report-toolbar.js').read_text(encoding='utf-8')
    assert 'cloneNode' not in js
    assert '[...controls.children].forEach(node=>panel.append(node))' in js
    assert not re.search(r'(?:totals|state\.data)\.[\w.]+\s*=(?!=)',js)
    assert "currency.format(value||0)" in js
    assert 'requestAnimationFrame(fit)' in js
    assert 'aria-expanded' in js and "e.key==='Escape'" in js

def test_toolbar_asset_versions_and_no_duplicate_mobile_report_menu():
    html=(ROOT/'index.html').read_text(encoding='utf-8')
    assert 'VERSION 1.44' in html
    assert 'report-toolbar.css?v=1.44' in html
    assert 'report-toolbar.js?v=1.43' in html
    mobile=(ROOT/'executive-mobile.js').read_text(encoding='utf-8')
    assert "dialog('executiveReportsDialog'" not in mobile
    assert 'relocate(refresh,brand)' not in mobile

def test_inline_financial_and_auth_scripts_unchanged():
    html=(ROOT/'index.html').read_bytes().replace(b'\r\n',b'\n')
    scripts=re.findall(rb'<script>(.*?)</script>',html,re.S)
    assert [hashlib.sha256(script).hexdigest() for script in scripts]==EXPECTED_INLINE
