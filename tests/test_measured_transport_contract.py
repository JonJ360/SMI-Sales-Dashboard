from pathlib import Path
import re
SQL=(Path(__file__).resolve().parents[1]/'supabase/migrations/008_measured_snapshot_download.sql').read_text()

def test_download_is_exact_uncompressed_raw_json_with_browser_visible_size():
    assert 'create domain public."application/octet-stream" as bytea;' in SQL
    assert 'returns public."application/octet-stream"' in SQL
    assert "convert_to(public.smi_sales_current_snapshot()::text,'UTF8')" in SQL
    assert "json_build_object('X-Uncompressed-Content-Length',pg_catalog.octet_length(body)::text)" in SQL
    assert "json_build_object('Access-Control-Expose-Headers','X-Uncompressed-Content-Length, Content-Type')" in SQL
    assert "json_build_object('Content-Type','application/json')" in SQL

def test_download_preserves_existing_authorization_and_excludes_anonymous_roles():
    assert 'if auth.uid() is null then' in SQL
    assert "language plpgsql stable security definer\nset search_path=''\nset statement_timeout='20s'" in SQL
    assert 'revoke all on function public.smi_sales_download_snapshot() from public,anon,service_role,ar_current_ingest,ar_current_promoter;' in SQL
    assert 'grant execute on function public.smi_sales_download_snapshot() to authenticated,ar_current_operator;' in SQL
    assert 'revoke all on domain public."application/octet-stream" from public;' in SQL
    assert 'grant usage on domain public."application/octet-stream" to authenticated,ar_current_operator;' in SQL

def test_download_is_additive_and_does_not_mutate_financial_storage():
    assert 'create or replace function public.smi_sales_current_snapshot' not in SQL.lower()
    assert not re.search(r'\b(insert|update|delete|truncate|drop|alter)\b',SQL,re.I)
    assert "set local lock_timeout='3s';" in SQL
    assert 'notify pgrst' in SQL
