import contextlib,copy,importlib.util,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_gl_financials import fixture
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'scripts'))
import gl_financials as gl
spec=importlib.util.spec_from_file_location('sales_sync_gl_test',R/'scripts/sales_sync.py');sales=importlib.util.module_from_spec(spec);spec.loader.exec_module(sales)
class IntegrationTests(unittest.TestCase):
 def test_flags_pair_before_any_extraction(self):
  for args in [['--with-gl-financials'],['--financial-cache','no-file.json']]:
   with self.subTest(args=args),patch.object(sales,'extract') as extract,contextlib.redirect_stderr(io.StringIO()) as err:
    with self.assertRaises(SystemExit) as exc:sales.main(args)
    self.assertEqual(exc.exception.code,2);self.assertIn('must be supplied together',err.getvalue());extract.assert_not_called()
 def test_opt_in_gl_and_default_legacy_both_write_verified_source_without_network(self):
  source={'as_of':'2025-01-15','refreshed_at':'test','months':{'2025-01':{}},'invoice_drilldown':{'documents':[]},'periods':{'YTD':{'sales':0}},'open_orders':{'amount':0},'today_activity':{},'sha256':''};source['sha256']=gl.snapshot_sha256(source)
  with tempfile.TemporaryDirectory() as directory:
   d=Path(directory);cache=d/'cache.json';cache.write_text(json.dumps(fixture()))
   for enabled in [False,True]:
    output=d/('gl.json' if enabled else 'legacy.json');args=['--output',str(output)]+(['--with-gl-financials','--financial-cache',str(cache)] if enabled else [])
    with patch.object(sales,'extract',return_value=copy.deepcopy(source)),patch.object(sales,'YEARS',(2026,)),contextlib.redirect_stdout(io.StringIO()):sales.main(args)
    result=json.loads(output.read_bytes());self.assertEqual(result['sha256'],gl.snapshot_sha256(result));self.assertEqual(result['invoice_drilldown'],source['invoice_drilldown']);self.assertEqual('gl_financials' in result,enabled)
    if enabled:self.assertEqual(result['gl_financials']['source']['transaction_source_sha256'],source['sha256'])
 def test_bad_gl_cache_cannot_overwrite_existing_output(self):
  source={'as_of':'2025-01-15','sha256':''};source['sha256']=gl.snapshot_sha256(source)
  with tempfile.TemporaryDirectory() as directory:
   d=Path(directory);cache=d/'bad.json';bad=fixture();bad['run']['mapping_sha256']='b'*64;cache.write_text(json.dumps(bad));out=d/'unchanged.json';out.write_text('preserved')
   with patch.object(sales,'extract',return_value=copy.deepcopy(source)),patch.object(sales,'YEARS',(2026,)):
    with self.assertRaisesRegex(ValueError,'unreviewed mapping'):sales.main(['--output',str(out),'--with-gl-financials','--financial-cache',str(cache)])
   self.assertEqual(out.read_text(),'preserved')
if __name__=='__main__':unittest.main()
