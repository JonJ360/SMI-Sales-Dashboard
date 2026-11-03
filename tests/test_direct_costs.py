from scripts import sales_sync as s


def test_approved_expedite_cost_is_added_once_preserving_gp():
    rows=[dict(sop='00777490',kind='Invoice',document_date='2026-04-01',salesperson='RUSSELL',sales=112390.87,extended_cost=84292.50)]
    lines=[dict(sop='00777490',kind='Invoice',item='41381',line_sequence=360448,quantity=1,raw_cost=16000)]
    evidence=[dict(po_count=1,bill_count=1,receipt_count=1,gl_count=3,gl_invalid=0,gl_balance=0,gl_cost=16000,inventory_count=1,accrual_count=1)]
    fn=getattr(s,'apply_approved_direct_costs',lambda r,l,e:(r,{}))
    adjusted,policy=fn(rows,lines,evidence)
    assert adjusted[0]['extended_cost']==100292.50
    assert adjusted[0]['gp_extended_cost']==84292.50
    assert policy['documents'][0]['cost_added']==16000


def test_changed_inventory_or_accrual_counterpart_is_rejected():
    row=dict(sop='00777490',kind='Invoice',document_date='2026-04-01',sales=112390.87,extended_cost=84292.50)
    line=dict(sop='00777490',kind='Invoice',item='41381',line_sequence=360448,quantity=1,raw_cost=16000)
    good=dict(po_count=1,bill_count=1,receipt_count=1,gl_count=3,gl_invalid=0,gl_balance=0,gl_cost=16000,inventory_count=1,accrual_count=1)
    for bad in [dict(good,inventory_count=0),dict(good,accrual_count=0)]:
        adjusted,p=s.apply_approved_direct_costs([row],[line],[bad])
        assert adjusted==[row] and p['exceptions']


def test_changed_missing_or_void_evidence_leaves_cost_unchanged_with_exception():
    row=dict(sop='00777490',kind='Invoice',document_date='2026-04-01',sales=112390.87,extended_cost=84292.50)
    line=dict(sop='00777490',kind='Invoice',item='41381',line_sequence=360448,quantity=1,raw_cost=16000)
    good=dict(po_count=1,bill_count=1,receipt_count=1,gl_count=3,gl_invalid=0,gl_balance=0,gl_cost=16000,inventory_count=1,accrual_count=1)
    for evidence in [[],[dict(good,gl_invalid=1)],[dict(good,bill_count=0)],[dict(good,gl_cost=15000)],[dict(good,gl_balance=10)]]:
        adjusted,p=s.apply_approved_direct_costs([row],[line],evidence)
        assert adjusted==[row] and len(p['exceptions'])==1
    adjusted,p=s.apply_approved_direct_costs([row],[],[good])
    assert adjusted==[row] and p['exceptions']


def test_no_double_cost_and_other_items_people_and_returns_unchanged():
    row=dict(sop='00777490',kind='Invoice',document_date='2026-04-01',sales=112390.87,extended_cost=100292.50)
    line=dict(sop='00777490',kind='Invoice',item='41381',line_sequence=360448,quantity=1,raw_cost=16000)
    good=dict(po_count=1,bill_count=1,receipt_count=1,gl_count=3,gl_invalid=0,gl_balance=0,gl_cost=16000,inventory_count=1,accrual_count=1)
    others=[dict(row,sop='00783997'),dict(row,sop='00781301'),dict(row,sop='00783542'),dict(row,kind='Return')]
    adjusted,p=s.apply_approved_direct_costs([row]+others,[line],[good])
    assert adjusted==[row]+others and not p['exceptions'] and not p['documents']
