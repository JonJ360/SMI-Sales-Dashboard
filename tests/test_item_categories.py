"""Item categories preserve GP source labels; no description-based inference."""
import subprocess
from pathlib import Path
import scripts.sales_sync as s
ROOT = Path(__file__).resolve().parents[1]


def test_category_transport_preserves_master_values_and_rejects_ambiguous_ids():
    assert hasattr(s, 'build_item_categories'), 'Missing source item category transport'
    rows = [dict(item=' A ', item_class=' STEEL ', category_1=' 50 '),
            dict(item='B', item_class='TOOLS', category_1=''),
            dict(item='B', item_class='MISC', category_1=''),
            dict(item='', item_class='TOOLS', category_1='')]
    got = s.build_item_categories(rows)
    assert got['items'] == {'A': ['STEEL', '50']}
    assert got['ambiguous_items'] == ['B']
    assert got['source'] == 'SMI.dbo.IV00101'
    assert 'current' in got['basis']


def test_extraction_adds_categories_without_joining_or_changing_sales_sql():
    import inspect
    body = inspect.getsource(s.extract)
    assert 'cursor.execute(ITEM_CATEGORY_SQL)' in body
    assert 'snapshot["item_categories"] = build_item_categories(category_rows)' in body
    assert 'JOIN' not in s.ITEM_CATEGORY_SQL
    assert 'IV00101' not in s.INVOICE_LINE_SQL


def test_category_frontend_model_and_both_drawer_hooks():
    js = ROOT / 'item-categories.js'
    assert js.exists(), 'Missing shared top-five category model'
    result = subprocess.run(['node', '--test', 'tests/category-model.test.cjs'], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    assert 'src="item-categories.js?v=1.20"' in html
    assert "renderItemCategories('customer',name,view)" in html
    assert "renderItemCategories('salesperson',name,view)" in html
