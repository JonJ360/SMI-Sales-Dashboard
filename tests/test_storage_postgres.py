"""Real PostgreSQL tests. Run through tools/run_storage_tests.py (isolated cluster)."""
import concurrent.futures
import copy
import json
import os
import time
from pathlib import Path

import pytest

psycopg = pytest.importorskip('psycopg')
from psycopg.types.json import Jsonb
from scripts.content_storage import build, canonical, digest, batches
from scripts.publish_snapshot import source_sha256
from test_content_storage import sample

DSN = os.environ.get('SMI_TEST_DSN')
pytestmark = pytest.mark.skipif(not DSN, reason='requires explicitly isolated PostgreSQL')


def connect(role='ar_current_ingest'):
    c = psycopg.connect(DSN, autocommit=True)
    c.execute("select set_config('request.jwt.claims', %s, false)", (json.dumps({'role': role, 'sub': '11111111-1111-1111-1111-111111111111'}),))
    c.execute('set role ' + role)
    return c


def call(c, name, *args):
    return c.execute('select public.' + name + '(' + ','.join(['%s'] * len(args)) + ')', args).fetchone()[0]


def stage(p):
    b = build(p)
    with connect() as c:
        missing = call(c, 'smi_sales_missing_chunks', list(b['chunks']))
        for batch in batches({h: b['chunks'][h] for h in missing}):
            call(c, 'smi_sales_put_chunks', Jsonb(batch))
        return call(c, 'smi_sales_stage_manifest', p['sha256'], p['as_of'], p['refreshed_at'], b['manifest_sha256'], b['manifest_text'])


def state(c):
    return call(c, 'smi_sales_storage_state')


def promote(v, expected):
    with connect('ar_current_promoter') as c:
        return call(c, 'smi_sales_publish_manifest', v, expected)


def test_01_schema_and_roundtrip():
    p = sample(); v = stage(p)
    with connect('ar_current_operator') as c:
        prior = state(c)
    promote(v, prior['generation'])
    with connect('ar_current_operator') as c:
        assert call(c, 'smi_sales_current_snapshot') == p
        assert state(c)['snapshot_id'] == -v


def test_02_hash_and_immutable_auth():
    with connect() as c:
        with pytest.raises(psycopg.Error, match='hash'):
            call(c, 'smi_sales_put_chunks', Jsonb({'0' * 64: '{}'}))
        with pytest.raises(psycopg.Error):
            c.execute('select * from public.smi_sales_chunks')
        with pytest.raises(psycopg.Error):
            call(c, 'smi_sales_publish_manifest', 1, 1)
    with connect('authenticated') as c:
        with pytest.raises(psycopg.Error):
            call(c, 'smi_sales_put_chunks', Jsonb({}))
    with psycopg.connect(DSN, autocommit=True) as c:
        with pytest.raises(psycopg.Error, match='immutable'):
            c.execute("update public.smi_sales_chunks set content=content")


def test_03_failure_missing_bad_source_no_current_loss():
    with connect('ar_current_operator') as c:
        before = state(c)
    p = sample(); p['as_of'] = '2026-09-29'; p['sha256'] = source_sha256(p)
    b = build(p)
    b['recipe'][1].append(['"missing"', ['c', 'f' * 64]])
    text = canonical({'format': 1, 'recipe': b['recipe']})
    with connect() as c:
        with pytest.raises(psycopg.Error, match='missing'):
            call(c, 'smi_sales_stage_manifest', p['sha256'], p['as_of'], p['refreshed_at'], digest(text), text)
        with pytest.raises(psycopg.Error, match='source'):
            call(c, 'smi_sales_stage_manifest', '0' * 64, p['as_of'], p['refreshed_at'], b['manifest_sha256'], b['manifest_text'])
    with connect('ar_current_operator') as c:
        assert state(c) == before


def test_04_two_publishers_aba_and_rollback():
    a = sample(); b = copy.deepcopy(a); b['months']['2026-09']['sales'] = 99.0; b['sha256'] = source_sha256(b)
    va, vb = stage(a), stage(b)
    with connect('ar_current_operator') as c:
        s = state(c)
    with concurrent.futures.ThreadPoolExecutor(2) as ex:
        fs = [ex.submit(promote, v, s['generation']) for v in (va, vb)]
        results = []
        for f in fs:
            try: results.append(f.result())
            except psycopg.Error as e: assert 'stale' in str(e)
    assert len(results) == 1
    with connect('ar_current_operator') as c:
        s1 = state(c)
    with connect('ar_current_promoter') as c:
        call(c, 'smi_sales_rollback', s1['generation'])
        with pytest.raises(psycopg.Error, match='stale'):
            call(c, 'smi_sales_rollback', s1['generation'])
    with pytest.raises(psycopg.Error, match='stale'):
        promote(va, s['generation'])


