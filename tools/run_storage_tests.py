"""Explicit isolated portable PostgreSQL test harness; never production credentials."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--bin',type=Path,required=True); ap.add_argument('--work',type=Path,required=True); ap.add_argument('--deps',type=Path,required=True); ap.add_argument('--payload',type=Path)
    a=ap.parse_args(); a.work.mkdir(parents=True,exist_ok=True)
    data=a.work/'pgdata'; password=secrets.token_urlsafe(32); pw=a.work/'init-password'
    if data.exists(): raise RuntimeError('refusing to reuse existing cluster')
    pw.write_text(password); log=(a.work/'runner.log').open('w')
    with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    def run(args): subprocess.run([str(x) for x in args],stdout=log,stderr=log,check=True,timeout=120)
    try: run([a.bin/'initdb.exe','-D',data,'-U','smi_test','--pwfile',pw,'--auth=scram-sha-256','--encoding=UTF8','--locale=C'])
    finally: pw.unlink(missing_ok=True)
    started=False
    try:
        run([a.bin/'pg_ctl.exe','-D',data,'-l',a.work/'postgres.log','-o',f'-h 127.0.0.1 -p {port} -c max_connections=20','-w','start']); started=True
        sys.path.insert(0,str(a.deps)); import psycopg
        dsn=f'host=127.0.0.1 port={port} dbname=postgres user=smi_test password={password}'
        root=Path(__file__).resolve().parents[1]
        with psycopg.connect(dsn,autocommit=True) as c:
            c.execute('create schema auth; create role anon; create role authenticated; create role service_role bypassrls; create role ar_current_ingest; create role ar_current_promoter; create role ar_current_operator;')
            c.execute("create function auth.jwt() returns jsonb language sql stable as $$ select coalesce(current_setting('request.jwt.claims',true),'{}')::jsonb $$; create function auth.uid() returns uuid language sql stable as $$ select (auth.jwt()->>'sub')::uuid $$;")
            for name in ['001_sales_snapshot.sql','002_sales_ingestion.sql','003_operator_verify.sql','003_sales_snapshot_heartbeat.sql','004_sales_ingestion_timeout.sql']:
                c.execute((root/'supabase/migrations'/name).read_text())
            c.execute("insert into public.smi_sales_snapshots(source_sha256,as_of,refreshed_at,payload) values(repeat('a',64),'2026-09-28',now(),'{\"legacy\":true}'); insert into public.smi_sales_current(snapshot_id) values(1)")
            c.execute((root/'supabase/migrations/005_content_storage.sql').read_text())
        env=dict(os.environ,SMI_TEST_DSN=dsn,SMI_TEST_EVIDENCE=str(a.work),PYTHONPATH=str(a.deps)+os.pathsep+str(root))
        if a.payload: env['SMI_TEST_PAYLOAD']=str(a.payload)
        result=subprocess.run([sys.executable,'-m','pytest','tests','-q','--basetemp='+str(a.work/'pytest-temp'),'--junitxml='+str(a.work/'tests.xml')],cwd=root,env=env,capture_output=True,text=True,timeout=600)
        (a.work/'tests.txt').write_text(result.stdout+'\n'+result.stderr)
        print(result.stdout); print(result.stderr); return result.returncode
    finally:
        if started: run([a.bin/'pg_ctl.exe','-D',data,'-m','fast','-w','stop'])
        log.close()
        with socket.socket() as sock: assert sock.connect_ex(('127.0.0.1',port)) != 0
        (a.work/'cleanup.json').write_text(json.dumps({'port':port,'stopped':True}))


if __name__=='__main__': raise SystemExit(main())
