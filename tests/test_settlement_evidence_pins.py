from copy import deepcopy
from decimal import Decimal
import pytest
from test_settlement_discounts import fixture, load

@pytest.mark.parametrize('field,value', [('row_id',999),('date','2026-02-11'),('journal',999),('source_table','GL30000'),('origin','CHANGED')])
def test_same_net_replaced_GL_leg_withheld(field,value):
    m=load();row,a,e=fixture();e['gl'][0][field]=value
    out,p=m.apply([row],a,e)
    assert out==[row] and p['cost_added']==0 and p['exceptions']

@pytest.mark.parametrize('case',['sales','payment_amount','payment_owner','payment_source','invoice_source','signed_cost','sop_type','missing_pin'])
def test_coordinated_or_immutable_evidence_change_withheld(case):
    m=load();row,a,e=fixture()
    if case=='sales':row['sales']=101;e['sop'][0]['sales']='101.00';e['rm'][0]['sales']='101.00'
    if case=='payment_amount':e['rm'][1]['original_amount']='101.00'
    if case=='payment_owner':e['rm'][1]['salesperson']='OTHER'
    if case=='payment_source':e['rm'][1]['source']='OTHER'
    if case=='invoice_source':e['rm'][0]['source']='OTHER'
    if case=='signed_cost':e['sop'][0]['raw_cost']='-50.00';e['rm'][0]['cost']='-50.00'
    if case=='sop_type':e['sop'][0]['type']=4
    if case=='missing_pin':a[0].pop('source_GL_rows')
    out,p=m.apply([row],a,e)
    assert out==[row] and p['cost_added']==0 and p['exceptions']

def test_two_events_one_changed_withholds_whole_invoice():
    m=load();row,a,e=fixture();second=deepcopy(a[0]);second['source_application']['payment']='SECOND';second['source_application']['row_id']=2
    second['source_GL_rows'][0].update(payment='SECOND',row_id=11)
    second['source_rm_payment']['document']='SECOND';a.append(second)
    e['apps'].append(deepcopy(second['source_application']));e['gl'].extend(deepcopy(second['source_GL_rows']));e['rm'].append(deepcopy(second['source_rm_payment']))
    e['gl'][1]['date']='2026-02-11'
    out,p=m.apply([row],a,e)
    assert out==[row] and p['cost_added']==0 and p['exceptions']

def test_stale_enrichment_rolls_back_when_pin_changes():
    m=load();row,a,e=fixture();out,_=m.apply([row],a,e);e['gl'][0]['row_id']=99
    out,p=m.apply(out,a,e)
    assert out[0]['extended_cost']==50 and '_settlement_signature' not in out[0] and p['cost_added']==0

def test_cross_lifecycle_mirror_and_decimal_format_equivalence():
    m=load();row,a,e=fixture();e['apps'].append({**e['apps'][0],'lifecycle':'open','row_id':2})
    for r in e['rm']:
        r['lifecycle']='open';e['rm'].append({**r,'lifecycle':'history'})
        if len(e['rm'])==4:break
    e['gl'][0]['cost']=Decimal('2.00000');e['sop'][0]['sales']=Decimal('100.000')
    out,p=m.apply([row],a,e)
    assert out[0]['extended_cost']==52 and p['cost_added']==2 and not p['exceptions']

def test_return_excluded_even_with_matching_invoice_number():
    m=load();row,a,e=fixture();row['kind']='Return';e['gl'][0]['row_id']=99
    out,p=m.apply([row],a,e)
    assert out==[row] and p['cost_added']==0