def test_05_real_advisory_wait_and_legacy_rollback():
    with connect('ar_current_operator') as c:
        s = state(c)
    v = stage(sample())
    holder = psycopg.connect(DSN)
    try:
        holder.execute('select pg_advisory_xact_lock(736491028)')
        with concurrent.futures.ThreadPoolExecutor(1) as ex:
            future = ex.submit(promote, v, s['generation'])
            waited = False
            with psycopg.connect(DSN, autocommit=True) as observer:
                for _ in range(50):
                    waited = observer.execute("select exists(select 1 from pg_stat_activity where wait_event='advisory' and pid<>pg_backend_pid())").fetchone()[0]
                    if waited: break
                    time.sleep(.02)
            holder.commit()
            assert waited
            future.result()
    finally:
        holder.close()
    with connect('ar_current_operator') as c:
        s = state(c)
    with connect('ar_current_promoter') as c:
        with pytest.raises(psycopg.Error, match='retired'):
            call(c, 'smi_sales_promote_snapshot', 1)
        call(c, 'smi_sales_publish_legacy', 1, s['generation'])
    with connect('ar_current_operator') as c:
        assert state(c)['snapshot_id'] == 1
        assert call(c, 'smi_sales_current_snapshot') == {'legacy': True}


def test_06_complete_real_payload_and_storage(tmp_path):
    path = os.environ.get('SMI_TEST_PAYLOAD')
    if not path: pytest.skip('no local payload specified')
    p = json.loads(Path(path).read_text(encoding='utf8'))
    first = build(p); v1 = stage(p)
    with connect('ar_current_operator') as c: s = state(c)
    promote(v1, s['generation'])
    with connect('ar_current_operator') as c:
        c.execute("set statement_timeout='8s'")
        started=time.monotonic()
        served = call(c, 'smi_sales_current_snapshot')
        serve_seconds=time.monotonic()-started
        assert bool(served == p)
        # Signed zero is JSONB-normalized; full canonical business hash is
        # separately verified server-side before conversion to JSONB.
    with psycopg.connect(DSN, autocommit=True) as c:
        before = c.execute('select count(*),sum(pg_column_size(content)) from public.smi_sales_chunks').fetchone()
    q = copy.deepcopy(p)
    dd = q['invoice_drilldown']; fi = dd['document_fields']; i = next(i for i,r in enumerate(dd['documents']) if r[fi.index('date')].startswith('2026'))
    dd['documents'][i][fi.index('sales')] += .01
    q['sha256'] = source_sha256(q); second = build(q); v2 = stage(q)
    assert {k:v for k,v in first['periods'].items() if k<'2026'} == {k:v for k,v in second['periods'].items() if k<'2026'}
    with psycopg.connect(DSN, autocommit=True) as c:
        after = c.execute('select count(*),sum(pg_column_size(content)) from public.smi_sales_chunks').fetchone()
        c.execute('create table public.test_legacy_size(payload jsonb)')
        c.execute('insert into public.test_legacy_size values(%s::jsonb)', (canonical(p),))
        legacy_bytes = c.execute('select pg_column_size(payload) from public.test_legacy_size').fetchone()[0]
        manifest_bytes = c.execute('select pg_column_size(manifest_text) from public.smi_sales_manifests where id=%s',(v2,)).fetchone()[0]
        refs_bytes = c.execute('select coalesce(sum(pg_column_size(r)),0) from public.smi_sales_manifest_chunks r where manifest_id=%s',(v2,)).fetchone()[0]
    assert after[1] - before[1] + manifest_bytes + refs_bytes < legacy_bytes / 10
    report = {'complete_payload_equal': True, 'source_sha256': p['sha256'], 'chunks': len(first['chunks']),
              'manifest_bytes':len(first['manifest_text'].encode()), 'compact_payload_bytes':len(canonical(p).encode()),
              'initial_chunk_stored_bytes':int(before[1]), 'next_version_new_chunks':after[0]-before[0],
              'next_version_new_chunk_stored_bytes':int(after[1]-before[1]), 'legacy_compressed_payload_bytes':legacy_bytes,
              'next_version_manifest_stored_bytes':manifest_bytes, 'next_version_ref_row_bytes':int(refs_bytes),
              'local_serving_seconds_under_8s_budget':serve_seconds,
              'note':'Synthetic one-cent current-period change to a private local real payload; not production storage.'}
    Path(os.environ['SMI_TEST_EVIDENCE']).joinpath('payload-storage.json').write_text(json.dumps(report,indent=2))


