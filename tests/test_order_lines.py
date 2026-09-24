"""Order detail is explanatory only: never rewrite the weekly accounting."""
import copy
import datetime as dt
from pathlib import Path
import scripts.sales_sync as sync


def fixture():
    order = dict(sop='O1', status='open', created_date='2026-09-21', salesperson='A', subtotal=150, line_items=3, stock_total=100, stock_cost=200)
    base = dict(sop='O1', status='open', component_sequence=0, quantity=2.5, uom='EA', item_class='MISC', category_1='', description='Part <test>')
    lines = [base | dict(line_sequence=1, item='7518', item_type=1, sales=100, raw_cost=-200),
             base | dict(line_sequence=2, item='FREIGHT', item_type=5, sales=50, raw_cost=0),
             base | dict(line_sequence=3, item='A', item_type=None, sales=0, raw_cost=25)]
    return order, lines


def test_detail_preserves_all_lines_signs_and_existing_stock_policy():
    order, lines = fixture()
    before = copy.deepcopy(lines)
    result = sync.build_weekly_order_lines(lines)['open:O1']
    assert lines == before
    assert len(result['lines']) == 3
    first, freight, unknown = result['lines']
    assert first['raw_cost'] == -200 and first['cost'] == 200
    assert first['profit'] == -100 and first['margin_pct'] == -100
    assert first['included_in_stock'] is True
    assert 'negative_source_cost' in first['flags']
    assert 'cost_over_sales' in first['flags']
    assert 'margin_screen_excluded' in first['flags']
    assert freight['included_in_stock'] is False
    assert unknown['margin_pct'] is None
    assert 'item_type_missing' in unknown['flags']
    assert first['quantity'] == 2.5 and first['uom'] == 'EA'
    assert result['stock_total'] == order['stock_total']
    assert result['stock_profit'] == order['stock_total'] - order['stock_cost']


def test_line_identity_keeps_components_and_status_separate():
    _, lines = fixture()
    lines += [lines[0] | dict(component_sequence=1), lines[0] | dict(status='history')]
    result = sync.build_weekly_order_lines(lines)
    assert len(result['open:O1']['lines']) == 4
    assert len(result['history:O1']['lines']) == 1


def test_attaching_details_never_changes_existing_weekly_totals():
    order, lines = fixture()
    original = sync.build_weekly_reports([order], dt.date(2026,9,21))
    enriched = sync.build_weekly_reports([order], dt.date(2026,9,21), line_rows=lines)
    fields = enriched.pop('order_line_fields')
    details = enriched.pop('order_lines')
    decoded = [dict(zip(fields, row)) for row in details['open:O1']['lines']]
    assert decoded == sync.build_weekly_order_lines(lines)['open:O1']['lines']
    assert original == enriched
    assert details['open:O1']['stock_profit'] == -100


def test_line_query_uses_same_deduped_header_scope_and_explicit_keys():
    sql = sync.WEEKLY_ORDER_LINE_SQL
    for token in ('h.rn = 1', 'h.SOPTYPE = l.SOPTYPE', 'l.SOPNUMBE', 'l.CMPNTSEQ', 'l.QUANTITY', 'l.UOFM', 'i.ITEMTYPE', 'l.EXTDCOST', 'l.XTNDPRCE'):
        assert token in sql
    assert sync.WEEKLY_ORDER_SQL.split('), line_source AS (')[0] in sql


def test_empty_and_out_of_scope_details_do_not_add_orders():
    order, lines = fixture()
    empty = sync.build_weekly_reports([], dt.date(2026,9,21), line_rows=lines)
    assert empty['order_lines'] == {}
    assert empty['order_line_fields'] == []
    today_only = sync.build_weekly_reports([order], dt.date(2026,9,21), week_count=0, line_rows=lines)
    assert len(today_only['order_lines']['open:O1']['lines']) == 3


def test_zero_and_negative_sales_margins_and_signed_quantities():
    _, lines = fixture()
    result = sync.build_weekly_order_lines([lines[0] | dict(sales=0, raw_cost=5, quantity=-2),
                                          lines[1] | dict(sales=-10, raw_cost=-15)])['open:O1']['lines']
    assert result[0]['margin_pct'] is None
    assert result[0]['quantity'] == -2
    assert result[0]['profit'] == -5
    assert 'nonpositive_sales_with_cost' in result[0]['flags']
    assert result[1]['sales'] == -10
    assert result[1]['raw_cost'] == -15
    assert result[1]['profit'] == -25


def test_frontend_exposes_accessible_lazy_detail_with_legacy_fallback():
    html = (Path(__file__).resolve().parents[1] / 'index.html').read_text(encoding='utf-8')
    for token in ('VERSION 1.17', 'data-weekly-order', 'aria-expanded', 'toggleWeeklyOrder', 'renderWeeklyOrderLines', 'Line detail unavailable', 'Stock contribution', 'Source cost', 'No lines are removed', 'esc(line.description)', "esc(line.item||'No item ID')", 'weeklyOrders.onclick'):
        assert token in html
