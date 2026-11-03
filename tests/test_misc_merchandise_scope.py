import pytest
from copy import deepcopy
from scripts import sales_sync as s
from tests.test_misc_item_policy import header, line

CODES = ['41381','41382','41384','41387','41388','41389','41390','41391','41392','7518']

@pytest.mark.parametrize('code', CODES)
def test_sydney_highlighted_merchandise_uses_existing_estimate(code):
    ls=[dict(line(code,200,999),description='MISC MERCHANDISE'),line('STOCK',100,40,2)]
    original=deepcopy(ls)
    rows,p=s.apply_misc_item_policy([header()],ls)
    assert rows[0]['extended_cost']==140
    assert ls==original
    assert set(p['item_codes'])==set(CODES)
    assert p['version']=='misc-merchandise-management-v2'

@pytest.mark.parametrize('code', ['41393','S1700','FREIGHT','087515','RV41390'])
def test_unapproved_or_retired_codes_unchanged(code):
    h=header();rows,p=s.apply_misc_item_policy([h],[line(code,300,40)])
    assert rows==[h] and not p['documents']

@pytest.mark.parametrize('description',['AMEX 1% CHARGE','CC FIX','FREIGHT AND SHOP DRAWING CHARGE','RENTAL TO PURCHASE','AMCON ENERGY SURCHARGE','LABOR - DOORS','EXPEDITING FEE'])
def test_reused_codes_do_not_estimate_nonmerchandise(description):
    h=header();rows,p=s.apply_misc_item_policy([h],[dict(line('41381',300,0),description=description)])
    assert rows==[h]
    assert p['exceptions'][0]['reason']=='nonmerchandise_target_line'


def test_approved_supplier_actual_allocation_takes_precedence():
    h=header(sop='00777490',sales=101000,extended_cost=100292.50,gp_extended_cost=84292.50)
    ls=[dict(line('41381',16000,16000),sop='00777490',description='EXPEDITING FEE')]
    rows,p=s.apply_misc_item_policy([h],ls)
    assert rows==[h]
    assert p['exceptions'][0]['reason']=='reserved_existing_direct_cost_policy'


def test_new_codes_mixed_with_7518_are_estimated_once_together():
    h=header(sales=400,extended_cost=40)
    ls=[line('41390',200,900),line('7518',100,999,2),line('STOCK',100,40,3)]
    rows,p=s.apply_misc_item_policy([h],ls)
    assert rows[0]['extended_cost']==190
    assert s.apply_misc_item_policy(rows,ls)==(rows,p)
