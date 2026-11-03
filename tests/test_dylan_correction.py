from scripts import sales_sync as s


def dylan_fixture():
    row=dict(sop='00795214',kind='Invoice',document_date='2026-08-05',salesperson='DYLAN',sales=2244,extended_cost=237663.36)
    gl=[dict(journal=1469379,date='2026-08-05',account=a,debit=d,credit=c,voided=0,ledger=1,backout_journal=0,note='CJE TO CORRECT COSTS ON S1100 PO 96407 INVOICE 00795214') for a,d,c in [('119-00-00',235862.88,0),('410-00-00',0,235862.88)]]
    lines=[dict(sop='00795214',kind='Invoice',line_sequence=16384,item='S1100',quantity=132,raw_cost=237663.36)]
    return row,gl,lines


def test_dylan_corrected_once_not_twice():
    row,gl,lines=dylan_fixture()
    fn=getattr(s,'apply_verified_gl_corrections')
    if 'line_rows' in fn.__code__.co_varnames:
        adjusted,p=fn([row],gl,lines)
    else: adjusted,p=fn([row],gl)
    assert adjusted[0]['extended_cost']==1800.48
    assert adjusted[0]['gp_extended_cost']==237663.36
    assert p['documents'][0]['profit']==443.52
    assert p['documents'][0]['journal']==1469379


def test_duplicate_journal_does_not_add_a_second_correction():
    row,gl,lines=dylan_fixture()
    both=gl+[dict(g,journal=1471752,date='2026-09-09') for g in gl]
    adjusted,p=s.apply_verified_gl_corrections([row],both,lines)
    assert adjusted[0]['extended_cost']==1800.48
    assert p['documents'][0]['excluded_duplicate_journal']==1471752
    assert len(p['documents'])==1
    again,p=s.apply_verified_gl_corrections(adjusted,both,lines)
    assert again==adjusted and not p['documents'] and not p['exceptions']


def test_missing_changed_or_invalid_source_is_not_applied():
    row,gl,lines=dylan_fixture()
    for evidence in [[],gl[:1],[dict(gl[0],voided=1),gl[1]],[dict(gl[0],ledger=2),gl[1]],[dict(gl[0],account='OTHER'),gl[1]],[dict(gl[0],debit=235862),gl[1]],[dict(g,note='unrelated') for g in gl]]:
        adjusted,p=s.apply_verified_gl_corrections([row],evidence,lines)
        assert adjusted==[row] and p['exceptions']
    for wrong_lines in [[],[dict(lines[0],quantity=131)],[dict(lines[0],raw_cost=1)]]:
        adjusted,p=s.apply_verified_gl_corrections([row],gl,wrong_lines)
        assert adjusted==[row] and p['exceptions']


def test_other_documents_and_returns_are_unchanged():
    row,gl,lines=dylan_fixture()
    others=[dict(row,sop='OTHER'),dict(row,kind='Return')]
    adjusted,p=s.apply_verified_gl_corrections(others,gl,lines)
    assert adjusted==others and not p['documents'] and not p['exceptions']
