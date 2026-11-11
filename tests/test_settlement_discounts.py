from pathlib import Path
import importlib.util
import pytest

MODULE=Path(__file__).parents[1]/'scripts/settlement_discounts.py'

def load():
    assert MODULE.exists(), 'Approved settlement-discount attribution is not implemented'
    spec=importlib.util.spec_from_file_location('settlement_discounts',MODULE)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def fixture():
    a=dict(lifecycle='history',customer='CUSTOMER',invoice='00123456',invoice_type=1,payment='RECEIPT',payment_type=9,amount='98.00',discount='2.00',actual_discount='2.00',invoice_date='2026-02-01',payment_date='2026-02-10',invoice_posting_date='2026-02-01',payment_posting_date='2026-02-10',posted=1,row_id=1)
    g=dict(source_table='GL20000',fiscal_year=2026,row_id=10,journal=123,source='CRJ',customer='CUSTOMER',payment='RECEIPT',payment_type=9,cost='2.00',date='2026-02-10')
    s=dict(sop='00123456',type=3,customer_id='CUSTOMER',customer='Customer',salesperson='PERSON',date='2026-02-01',sales='100.00',raw_cost='50.00',voided=0)
    i=dict(customer='CUSTOMER',type=1,document='00123456',date='2026-02-01',salesperson='PERSON',sales='100.00',cost='50.00',voided=0)
    p=dict(customer='CUSTOMER',type=9,document='RECEIPT',date='2026-02-10',salesperson='',sales='0.00',cost='0.00',voided=0)
    row=dict(sop='00123456',kind='Invoice',document_date='2026-02-01',customer='Customer',salesperson='PERSON',location='FARGO',sales=100,extended_cost=50)
    approved=[dict(source_application=a,baseline_invoice_cost='50.00',invoice='00123456',customer_id='CUSTOMER',salesperson='PERSON',invoice_date='2026-02-01',amount='2.00')]
    from copy import deepcopy
    i.update(original_amount='100.00',source='SALE');p.update(original_amount='100.00',source='CASH')
    approved[0].update(source_GL_rows=deepcopy([g]),source_sop=deepcopy(s),source_rm_invoice=deepcopy(i),source_rm_payment=deepcopy(p))
    evidence=dict(apps=[a],gl=[g],sop=[s],rm=[i,p])
    return row,approved,evidence

def test_exact_supported_discount_updates_cost_once_and_preserves_source():
    m=load();row,approved,e=fixture();out,policy=m.apply([row],approved,e)
    assert out[0]['extended_cost']==52
    assert row['extended_cost']==50
    assert out[0]['gp_extended_cost']==50
    assert policy['cost_added']==2
    assert policy['documents'][0]['salesperson']=='PERSON'
    twice,p2=m.apply(out,approved,e)
    assert twice==out and p2['cost_added']==2

@pytest.mark.parametrize('case', ['owner','customer','invoice_void','payment_void','sop_void','date','raw_cost','sales','unposted','amount','GL_cent','GL_reversal','already_in_header','missing_payment','duplicate_SOP','wrong_type'])
def test_changed_evidence_withholds_instead_of_guessing(case):
    from copy import deepcopy
    m=load();row,approved,e=fixture();e=deepcopy(e)
    if case=='owner':e['sop'][0]['salesperson']='OTHER'
    if case=='customer':e['sop'][0]['customer_id']='OTHER'
    if case=='invoice_void':e['rm'][0]['voided']=1
    if case=='payment_void':e['rm'][1]['voided']=1
    if case=='sop_void':e['sop'][0]['voided']=1
    if case=='date':e['sop'][0]['date']='2026-02-02'
    if case=='raw_cost':e['sop'][0]['raw_cost']='51.00'
    if case=='sales':e['sop'][0]['sales']='101.00'
    if case=='unposted':e['apps'][0]['posted']=0
    if case=='amount':e['apps'][0]['actual_discount']='2.01'
    if case=='GL_cent':e['gl'][0]['cost']='2.01'
    if case=='GL_reversal':e['gl'].append({**e['gl'][0],'source':'RMJ','row_id':11,'cost':'-2.00'})
    if case=='already_in_header':row['extended_cost']=52;e['sop'][0]['raw_cost']='52.00';e['rm'][0]['cost']='52.00'
    if case=='missing_payment':e['rm']=e['rm'][:1]
    if case=='duplicate_SOP':e['sop'].append(dict(e['sop'][0]))
    if case=='wrong_type':e['apps'][0]['payment_type']=7
    out,policy=m.apply([row],approved,e)
    assert out==[row]
    assert policy['cost_added']==0 and policy['exceptions']

def test_collect_reuses_connection_and_fetches_all_source_contracts(monkeypatch):
    import sys
    monkeypatch.syspath_prepend(str(MODULE.parent))
    m=load();assert hasattr(m,'collect'), 'Live source collection is missing'
    row,approved,e=fixture()
    class Cursor:
        def __init__(self):self.datasets=iter([e['apps'],e['gl'],e['sop'],e['rm']])
        def execute(self,sql,*params):
            assert sql.lstrip().upper().startswith(('SELECT','WITH'))
            if 'FROM dbo.RM20101 WHERE DOCNUMBR IN' in sql:
                assert 'CAST(? AS char(21))' in sql, 'Unicode parameters must not force full RM scans'
            self.data=next(self.datasets);self.description=[(k,) for k in self.data[0]];return self
        def fetchmany(self,n):return [tuple(r.values()) for r in self.data][:n]
        def close(self):pass
    class Connection:
        def cursor(self):return Cursor()
    assert m.collect(Connection())==e


def test_settlement_policy_is_disclosed_in_invoice_detail():
    root=MODULE.parents[1]
    ui=(root/'invoice-drilldown.js').read_text(encoding='utf-8')
    assert 'settlement_discount_policy' in ui
    assert 'Payment discount' in ui
    assert '${settlementNote}' in ui


def test_same_lifecycle_duplicate_fails_closed():
    from copy import deepcopy
    m=load();row,approved,e=fixture();e['apps'].append(deepcopy(e['apps'][0]))
    with pytest.raises(ValueError,match='duplicate'):
        m.apply([row],approved,e)
