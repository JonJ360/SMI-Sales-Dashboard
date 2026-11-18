-- Additive authenticated raw JSON transport. Existing serving/storage RPCs remain untouched.
-- The advertised length describes these exact UTF-8 response bytes before HTTP compression.
begin;
set local lock_timeout='3s';
set local statement_timeout='20s';
do $$ begin
 if to_regprocedure('public.smi_sales_download_snapshot()') is not null then
  raise exception 'SMI download RPC already exists; inspect rather than replace';
 end if;
 if to_regprocedure('public.smi_sales_current_snapshot()') is null then
  raise exception 'SMI current snapshot serving RPC is missing';
 end if;
end $$;
-- PostgREST media type domain makes the scalar result raw bytes, not a JSON hex string.
create domain public."application/octet-stream" as bytea;
revoke all on domain public."application/octet-stream" from public;
grant usage on domain public."application/octet-stream" to authenticated,ar_current_operator;
create function public.smi_sales_download_snapshot()
returns public."application/octet-stream"
language plpgsql stable security definer
set search_path=''
set statement_timeout='20s'
as $$
declare body bytea;
begin
 if auth.uid() is null then
  raise insufficient_privilege using message='authentication required';
 end if;
 body:=pg_catalog.convert_to(public.smi_sales_current_snapshot()::text,'UTF8');
 perform pg_catalog.set_config('response.headers',pg_catalog.json_build_array(
  pg_catalog.json_build_object('X-Uncompressed-Content-Length',pg_catalog.octet_length(body)::text),
  pg_catalog.json_build_object('Content-Type','application/json'),
  pg_catalog.json_build_object('Access-Control-Expose-Headers','X-Uncompressed-Content-Length, Content-Type'),
  pg_catalog.json_build_object('Cache-Control','no-store')
 )::text,true);
 return body;
end $$;
revoke all on function public.smi_sales_download_snapshot() from public,anon,service_role,ar_current_ingest,ar_current_promoter;
grant execute on function public.smi_sales_download_snapshot() to authenticated,ar_current_operator;
comment on function public.smi_sales_download_snapshot() is 'SMI authenticated byte-exact JSON download. POST with Accept: application/octet-stream. X-Uncompressed-Content-Length measures the returned UTF-8 bytes, independent of HTTP compression. No storage/auth/calculation changes.';
notify pgrst,'reload schema';
commit;
