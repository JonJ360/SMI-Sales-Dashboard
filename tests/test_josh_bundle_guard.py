"""Offline, narrowly scoped Josh bundle protection; no production IO."""
from copy import deepcopy

import pytest
from scripts import sales_sync as s
from test_misc_item_policy import header, line


@pytest.mark.parametrize('description', [
    'Above All For', 'Above For All', 'All the Above For',
    '  aBoVe\tALL---for: project', '(Above / For / All) job',
    'ALL, the ABOVE: FOR materials', 'Above_All_For',
])
@pytest.mark.parametrize('kind,source_sign', [('Invoice', 1), ('Return', 1), ('Return', -1)])
def test_exact_josh_bundle_holds_whole_document(description, kind, source_sign):
    h = header(salesperson='JOSH', kind=kind, sales=source_sign * 300,
               extended_cost=source_sign * 30, gp_extended_cost=source_sign * 40)
    ls = [dict(line('7518', source_sign * 200, 0), kind=kind),
          dict(line('STOCK', source_sign * 100, source_sign * 40, 2),
               kind=kind, description=description)]
    original = deepcopy((h, ls))
    rows, policy = s.apply_misc_item_policy([h], ls)
    assert rows == [h]  # Preserve earlier approved -10 adjustment, not original GP cost.
    assert not policy['documents']
    assert policy['exceptions'][0]['reason'] == 'josh_above_all_bundle_excluded'
    assert s.apply_misc_item_policy(rows, ls) == (rows, policy)
    assert (h, ls) == original
    expected_sign = -1 if kind == 'Return' else 1
    assert s.normalize_transaction(rows[0])['cost'] == expected_sign * 30


@pytest.mark.parametrize('kind,source_sign', [('Invoice', 1), ('Return', 1), ('Return', -1)])
def test_cached_bridge_is_reversed_without_losing_prior_adjustments(kind, source_sign):
    h = header(salesperson='JOSH', kind=kind, sales=source_sign * 300,
               extended_cost=source_sign * 30, gp_extended_cost=source_sign * 40)
    ls = [dict(line('7518', source_sign * 200, 0), kind=kind),
          dict(line('STOCK', source_sign * 100, source_sign * 40, 2), kind=kind)]
    estimated, _ = s.apply_misc_item_policy([h], ls)
    assert estimated[0]['extended_cost'] == 130
    ls[1]['description'] = 'Above All For project'
    rows, policy = s.apply_misc_item_policy(estimated, ls)
    assert rows[0]['extended_cost'] == h['extended_cost']
    assert '_misc_7518_bridge' not in rows[0]
    assert rows[0]['gp_extended_cost'] == h['gp_extended_cost']
    assert not policy['documents']
    assert policy['exceptions'][0]['reason'] == 'josh_above_all_bundle_excluded'
    assert s.apply_misc_item_policy(rows, ls) == (rows, policy)


@pytest.mark.parametrize('person,description', [
    ('JOSH', 'MISC MERCHANDISE'), ('JOSHK', 'Above All For'),
    ('OTHER', 'All the Above For'), ('JOSH', 'Above All'),
    ('JOSH', 'Above anything For All'), ('JOSH', 'NotAbove All For'),
    ('JOSH', 'Above All Forever'),
])
def test_no_blanket_salesperson_or_unknown_phrase_exemption(person, description):
    h = header(salesperson=person)
    ls = [dict(line('7518', 200, 0), description=description), line('STOCK', 100, 40, 2)]
    rows, policy = s.apply_misc_item_policy([h], ls)
    assert rows[0]['extended_cost'] == 140
    assert len(policy['documents']) == 1
    assert not policy['exceptions']
    assert s.apply_misc_item_policy(rows, ls) == (rows, policy)