def test_07_prior_period_correction_and_original_version_survive():
    p=sample(); original=stage(p)
    p['invoice_drilldown']['documents'][1][2]=-8.75
    p['invoice_drilldown']['lines']['I:1'][0][1]=11.25
    p['sha256']=source_sha256(p); corrected=stage(p)
    assert original != corrected
    with connect('ar_current_operator') as c:
        assert call(c,'smi_sales_manifest_payload',original)==sample()
        assert call(c,'smi_sales_manifest_payload',corrected)==p


def test_08_unicode_keys_and_numeric_representation_server_hash():
    p=sample(); dd=p['invoice_drilldown']; dd['documents'][0][0]='I:é😀'
    dd['lines']['I:é😀']=dd['lines'].pop('I:2'); p['sha256']=source_sha256(p)
    v=stage(p)
    with connect('ar_current_operator') as c:
        assert call(c,'smi_sales_manifest_payload',v)==p


def test_09_failed_publication_fk_keeps_current_and_event_count():
    with connect('ar_current_operator') as c: before=state(c)
    with psycopg.connect(DSN,autocommit=True) as c:
        count=c.execute('select count(*) from public.smi_sales_publications').fetchone()[0]
    with pytest.raises(psycopg.Error): promote(999999999,before['generation'])
    with connect('ar_current_promoter') as c:
        with pytest.raises(psycopg.Error): call(c,'smi_sales_rollback',None)
    with connect('ar_current_operator') as c: assert state(c)==before
    with psycopg.connect(DSN,autocommit=True) as c:
        assert c.execute('select count(*) from public.smi_sales_publications').fetchone()[0]==count


def test_10_no_direct_access_or_internal_helper_execute():
    with psycopg.connect(DSN,autocommit=True) as c:
        with pytest.raises(psycopg.Error, match='immutable'):
            c.execute("update public.smi_sales_manifests set created_at=now()+interval '1 day'")
    for role in ('anon','authenticated','ar_current_ingest','ar_current_promoter','ar_current_operator','service_role'):
        with connect(role) as c:
            for table in ('smi_sales_chunks','smi_sales_manifests','smi_sales_manifest_chunks','smi_sales_publications','smi_sales_storage_current'):
                with pytest.raises(psycopg.Error): c.execute('select * from public.'+table)
            with pytest.raises(psycopg.Error): call(c,'smi_sales_assemble',Jsonb(['v','1']),0)


def test_11_same_hash_concurrent_staging_and_refreshed_metadata():
    p=sample(); p['as_of']='2026-09-27';p['sha256']=source_sha256(p)
    q=copy.deepcopy(p);q['refreshed_at']='2026-09-28T21:00:00Z'
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        a=pool.submit(stage,p); b=pool.submit(stage,q)
        assert a.result()==b.result()
    with connect('ar_current_operator') as c:
        served=call(c,'smi_sales_manifest_payload',a.result())
        assert served in (p,q)


def test_12_publish_rollback_race_one_winner():
    with connect('ar_current_operator') as c: base=state(c)
    v=stage(sample())
    def change(rollback):
        try:
            with connect('ar_current_promoter') as c:
                return call(c,'smi_sales_rollback',base['generation']) if rollback else call(c,'smi_sales_publish_manifest',v,base['generation'])
        except psycopg.Error as e: return e.sqlstate
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        result=list(pool.map(change,[True,False]))
    assert sum(isinstance(r,int) for r in result)==1
    with connect('ar_current_operator') as c:
        assert state(c)['generation']==base['generation']+1
        assert call(c,'smi_sales_current_snapshot') is not None


def test_13_http_lost_response_commits_once_no_automatic_replay():
    import http.server
    import socket
    import threading
    from scripts.publish_snapshot import rpc
    with connect('ar_current_operator') as c: before=state(c)
    v=stage(sample()); requests=[]
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(data)
            with connect('ar_current_promoter') as c:
                call(c,'smi_sales_publish_manifest',data['p_manifest_id'],data['p_expected_generation'])
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with pytest.raises(Exception):
            rpc('http://127.0.0.1:'+str(server.server_port),'synthetic','synthetic','smi_sales_publish_manifest',{'p_manifest_id':v,'p_expected_generation':before['generation']},single_attempt=True)
        assert len(requests)==1
        with connect('ar_current_operator') as c:
            after=state(c)
            assert after['generation']==before['generation']+1
            assert after['snapshot_id']==-v
        with pytest.raises(psycopg.Error): promote(v,before['generation'])
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
