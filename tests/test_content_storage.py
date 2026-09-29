"""Lossless content storage: tests contain synthetic data only."""
import copy
import hashlib
import json

import pytest
from scripts.content_storage import build, restore, canonical, digest
from scripts.publish_snapshot import source_sha256


def sample():
    p = {'as_of': '2026-09-28', 'refreshed_at': '2026-09-28T00:00:00Z',
         'months': {'2025-01': {'sales': 12.5}, '2026-09': {'sales': -3.0}},
         'invoice_drilldown': {
             'document_fields': ['key', 'date', 'sales'], 'line_fields': ['item', 'cost'],
             'documents': [['I:2', '2026-09-02', -3.0], ['R:1', '2025-01-02', -1.25],
                           ['I:1', '2025-01-01', 13.75]],
             'lines': {'I:2': [['é😀', -0.0]], 'I:1': [['x', 10.0]]},
             'date_basis': 'document_date', 'start': '2024-01-01', 'end': '2026-09-28'},
         'other': {'null': None, 'boolean': True, 'empty': [], 'text': '\n"é'}}
    p['sha256'] = source_sha256(p)
    return p


def test_exact_canonical_roundtrip_and_determinism():
    p = sample()
    a = build(p)
    assert restore(a['recipe'], a['chunks']) == canonical(p)
    assert json.loads(restore(a['recipe'], a['chunks'])) == p
    assert a == build(copy.deepcopy(p))
    for h, text in a['chunks'].items():
        assert digest(text) == h
    assert digest(a['manifest_text']) == a['manifest_sha256']


def test_current_change_reuses_old_period_and_changed_history_versions():
    p = sample(); a = build(p)
    q = copy.deepcopy(p); q['invoice_drilldown']['documents'][0][2] = -5.0
    q['sha256'] = source_sha256(q); b = build(q)
    assert a['periods']['2025-01'] == b['periods']['2025-01']
    assert a['periods']['2026-09'] != b['periods']['2026-09']
    q['invoice_drilldown']['lines']['I:1'][0][1] = 11.0
    q['sha256'] = source_sha256(q); c = build(q)
    assert b['periods']['2025-01'] != c['periods']['2025-01']
    assert restore(a['recipe'], a['chunks']) == canonical(p)


def test_noncontiguous_months_and_missing_lines_preserve_order():
    p = sample(); p['invoice_drilldown']['documents'].append(['I:3', '2026-09-03', 1.0])
    p['sha256'] = source_sha256(p)
    b = build(p)
    assert json.loads(restore(b['recipe'], b['chunks'])) == p


def test_corruption_or_missing_chunk_rejected():
    b = build(sample()); h = next(iter(b['chunks']))
    broken = dict(b['chunks']); broken[h] = '{}'
    with pytest.raises(ValueError, match='hash'):
        restore(b['recipe'], broken)
    del broken[h]
    with pytest.raises(KeyError):
        restore(b['recipe'], broken)


def test_bad_business_hash_and_nonfinite_rejected():
    p = sample(); p['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='source'):
        build(p)
    with pytest.raises(ValueError):
        canonical(float('nan'))


def test_duplicate_document_keys_and_orphan_lines_fail_closed():
    p = sample(); p['invoice_drilldown']['documents'].append(p['invoice_drilldown']['documents'][0])
    p['sha256'] = source_sha256(p)
    with pytest.raises(ValueError, match='duplicate'):
        build(p)
    p = sample(); p['invoice_drilldown']['lines']['unknown'] = []
    p['sha256'] = source_sha256(p)
    with pytest.raises(ValueError, match='orphan'):
        build(p)
