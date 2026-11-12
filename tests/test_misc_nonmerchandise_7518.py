"""Merchandise-only scope includes 7518; stale estimates must not bypass it."""
from copy import deepcopy
import pytest
from scripts import sales_sync as s
from test_misc_item_policy import header, line

@pytest.mark.parametrize('description',['LABOR - DOORS','FREIGHT','RENTAL EQUIPMENT'])
@pytest.mark.parametrize('seller',['RICK','JOSH'])
@pytest.mark.parametrize('kind,orientation',[('Invoice',1),('Return',1),('Return',-1)])
def test_7518_nonmerchandise_preserves_source_cost(description,seller,kind,orientation):
    h=header(kind=kind,sales=orientation*300,extended_cost=orientation*40,salesperson=seller)
    ls=[dict(line('7518',orientation*300,orientation*40),kind=kind,description=description)]
    before=deepcopy((h,ls));rows,p=s.apply_misc_item_policy([h],ls)
    assert rows==[h] and not p['documents']
    assert p['exceptions'][0]['reason']=='nonmerchandise_target_line'
    assert (h,ls)==before

@pytest.mark.parametrize('kind,orientation',[('Invoice',1),('Return',1),('Return',-1)])
@pytest.mark.parametrize('later',[-7,7])
def test_new_nonmerchandise_scope_removes_only_old_estimate(kind,orientation,later):
    h=header(kind=kind,sales=orientation*300,extended_cost=orientation*30,
             gp_extended_cost=orientation*40,salesperson='RICK')
    ls=[dict(line('7518',orientation*200,orientation*10),kind=kind,description='MISC MERCHANDISE'),
        dict(line('STOCK',orientation*100,orientation*30,2),kind=kind)]
    cached,p=s.apply_misc_item_policy([h],ls);assert p['documents']
    cached[0]['extended_cost']+=later
    changed=deepcopy(ls);changed[0]['description']='FREIGHT'
    original=deepcopy(cached);rows,p=s.apply_misc_item_policy(cached,changed)
    assert rows[0]['extended_cost']==orientation*(30+later)
    assert rows[0]['gp_extended_cost']==orientation*40
    assert '_misc_7518_bridge' not in rows[0]
    assert not p['documents'] and p['exceptions'][0]['reason']=='nonmerchandise_target_line'
    assert cached==original

@pytest.mark.parametrize('cache',[{},[],None,'invalid'])
def test_nonmerchandise_malformed_cache_is_explicitly_unverified(cache):
    h=header(extended_cost=150);h['_misc_7518_bridge']=cache
    rows,p=s.apply_misc_item_policy([h],[dict(line('7518',300,0),description='FREIGHT')])
    assert rows==[h] and not p['documents']
    assert p['exceptions'][0]['reason']=='nonmerchandise_target_line_cached_cost_unverified'
