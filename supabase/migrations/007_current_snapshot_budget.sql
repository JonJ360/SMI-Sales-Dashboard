-- SMI-only RPC budget: assembly plus 64 MB JSONB serialization exceeds
-- the default 8s transaction budget even after single-evaluation repair.
-- PostgREST hoists this function-local setting; no role/global change.
begin;
set local lock_timeout='5s';
do $$ begin
 if md5(pg_get_functiondef('public.smi_sales_current_snapshot()'::regprocedure)) <> 'e378fdabb700348b8a8a503b21019c70' then raise exception 'SMI serving preimage drift'; end if;
end $$;
alter function public.smi_sales_current_snapshot() set statement_timeout='20s';
notify pgrst, 'reload schema';
commit;
