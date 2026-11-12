from copy import deepcopy
from scripts import sales_sync as s
from test_misc_item_policy import header, line


def test_inconsistent_finite_cached_before_cost_is_not_trusted():
    h = header(salesperson='JOSH', extended_cost=130)
    h['_misc_7518_bridge'] = dict(kind='Invoice', sop=h['sop'], cost=130, cost_added=100, pre_misc_extended_cost=99999)
    ls = [dict(line('7518', 200, 0), description='Above All For'), line('STOCK', 100, 40, 2)]
    original = deepcopy(h)
    rows, policy = s.apply_misc_item_policy([h], ls)
    assert rows == [original]
    assert policy['exceptions'][0]['reason'] == 'josh_above_all_bundle_cached_cost_unverified'


def test_negative_source_return_retains_later_unrelated_cost_adjustment():
    h = header(salesperson='JOSH', kind='Return', sales=-300, extended_cost=-30, gp_extended_cost=-40)
    ls = [dict(line('7518', -200, 0), kind='Return'), dict(line('STOCK', -100, -40, 2), kind='Return')]
    estimated, _ = s.apply_misc_item_policy([h], ls)
    assert estimated[0]['extended_cost'] == 130
    estimated[0]['extended_cost'] += 7
    ls[1]['description'] = 'Above All For'
    rows, policy = s.apply_misc_item_policy(estimated, ls)
    assert rows[0]['extended_cost'] == -37
    assert s.normalize_transaction(rows[0])['cost'] == -37
    assert policy['exceptions'][0]['reason'] == 'josh_above_all_bundle_excluded'


def test_outer_underscores_are_bundle_punctuation():
    h = header(salesperson='JOSH')
    ls = [dict(line('7518', 200, 0), description='_Above_All_For_'), line('STOCK', 100, 40, 2)]
    rows, policy = s.apply_misc_item_policy([h], ls)
    assert rows == [h] and not policy['documents']
    assert policy['exceptions'][0]['reason'] == 'josh_above_all_bundle_excluded'
