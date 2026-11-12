from scripts import sales_sync as s
import pytest
from copy import deepcopy


@pytest.mark.parametrize('person', ['Neil','Walter','Dylan','Russell','Other'])
@pytest.mark.parametrize('kind,source_sign', [('Invoice',1),('Return',1),('Return',-1)])
def test_multiple_lines_returns_rounding_all_people(person, kind, source_sign):
    h = header(sales=source_sign * 100.02, extended_cost=0, salesperson=person, kind=kind)
    ls = [dict(line(sales=source_sign * 100.01,cost=0),kind=kind), dict(line(sales=source_sign * .01,cost=0,seq=2),kind=kind)]
    before = deepcopy(ls)
    rows, policy = apply([h],ls)
    sign = -1 if kind == 'Return' else 1
    assert s.normalize_transaction(rows[0])['cost'] == sign * 50.02
    assert ls == before
    assert policy['documents'][0]['cost_added'] == sign * 50.02


@pytest.mark.parametrize('sales,expected', [(0,0),(-.01,-.01),(-100,-50)])
def test_nonpositive_source_extended_sales(sales,expected):
    rows, _ = apply([header(sales=sales,extended_cost=0)], [line(sales=sales,cost=0)])
    assert rows[0]['extended_cost'] == expected
    assert s.normalize_transaction(rows[0])['cost'] == expected


@pytest.mark.parametrize('included', [0, 70, 100])
def test_header_bridge_incorporation_idempotence_and_previous_adjustments(included):
    h = header(extended_cost=40+included)
    h.update(gp_extended_cost=40+included,extended_cost=30+included)  # earlier correction preserved
    ls = [line(sales=200,cost=70),line('STOCK',100,40,2)]
    rows,p = apply([h],ls)
    assert rows[0]['extended_cost'] == 130
    again,q = apply(rows,ls)
    assert again == rows
    assert q == p


@pytest.mark.parametrize('case,reason', [('missing', 'missing_lines'), ('incomplete','incomplete_line_sales'), ('duplicate','duplicate_line_identity')])
def test_missing_or_incomplete_evidence(case,reason):
    lines = {'missing': [], 'incomplete': [line(sales=200)], 'duplicate': [line(sales=150),line(sales=150)]}[case]
    h=header()
    rows,p = apply([h],lines)
    assert rows == [h]
    assert p['exceptions'][0]['reason'] == reason


def test_unrelated_literal_scope():
    h=header()
    rows,p = apply([h],[line('17518',300,40)])
    assert rows == [h] and not p['documents']



@pytest.mark.parametrize('missing', ['sales','raw_cost','line_sequence','component_sequence'])
def test_incomplete_line_fields_fail_closed(missing):
    ls=[line(sales=200),line('STOCK',100,40,2)]
    del ls[0][missing]
    rows,p=apply([header()],ls)
    assert rows == [header()]
    assert p['exceptions'][0]['reason'] == 'missing_line_evidence'


def test_discount_uses_extended_not_quantity_or_unit_price():
    ls=[dict(line(sales=81.01,cost=0),quantity=100,unit_price=500)]
    rows,_=apply([header(sales=81.01,extended_cost=0)],ls)
    assert rows[0]['extended_cost'] == 40.51


def test_negative_source_return_header():
    h=header(kind='Return',sales=-200,extended_cost=-40)
    ls=[dict(line(sales=-100,cost=0),kind='Return'),dict(line('STOCK',-100,-40,2),kind='Return')]
    rows,_=apply([h],ls)
    assert s.normalize_transaction(rows[0])['cost'] == -90


def test_integration_and_disclosure_contract():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    sync = (root/'scripts/sales_sync.py').read_text()
    assert sync.index('transaction_rows, misc_item_policy = apply_misc_item_policy') < sync.index('snapshot = build_snapshot(transaction_rows)')
    assert "snapshot['misc_item_policy'] = misc_item_policy" in sync
    html = (root/'index.html').read_text()
    assert 'VERSION 1.40' in html
    assert 'Management estimate, not supplier actual' in html
    assert 'misc_item_policy' in html
    assert 'misc_item_policy' in (root/'invoice-drilldown.js').read_text()
    assert "[Document Date] >= '2021-01-01'" in s.INVOICE_LINE_SQL
    assert 'WHERE t.rn = 1' in s.INVOICE_LINE_SQL


def header(**kw):
    return dict(dict(sop='X', kind='Invoice', document_date='2023-01-01', salesperson='ANY', sales=300, extended_cost=40), **kw)


def line(item='7518', sales=100, cost=999, seq=1):
    return dict(sop='X', kind='Invoice', item=item, sales=sales, raw_cost=cost, line_sequence=seq, component_sequence=0)


def apply(rows, lines):
    return getattr(s, 'apply_misc_item_policy', lambda r,l:(r, {}))(rows, lines)


def test_7518_uses_half_extended_sales_not_half_source_cost():
    rows, policy = apply([header()], [line(sales=200), line('STOCK',100,40,2)])
    assert rows[0]['extended_cost'] == 140
    assert policy['documents'][0]['cost_added'] == 100


@pytest.mark.parametrize('case', ['missing_current', 'null_current', 'null_original'])
def test_missing_header_cost_evidence_fails_closed(case):
    h = header(sales=100, extended_cost=0)
    if case == 'missing_current':
        del h['extended_cost']
    elif case == 'null_current':
        h['extended_cost'] = None
    else:
        h['gp_extended_cost'] = None
    rows, policy = apply([h], [line(sales=100, cost=0)])
    assert rows == [h]
    assert policy['exceptions'][0]['reason'] == 'missing_header_cost_evidence'
    assert not policy['documents']


@pytest.mark.parametrize('mixed', [False, True])
def test_negative_invoice_cost_evidence_fails_closed(mixed):
    h = header(sales=-100, extended_cost=-50)
    ls = [line(sales=-100, cost=-50)]
    if mixed:
        h = header(sales=100, extended_cost=30)
        ls = [line(sales=-100, cost=-50), line('STOCK', 200, 80, 2)]
    rows, policy = apply([h], ls)
    assert rows == [h]
    assert policy['exceptions'][0]['reason'] == 'unsupported_negative_invoice_cost'
    assert not policy['documents']


def test_ambiguous_header_fails_closed():
    source = header(extended_cost=77)
    rows, policy = apply([source], [line(sales=200), line('STOCK',100,40,2)])
    assert rows == [source]
    assert policy['exceptions'][0]['reason'] == 'ambiguous_header_cost'
