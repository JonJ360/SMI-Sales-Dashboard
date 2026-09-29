"""SMI-only immutable content format v1; no network and no business transforms.

All source history is checked on EVERY existing SELECT-only extract (at least as
frequently as a periodic audit). Publication uploads only absent content. Never
assume a closed month is immutable. Recipes retain original document/line order,
number spellings and Python's existing source-hash representation.
"""
from __future__ import annotations
import hashlib
import json
from itertools import groupby


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def restore(recipe, chunks):
    kind, value = recipe
    if kind == 'c':
        text = chunks[value]
        if digest(text) != value:
            raise ValueError('chunk hash mismatch')
        return text
    if kind == 'v':
        return value
    if kind == 'o':
        return '{' + ','.join(k + ':' + restore(v, chunks) for k, v in value) + '}'
    if kind == 'a':
        parts = [restore(v, chunks)[1:-1] for v in value]
        return '[' + ','.join(v for v in parts if v) + ']'
    if kind == 'm':
        # json raw_decode keeps the serialized value spelling, including -0.0.
        entries = {}
        decoder = json.JSONDecoder()
        for child in value:
            text = restore(child, chunks); pos = 1
            while pos < len(text) - 1:
                key, end = decoder.raw_decode(text, pos)
                start = end + 1
                _, end = decoder.raw_decode(text, start)
                if key in entries:
                    raise ValueError('duplicate merge key')
                entries[key] = text[start:end]
                pos = end + 1
        return '{' + ','.join(canonical(k) + ':' + entries[k] for k in sorted(entries)) + '}'
    raise ValueError('unknown recipe')


def batches(chunks, limit=8_000_000):
    """Bound actual JSON upload representation, including escaped content text."""
    batch = {}; size = 2
    for h, text in chunks.items():
        entry_size = len(canonical({h: text}).encode('utf8'))
        if entry_size > limit:
            raise ValueError('SMI chunk exceeds upload limit')
        if size + entry_size > limit and batch:
            yield batch; batch = {}; size = 2
        batch[h] = text; size += entry_size
    if batch:
        yield batch


def build(snapshot):
    source = {k: v for k, v in snapshot.items() if k not in {'sha256', 'refreshed_at'}}
    if snapshot.get('sha256') != digest(canonical(source)):
        raise ValueError('source hash mismatch')
    chunks = {}; periods = {}

    def chunk(value):
        text = canonical(value); h = digest(text)
        chunks[h] = text
        return ['c', h]

    def node(value, depth=0):
        if isinstance(value, dict) and depth < 1:
            return ['o', [[canonical(k), node(value[k], depth + 1)] for k in sorted(value)]]
        if not isinstance(value, (dict, list)):
            return ['v', canonical(value)]
        return chunk(value)

    drill = snapshot.get('invoice_drilldown')
    drill_recipe = None
    if drill is not None:
        fields = drill['document_fields']
        if not drill['documents']:
            if drill['lines']:
                raise ValueError('orphan invoice lines')
            drill_recipe = node(drill)
        else:
            key_idx, date_idx = fields.index('key'), fields.index('date')
            key_period = {}
            for row in drill['documents']:
                if row[key_idx] in key_period:
                    raise ValueError('duplicate document key')
                key_period[row[key_idx]] = row[date_idx][:7]
            if set(drill['lines']) - set(key_period):
                raise ValueError('orphan invoice lines')
            docs = []
            for period, rows in groupby(drill['documents'], key=lambda r: r[date_idx][:7]):
                ref = chunk(list(rows)); docs.append(ref)
                periods.setdefault(period, []).append(ref[1])
            grouped = {}
            for key, lines in drill['lines'].items():
                grouped.setdefault(key_period[key], {})[key] = lines
            line_refs = []
            for period in sorted(grouped):
                ref = chunk(grouped[period]); line_refs.append(ref)
                periods.setdefault(period, []).append(ref[1])
            drill_recipe = ['o', [[canonical(k), ['a', docs] if k == 'documents' else
                                  ['m', line_refs] if k == 'lines' else node(drill[k])]
                                 for k in sorted(drill)]]
    recipe = ['o', [[canonical(k), drill_recipe if k == 'invoice_drilldown' else node(snapshot[k])]
                    for k in sorted(snapshot)]]
    manifest = canonical({'format': 1, 'recipe': recipe})
    return {'recipe': recipe, 'manifest_text': manifest, 'manifest_sha256': digest(manifest),
            'chunks': chunks, 'periods': periods}
