import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'gl_financials.py'


def seal(period):
    text = json.dumps(period['payload'], sort_keys=True, separators=(',', ':'))
    period['payload_canonical'] = text
    period['payload_sha256'] = hashlib.sha256(text.encode()).hexdigest()
    return period


def seal_run(cache):
    ordered=sorted(cache['periods'], key=lambda p:(str(p['company_code']),int(p['fiscal_year']),int(p['fiscal_period'])))
    cache['run']['source_sha256']=hashlib.sha256(''.join(p['payload_sha256'] for p in ordered).encode()).hexdigest()
    return cache

def fixture():
    rows = []
    for index, (number, cat, description, debit, credit) in enumerate([
        ('310-00-00', 31, 'SALES', '0.10', '100.20'),
        ('320-00-01', 32, 'RETURNS', '10.01', '0'),
        ('321-00-00', 32, 'DISCOUNTS GIVEN', '1.02', '0'),
        ('330-00-03', 33, 'COST', '30.03', '0.01'),
        ('364-00-00', 42, 'OTHER', '9', '0'),
        ('430-00-00', 43, 'OTHER INCOME', '0', '8'),
    ], 1):
        rows.append(dict(account_index=index, account_number=number, category_id=cat,
                         account_description=description, posting_type=1,
                         period_debit=debit, period_credit=credit,
                         detail_period_debit=debit, detail_period_credit=credit))
    def k(s, c, p):
        return dict(revenue=s, cost_of_goods_sold=c, gross_profit=p)
    statement = dict(income_statement=rows, kpis=k('90.09', '31.04', '59.05'), branches={
        '00': {'kpis': k('100.10', '1.02', '99.08')},
        '01': {'kpis': k('-10.01', '0', '-10.01')},
        '02': {'kpis': k('0', '0', '0')},
        '03': {'kpis': k('0', '30.02', '-30.02')},
        '99': {'kpis': k('0', '0', '0')},
    })
    p = dict(company_code='SMI', fiscal_year=2025, fiscal_period=1,
             period_start='2025-01-01', period_end='2025-01-31')
    p['payload'] = dict(p, statement=statement)
    return seal_run(dict(run=dict(as_of='2025-01-15', mapping_version='4.1.0',
                        mapping_sha256='7787641c4726e74b0b3bccda796a43c6ffdeafcf63c9a298a192b3de54212c7a',
                        source_sha256='a' * 64), periods=[seal(p)]))


class GLTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.exists(), 'GL adapter implementation is missing')
        spec = importlib.util.spec_from_file_location('gl_financials', MODULE)
        self.gl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gl)
        self.cache = fixture()

    def build(self):
        return self.gl.build_gl_financials(self.cache, '2025-01-15', start_year=2025)

    def test_canonical_signs_discounts_exclusions_exact_cents(self):
        result = self.build()
        p = result['periods']['2025-01']
        self.assertEqual(p['company'], dict(sales=90.09, cost=31.04, profit=59.05))
        self.assertEqual([b['name'] for b in p['branches']], ['Fargo', 'Grand Forks', 'Bismarck'])
        self.assertEqual(len(p['accounts']), 4)
        self.assertEqual(len(p['excluded_accounts']), 2)
        self.assertEqual({b['code'] for b in result['omitted_branches']}, {'02', '99'})

    def test_nonzero_fergus_falls_is_separate(self):
        p = self.cache['periods'][0]
        s = p['payload']['statement']
        s['income_statement'][0]['account_number'] = '310-00-02'
        s['branches']['02']['kpis'] = dict(revenue='100.10', cost_of_goods_sold='0', gross_profit='100.10')
        s['branches']['00']['kpis'] = dict(revenue='0', cost_of_goods_sold='1.02', gross_profit='-1.02')
        seal(p)
        seal_run(self.cache)
        branches = self.build()['periods']['2025-01']['branches']
        self.assertEqual(next(b for b in branches if b['code'] == '02')['sales'], 100.10)

    def test_rejects_corruption(self):
        for kind in ('company_kpi', 'branch_kpi', 'unknown_branch', 'duplicate', 'missing',
                     'hash', 'canonical_semantics', 'detail', 'nonfinite', 'calendar', 'mapping', 'root_source_hash'):
            with self.subTest(kind=kind):
                self.cache = fixture()
                p = self.cache['periods'][0]
                s = p['payload']['statement']
                if kind == 'company_kpi': s['kpis']['revenue'] = '0'
                if kind == 'branch_kpi': s['branches']['00']['kpis']['revenue'] = '0'
                if kind == 'unknown_branch': s['income_statement'][0]['account_number'] = '310-00-77'
                if kind == 'duplicate': self.cache['periods'].append(copy.deepcopy(p))
                if kind == 'missing': self.cache['periods'] = []
                if kind == 'detail': s['income_statement'][0]['detail_period_debit'] = '0'
                if kind == 'nonfinite': s['income_statement'][0]['period_debit'] = 'NaN'
                if kind == 'calendar': p['period_start'] = '2025-01-02'
                if kind == 'mapping': self.cache['run']['mapping_sha256'] = 'b' * 64
                seal(p)
                if kind == 'hash': p['payload_sha256'] = '0' * 64
                if kind == 'canonical_semantics': s['kpis']['revenue'] = '0'
                seal_run(self.cache)
                if kind == 'root_source_hash': self.cache['run']['source_sha256'] = 'b' * 64
                with self.assertRaises(ValueError): self.build()

    def test_future_period_excluded(self):
        p = copy.deepcopy(self.cache['periods'][0])
        p.update(fiscal_period=2, period_start='2025-02-01', period_end='2025-02-28')
        self.cache['periods'].append(p)
        seal_run(self.cache)
        self.assertEqual(list(self.build()['periods']), ['2025-01'])

    def test_rejects_boolean_fiscal_period(self):
        p = self.cache['periods'][0]
        p['fiscal_period'] = True
        p['payload']['fiscal_period'] = True
        seal(p)
        with self.assertRaises(ValueError): self.build()

    def test_cli_new_output_and_original_hash(self):
        import tempfile
        scratch = 'C:/Users/jonj/AppData/Local/hermes/cache/scratch'
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            cache, sales, output = [root / name for name in ('cache.json', 'sales.json', 'new.json')]
            cache.write_text(json.dumps(self.cache), encoding='utf-8')
            snapshot = dict(as_of='2025-01-15', refreshed_at='unchanged', data=[1, 2])
            snapshot['sha256'] = self.gl.snapshot_sha256(snapshot)
            original = json.dumps(snapshot)
            sales.write_text(original, encoding='utf-8')
            args = ['--financial-cache', str(cache), '--sales-snapshot', str(sales),
                    '--output', str(output), '--start-year', '2025']
            self.gl.main(args)
            result = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['sha256'], self.gl.snapshot_sha256(result))
            self.assertEqual(result['gl_financials']['source']['transaction_source_sha256'], snapshot['sha256'])
            self.assertEqual(sales.read_text(encoding='utf-8'), original)
            with self.assertRaises(ValueError): self.gl.main(args)
            args[5] = str(sales)
            with self.assertRaises(ValueError): self.gl.main(args)
            args[5] = str(root / 'bad.json')
            snapshot['data'] = [3]
            sales.write_text(json.dumps(snapshot), encoding='utf-8')
            with self.assertRaises(ValueError): self.gl.main(args)
            self.assertFalse((root / 'bad.json').exists())


if __name__ == '__main__':
    unittest.main()
