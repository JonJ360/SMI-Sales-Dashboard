import datetime as dt
from scripts import sales_sync as s


def row(kind='Invoice', cost=0, sales=1000):
    return dict(sop='X', document_date='2026-10-01', customer='C', salesperson='ANYONE', location='BIS', kind=kind, sales=sales, extended_cost=cost)


def line(item='GROUND HEATER RENTAL', description='4 WEEK HEATER RENTAL', sales=1000, cost=700):
    return dict(sop='X', kind='Invoice', line_sequence=1, component_sequence=0, item=item, description=description, sales=sales, raw_cost=cost)


def apply(rows, lines):
    fn=getattr(s, 'apply_rental_policy', lambda rows, lines:(rows, {}))
    return fn(rows, lines)


def test_rental_normal_cost_automatically_applies_without_person_or_invoice_override():
    rows, policy=apply([row()], [line()])
    assert s.normalize_transaction(rows[0])['profit']==300
    assert policy['version']=='rental-management-v1'
    assert policy['documents'][0]['gp_cost']==0
    assert policy['documents'][0]['rental_cost_added']==700


def test_repair_recovery_and_expense_stay_out_of_performance():
    rows, policy=apply([row(sales=1100)], [line(), line(description='REPAIRS ON HEATER RENTAL',sales=100,cost=120)])
    actual=s.normalize_transaction(rows[0])
    assert actual['sales']==1000
    assert actual['cost']==700
    assert actual['profit']==300
    assert policy['documents'][0]['repair_cost_excluded']==120


def test_already_costed_rental_is_not_double_counted():
    rows, policy=apply([row(cost=700)], [line()])
    assert s.normalize_transaction(rows[0])['cost']==700
    assert not policy['exceptions']


def test_ambiguous_header_is_not_guessed():
    rows, policy=apply([row(cost=200)], [line()])
    assert s.normalize_transaction(rows[0])['cost']==200
    assert policy['exceptions'][0]['reason']=='ambiguous_header_cost'


def test_return_reverses_same_policy_and_leaves_source_lines_unchanged():
    source=line();source['kind']='Return';before=dict(source)
    rows, policy=apply([row(kind='Return')], [source])
    assert s.normalize_transaction(rows[0])['profit']==-300
    assert source==before


def test_zero_sales_cost_document_is_preserved_and_negative_cost_is_not_estimated():
    rows, policy=apply([row(sales=0)], [line(sales=0,cost=700)])
    assert s.normalize_transaction(rows[0])['profit']==-700
    rows, policy=apply([row()], [line(cost=-700)])
    assert s.normalize_transaction(rows[0])['cost']==0
    assert policy['exceptions'][0]['reason']=='negative_rental_source_cost'


def test_unrelated_items_remain_identical_and_unknown_rental_code_is_flagged():
    r=row(cost=20); rows,policy=apply([r], [line(item='WIDGET',description='Widget',cost=20)])
    assert rows==[r]
    rows,policy=apply([r], [line(item='NEW RENTAL',description='GROUND HEATER RENTAL')])
    assert rows==[r]
    assert policy['exceptions'][0]['reason']=='unmapped_rental_item'


def test_policy_source_covers_prior_years_independent_of_drilldown_window():
    assert "t.document_date >= '2024-01-01'" not in s.INVOICE_LINE_SQL
    r=row(sales=1100);r['document_date']='2023-10-01'
    rows,policy=apply([r],[line(),line(description='REPAIR HEATER',sales=100,cost=120)])
    assert s.normalize_transaction(rows[0])['profit']==300
    detail=s.build_invoice_drilldown(rows,[],dt.date(2026,11,3))
    assert not detail['documents']


def test_repair_included_header_cost_is_removed_without_adding_rental_twice():
    rows,policy=apply([row(cost=820,sales=1100)], [line(),line(description='HEATER REPAIR',sales=100,cost=120)])
    actual=s.normalize_transaction(rows[0])
    assert (actual['sales'],actual['cost'],actual['profit'])==(1000,700,300)
    assert policy['documents'][0]['rental_cost_added']==0


def test_mixed_normal_items_and_signed_repair_return():
    rows,policy=apply([row(cost=50,sales=1200)], [line(),line(item='WIDGET',description='widget',sales=100,cost=50),line(description='HEATER REPAIR',sales=100,cost=120)])
    actual=s.normalize_transaction(rows[0]);assert (actual['sales'],actual['cost'])==(1100,750)
    ls=[line(),line(description='HEATER REPAIR',sales=100,cost=120)]
    for l in ls:l['kind']='Return';l['sales']=-l['sales']
    rows,policy=apply([row(kind='Return',sales=-1100)],ls)
    actual=s.normalize_transaction(rows[0]);assert (actual['sales'],actual['cost'],actual['profit'])==(-1000,-700,-300)
