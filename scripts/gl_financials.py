"""Strict offline adapter for the reviewed Financial Statements mapping 4.1.0.

No SQL, network, refresh, or publication. Decimal arithmetic is retained until
JSON-number conversion, which must round-trip to the exact original cents.
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path
import re

MAPPING_SHA256 = '7787641c4726e74b0b3bccda796a43c6ffdeafcf63c9a298a192b3de54212c7a'
BRANCHES = {'00': 'Fargo', '01': 'Grand Forks', '03': 'Bismarck',
            '02': 'Fergus Falls', '99': 'Unassigned (GL 99)'}
NOTE = ('Unallocated GP account balances by third GL account segment; not standalone '
        'legal-entity results. No SOP-location inference or allocation. Butte and '
        'Sheridan GL mappings are unknown. Zero-only GL 02/99 scopes are audited '
        'and omitted; nonzero scopes remain separate.')


def _money(value):
    try:
        if isinstance(value, bool):
            raise ValueError('boolean money')
        result = Decimal(str(value))
        if not result.is_finite() or result != result.quantize(Decimal('.01')):
            raise ValueError('nonfinite or fractional-cent money')
        return result
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('invalid money') from exc


def _number(value):
    result = int(value) if value == value.to_integral_value() else float(value)
    if Decimal(str(result)) != value:
        raise ValueError('money cannot round-trip as a JSON number')
    return result


def _totals(sales=Decimal(0), cost=Decimal(0)):
    return {'sales': sales, 'cost': cost, 'profit': sales - cost}


def _check_kpis(totals, kpis):
    for output, source in [('sales', 'revenue'), ('cost', 'cost_of_goods_sold'),
                           ('profit', 'gross_profit')]:
        if totals[output] != _money(kpis[source]):
            raise ValueError('account sum / KPI mismatch: ' + source)


def _date(value):
    result = dt.date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError('date must be YYYY-MM-DD')
    return result


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid source hash')
    return value


def build_gl_financials(cache, as_of, start_year=2024):
    """Return JSON-ready GL company/branch/account lineage, or raise ValueError.

    Requires every calendar month from start_year January through as_of's month.
    Validates exact stored canonical payload hashes and semantic payload equality;
    pins the reviewed mapping and reconciles period summary/detail and all KPIs.
    Root run source hash is recomputed from the ordered payload-hash manifest and verified.
    """
    try:
        with localcontext() as ctx:
            ctx.prec = 50
            return _build(cache, as_of, start_year)
    except (KeyError, TypeError, InvalidOperation, OverflowError) as exc:
        raise ValueError('malformed Financial Statements cache: ' + str(exc)) from exc


def _build(cache, as_of, start_year):
    end = _date(as_of)
    run = cache['run']
    if _date(run['as_of']) < end:
        raise ValueError('cache as_of precedes requested as_of')
    if run['mapping_version'] != '4.1.0' or run['mapping_sha256'] != MAPPING_SHA256:
        raise ValueError('unreviewed mapping')
    _hash(run['source_sha256'])
    ordered = sorted(cache['periods'], key=lambda p: (str(p['company_code']), int(p['fiscal_year']), int(p['fiscal_period'])))
    actual_source_hash = hashlib.sha256(''.join(_hash(p['payload_sha256']) for p in ordered).encode()).hexdigest()
    if actual_source_hash != run['source_sha256']:
        raise ValueError('root source hash mismatch')
    if not isinstance(start_year, int) or isinstance(start_year, bool) or not 1 <= start_year <= end.year:
        raise ValueError('invalid start_year')
    expected = {f'{year:04d}-{month:02d}' for year in range(start_year, end.year + 1)
                for month in range(1, 13) if (year, month) <= (end.year, end.month)}
    periods = {}
    branch_nonzero = set()
    for period in cache['periods']:
        if period['company_code'] != 'SMI':
            continue
        year, month = period['fiscal_year'], period['fiscal_period']
        if type(year) is not int or type(month) is not int or not 1 <= month <= 12:
            raise ValueError('invalid fiscal period')
        key = f'{year:04d}-{month:02d}'
        if key not in expected:
            continue
        if key in periods:
            raise ValueError('duplicate period: ' + key)
        first = dt.date(year, month, 1).isoformat()
        last = dt.date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        if period['period_start'] != first or period['period_end'] != last:
            raise ValueError('noncalendar fiscal period')
        text = period['payload_canonical']
        digest = _hash(period['payload_sha256'])
        if not isinstance(text, str) or hashlib.sha256(text.encode('utf-8')).hexdigest() != digest:
            raise ValueError('payload hash mismatch')
        payload = period['payload']
        if json.loads(text) != payload:
            raise ValueError('canonical payload differs from actual payload')
        for field in ('company_code', 'fiscal_year', 'fiscal_period', 'period_start', 'period_end'):
            if payload[field] != period[field]:
                raise ValueError('payload period identity mismatch')
        statement = payload['statement']
        metadata = statement.get('model_metadata', {})
        for field in ('mapping_version', 'mapping_sha256'):
            if field in metadata and metadata[field] != run[field]:
                raise ValueError('statement mapping mismatch')
        totals = _totals()
        branches = {code: _totals() for code in BRANCHES}
        included, excluded, identities = [], [], set()
        for row in statement['income_statement']:
            identity = row['account_index']
            if identity in identities:
                raise ValueError('duplicate account')
            identities.add(identity)
            debit, credit = _money(row['period_debit']), _money(row['period_credit'])
            if row['posting_type'] == 1:
                if debit != _money(row['detail_period_debit']) or credit != _money(row['detail_period_credit']):
                    raise ValueError('summary/detail income-account mismatch')
            category = row['category_id']
            description = str(row.get('account_description', ''))
            section = ('cost' if category == 33 or (category == 32 and 'DISCOUNTS GIVEN' in description.upper())
                       else 'sales' if category in (31, 32) else None)
            account = {field: row[field] for field in ('account_index', 'account_number', 'category_id',
                       'posting_type', 'period_debit', 'period_credit')}
            account.update(namespace='SMI:GP:GL', account_description=description)
            if row['posting_type'] != 1 or section is None:
                account['exclusion_reason'] = 'not revenue/COGS under Financial Statements mapping 4.1.0'
                excluded.append(account)
                continue
            segments = row['account_number'].split('-')
            if len(segments) != 3 or segments[2] not in BRANCHES:
                raise ValueError('unknown GL branch: ' + row['account_number'])
            code = segments[2]
            amount = credit - debit if section == 'sales' else debit - credit
            totals[section] += amount
            branches[code][section] += amount
            account.update(branch_code=code, classification=section, amount=_number(amount),
                           detail_period_debit=row['detail_period_debit'],
                           detail_period_credit=row['detail_period_credit'])
            included.append(account)
        totals['profit'] = totals['sales'] - totals['cost']
        _check_kpis(totals, statement['kpis'])
        canonical_branches = statement['branches']
        if set(canonical_branches) - set(BRANCHES):
            raise ValueError('unknown canonical GL branch')
        branch_rows = []
        for code, values in branches.items():
            values['profit'] = values['sales'] - values['cost']
            _check_kpis(values, canonical_branches[code]['kpis'])
            if any(values.values()):
                branch_nonzero.add(code)
            branch_rows.append(dict(code=code, name=BRANCHES[code],
                                    **{k: _number(v) for k, v in values.items()}))
        periods[key] = dict(company={k: _number(v) for k, v in totals.items()}, branches=branch_rows,
                            accounts=included, excluded_accounts=excluded, period_start=first,
                            period_end=last, payload_sha256=digest)
    if set(periods) != expected:
        raise ValueError('missing months: ' + ', '.join(sorted(expected - set(periods))))
    omitted = []
    for code in ('02', '99'):
        if code not in branch_nonzero:
            omitted.append(dict(code=code, name=BRANCHES[code], reason='zero in every selected period',
                                period_count=len(periods), sales=0, cost=0, profit=0))
    omitted_codes = {row['code'] for row in omitted}
    for period in periods.values():
        period['branches'] = [b for b in period['branches'] if b['code'] not in omitted_codes]
    return dict(version='smi-gl-financial-v1', basis='GP actual-ledger fiscal period balances',
                as_of=as_of, periods=dict(sorted(periods.items())),
                source={k: run[k] for k in ('mapping_version', 'mapping_sha256', 'source_sha256')},
                branch_scope_note=NOTE, omitted_branches=omitted)


def snapshot_sha256(snapshot):
    source = {k: v for k, v in snapshot.items() if k not in {'sha256', 'refreshed_at'}}
    return hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--financial-cache', required=True, type=Path)
    parser.add_argument('--sales-snapshot', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--start-year', type=int, default=2024)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output in {args.sales_snapshot.resolve(), args.financial_cache.resolve()} or output.exists():
        raise ValueError('output must be a new path, never an input or existing file')
    sales = json.loads(args.sales_snapshot.read_text(encoding='utf-8'))
    if sales['sha256'] != snapshot_sha256(sales):
        raise ValueError('sales snapshot hash mismatch')
    cache = json.loads(args.financial_cache.read_text(encoding='utf-8'))
    gl = build_gl_financials(cache, sales['as_of'], args.start_year)
    gl['source']['transaction_source_sha256'] = sales['sha256']
    sales['gl_financials'] = gl
    sales['sha256'] = snapshot_sha256(sales)
    serialized = json.dumps(sales, ensure_ascii=True, separators=(',', ':'), allow_nan=False)
    with output.open('x', encoding='utf-8') as handle:
        handle.write(serialized)
    print(json.dumps({'output': str(output), 'sha256': sales['sha256'], 'period_count': len(gl['periods'])}))


if __name__ == '__main__':
    main()
