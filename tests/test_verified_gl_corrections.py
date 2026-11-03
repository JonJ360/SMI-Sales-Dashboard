from scripts import sales_sync as s


def test_verified_posted_correction_reduces_cost_and_preserves_actuals():
    rows=[dict(sop='00786458',kind='Invoice',document_date='2026-06-11',customer='MATT',salesperson='WALTER',location='BIS',sales=2371,extended_cost=374049.50)]
    gl=[dict(journal=1452013,date='2026-06-11',account=a,debit=d,credit=c,voided=0,ledger=1,backout_journal=0,note='INVOICE 00786458 INCORRECT COST ON ITEM UD39514') for a,d,c in [('120-00-03',372559,0),('410-00-03',0,372559)]]
    fn=getattr(s,'apply_verified_gl_corrections',lambda r,g:(r,{}))
    adjusted,policy=fn(rows,gl)
    actual=s.normalize_transaction(adjusted[0])
    assert actual['profit']==880.50
    assert adjusted[0]['gp_extended_cost']==374049.50
    assert policy['documents'][0]['cost_reduction']==372559


def test_unsafe_or_missing_evidence_never_changes_source_cost():
    row=dict(sop='00786458',kind='Invoice',document_date='2026-06-11',sales=2371,extended_cost=374049.50)
    for evidence in [[],[dict(journal=1452013,date='2026-06-11',account='410-00-03',debit=0,credit=372559,voided=0,ledger=1,backout_journal=0,note='unrelated')]]:
        adjusted,policy=s.apply_verified_gl_corrections([row],evidence)
        assert adjusted==[row]
        assert policy['exceptions']


def test_already_reflected_correction_is_not_applied_twice_and_others_unchanged():
    row=dict(sop='00786458',kind='Invoice',document_date='2026-06-11',sales=2371,extended_cost=1490.50)
    gl=[dict(journal=1452013,date='2026-06-11',account=a,debit=d,credit=c,voided=0,ledger=1,backout_journal=0,note='INVOICE 00786458 INCORRECT COST ON ITEM UD39514') for a,d,c in [('120-00-03',372559,0),('410-00-03',0,372559)]]
    unrelated=dict(row,sop='OTHER',extended_cost=99)
    adjusted,policy=s.apply_verified_gl_corrections([row,unrelated],gl)
    assert adjusted==[row,unrelated]
    assert not policy['documents'] and not policy['exceptions']
    gl[0]['voided']=1
    original=dict(row,extended_cost=374049.50)
    adjusted,policy=s.apply_verified_gl_corrections([original],gl)
    assert adjusted==[original] and policy['exceptions']


def test_closed_year_source_remains_supported():
    assert 'dbo.GL20000' in s.VERIFIED_GL_CORRECTION_SQL
    assert 'dbo.GL30000' in s.VERIFIED_GL_CORRECTION_SQL
    assert 'g.HSTYEAR=2026' in s.VERIFIED_GL_CORRECTION_SQL
