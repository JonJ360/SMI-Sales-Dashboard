import datetime as dt
from pathlib import Path
import scripts.sales_sync as s


def rows():
    base = dict(document_date='2026-09-01', salesperson='RUSSELL', customer='Customer', location='01')
    return [base | dict(sop='0001', kind='Invoice', sales=100, extended_cost=-250),
            base | dict(sop='0001', kind='Return', sales=20, extended_cost=10),
            base | dict(sop='old', kind='Invoice', document_date='2023-01-01', sales=1, extended_cost=0)]


def test_documents_preserve_existing_net_math_and_type_identity():
    source = rows()
    result = s.build_invoice_drilldown(source, [], dt.date(2026,9,24))
    docs = [dict(zip(result['document_fields'], row)) for row in result['documents']]
    assert len(docs) == 2
    assert {d['key'] for d in docs} == {'Invoice:0001', 'Return:0001'}
    assert sum(d['sales'] for d in docs) == 80
    assert sum(d['cost'] for d in docs) == 240
    assert sum(d['profit'] for d in docs) == -160
    assert all(d['line_count'] == 0 for d in docs)
    assert docs[0]['raw_cost'] == -250
    assert docs[0]['margin_pct'] == -150


def test_all_lines_kept_without_stock_exclusions_and_residual_exposed():
    line = dict(kind='Invoice', sop='0001', line_sequence=1, component_sequence=0, item='FREIGHT', description='<unsafe>', quantity=1, uom='EA', sales=90, raw_cost=-200)
    result = s.build_invoice_drilldown(rows(), [line, line | dict(component_sequence=1,sales=0,raw_cost=25), line | dict(sop='outside')], dt.date(2026,9,24))
    doc = dict(zip(result['document_fields'], result['documents'][0]))
    lines = [dict(zip(result['line_fields'], l)) for l in result['lines'][doc['key']]]
    assert len(lines) == 2
    assert lines[0]['raw_cost'] == -200 and lines[0]['cost'] == 200
    assert lines[0]['profit'] == -110 and lines[1]['margin_pct'] is None
    assert doc['sales_difference'] == 10 and doc['cost_difference'] == 25
    assert doc['profit_difference'] == -15
    assert set(result['lines']) == {'Invoice:0001'}


def test_return_lines_sign_and_source_amounts():
    line = dict(kind='Return',sop='0001',sales=20,raw_cost=-10)
    result = s.build_invoice_drilldown(rows(), [line], dt.date(2026,9,24))
    got = dict(zip(result['line_fields'],result['lines']['Return:0001'][0]))
    assert (got['sales'],got['cost'],got['profit'],got['raw_cost']) == (-20,-10,-10,-10)


def test_query_reuses_exact_posted_normal_population_and_type_join():
    sql = s.INVOICE_LINE_SQL
    for token in (s.TRANSACTION_SQL.split('SELECT sop, document_date')[0], 't.rn = 1', "t.document_date >= '2024-01-01'", 'l.SOPTYPE = CASE', 'l.SOPNUMBE', 'l.CMPNTSEQ', 'dbo.SOP30300'):
        assert token in sql
    assert 'SOP10200' not in sql


def test_date_scope_matches_selectable_periods_and_keeps_zero_cost_losses():
    base = rows()[0]
    source = [base | dict(sop='old', document_date='2023-12-31'),
              base | dict(sop='first', document_date='2024-01-01', extended_cost=0),
              base | dict(sop='last', document_date='2026-09-24', sales=0, extended_cost=5),
              base | dict(sop='future', document_date='2026-09-25')]
    result = s.build_invoice_drilldown(source, [], dt.date(2026,9,24))
    docs = [dict(zip(result['document_fields'], r)) for r in result['documents']]
    assert [d['sop'] for d in docs] == ['first','last']
    assert docs[0]['profit'] == 100 and docs[0]['cost'] == 0
    assert docs[1]['profit'] == -5 and docs[1]['margin_pct'] is None
    assert docs[1]['line_count'] == 0 and docs[1]['cost_difference'] == 5


def test_negative_invoice_adjustment_lines_are_not_flipped_positive():
    line = dict(kind='Invoice', sop='0001', sales=-10, raw_cost=-5)
    result = s.build_invoice_drilldown(rows(), [line], dt.date(2026,9,24))
    d = dict(zip(result['line_fields'], result['lines']['Invoice:0001'][0]))
    assert (d['sales'], d['raw_cost'], d['cost'], d['profit']) == (-10,-5,5,-15)


def test_empty_detail_has_valid_transport():
    result = s.build_invoice_drilldown([], [], dt.date(2026,9,24))
    assert result['documents'] == [] and result['lines'] == {}
    assert result['document_fields'] == [] and result['line_fields'] == []


def test_frontend_contract():
    root = Path(__file__).resolve().parents[1]
    html = (root/'index.html').read_text(encoding='utf-8') + (root/'invoice-drilldown.js').read_text(encoding='utf-8')
    for token in ('renderSalespersonInvoices', 'data-invoice-index', 'toggleInvoice', 'invoiceDrilldown', 'Posted invoices', 'Posted returns', 'Header less lines', 'Invoice detail unavailable', 'Lowest profit first', 'invoicePage'):
        assert token in html