@pytest.mark.parametrize('code', ['204100', '46300', 'RV41390'])
@pytest.mark.parametrize('kind,source_sign', [('Invoice', 1), ('Return', 1), ('Return', -1)])
def test_master_identified_merchandise_codes_keep_signed_estimate_guards(code, kind, source_sign):
    h = header(kind=kind, sales=source_sign * 100.01, extended_cost=0)
    ls = [dict(line(code, source_sign * 100.01, 0), kind=kind, description='MISC MERCHANDISE')]
    rows, policy = s.apply_misc_item_policy([h], ls)
    assert rows[0]['extended_cost'] == 50.01
    assert policy['version'] == 'misc-merchandise-management-v3'
    assert s.normalize_transaction(rows[0])['cost'] == (-50.01 if kind == 'Return' else 50.01)
    assert s.apply_misc_item_policy(rows, ls) == (rows, policy)
    bad, exceptions = s.apply_misc_item_policy([dict(h, extended_cost=77)], ls)
    assert bad == [dict(h, extended_cost=77)]
    assert exceptions['exceptions'][0]['reason'] == 'ambiguous_header_cost'


@pytest.mark.parametrize('code', ['087515', 'COMMENT', '911', 'SERIAL', 'PREPAID', '41393'])
def test_service_and_unapproved_codes_stay_outside_scope(code):
    h = header()
    rows, policy = s.apply_misc_item_policy([h], [line(code, 300, 40)])
    assert rows == [h]
    assert not policy['documents']


@pytest.mark.parametrize('kind', ['Invoice', 'Return'])
def test_legacy_cached_delta_preserves_other_approved_adjustments(kind):
    h = header(salesperson='JOSH', kind=kind, extended_cost=30, gp_extended_cost=40)
    ls = [dict(line('7518', 200, 0), kind=kind), dict(line('STOCK', 100, 40, 2), kind=kind)]
    estimated, _ = s.apply_misc_item_policy([h], ls)
    estimated[0]['_misc_7518_bridge'].pop('pre_misc_extended_cost')
    # A later approved, unrelated correction also must survive reversal.
    estimated[0]['extended_cost'] += 7
    ls[1]['description'] = 'All the Above For project'
    rows, policy = s.apply_misc_item_policy(estimated, ls)
    assert rows[0]['extended_cost'] == 37
    assert '_misc_7518_bridge' not in rows[0]
    assert s.normalize_transaction(rows[0])['cost'] == (-37 if kind == 'Return' else 37)
    assert s.apply_misc_item_policy(rows, ls) == (rows, policy)


@pytest.mark.parametrize('code', ['204100', '46300', 'RV41390'])
@pytest.mark.parametrize('header_cost,expected_cost', [(40, 140), (65, 140), (140, 140)])
def test_additional_codes_only_replace_proven_header_component(code, header_cost, expected_cost):
    h = header(extended_cost=header_cost)
    ls = [dict(line(code, 200, 25), description='MISC MERCHANDISE'), line('STOCK', 100, 40, 2)]
    rows, policy = s.apply_misc_item_policy([h], ls)
    assert rows[0]['extended_cost'] == expected_cost
    assert policy['documents'][0]['cost_added'] == expected_cost - header_cost


@pytest.mark.parametrize('code', ['204100', '46300', 'RV41390'])
def test_additional_codes_keep_nonmerchandise_and_supplier_guards(code):
    h = header()
    ls = [dict(line(code, 300, 0), description='LABOR - DOORS')]
    rows, policy = s.apply_misc_item_policy([h], ls)
    assert rows == [h]
    assert policy['exceptions'][0]['reason'] == 'nonmerchandise_target_line'
    reserved = dict(h, sop='00777490')
    rows, policy = s.apply_misc_item_policy([reserved], [dict(ls[0], sop='00777490')])
    assert rows == [reserved]
    assert policy['exceptions'][0]['reason'] == 'reserved_existing_direct_cost_policy'


def test_unverifiable_cached_cost_is_not_guessed():
    h = header(salesperson='JOSH', extended_cost=130,
               _misc_7518_bridge={'kind': 'Invoice', 'sop': '1'})
    ls = [dict(line('7518', 300, 0), description='Above All For')]
    rows, policy = s.apply_misc_item_policy([h], ls)
    assert rows == [h]
    assert not policy['documents']
    assert policy['exceptions'][0]['reason'] == 'josh_above_all_bundle_cached_cost_unverified'

