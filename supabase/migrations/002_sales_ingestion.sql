begin;

create or replace function public.smi_sales_stage_snapshot(
  p_source_sha256 text,
  p_as_of date,
  p_refreshed_at timestamptz,
  p_payload jsonb
) returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare v_id bigint;
begin
  if coalesce(auth.jwt()->>'role','') <> 'ar_current_ingest' then
    raise insufficient_privilege using message = 'SMI sales ingestion role required';
  end if;
  if p_source_sha256 !~ '^[0-9a-f]{64}$' or jsonb_typeof(p_payload) <> 'object' then
    raise exception 'invalid SMI sales snapshot';
  end if;
  insert into public.smi_sales_snapshots(source_sha256,as_of,refreshed_at,payload)
  values(p_source_sha256,p_as_of,p_refreshed_at,p_payload)
  on conflict(source_sha256) do update set source_sha256=excluded.source_sha256
  returning id into v_id;
  return v_id;
end;
$$;

create or replace function public.smi_sales_promote_snapshot(p_snapshot_id bigint)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if coalesce(auth.jwt()->>'role','') <> 'ar_current_promoter' then
    raise insufficient_privilege using message = 'SMI sales promotion role required';
  end if;
  if not exists(select 1 from public.smi_sales_snapshots where id=p_snapshot_id) then
    raise exception 'snapshot does not exist';
  end if;
  insert into public.smi_sales_current(singleton,snapshot_id,promoted_at)
  values(true,p_snapshot_id,now())
  on conflict(singleton) do update set snapshot_id=excluded.snapshot_id,promoted_at=excluded.promoted_at;
end;
$$;

create or replace function public.smi_sales_snapshot_metadata()
returns table(snapshot_id bigint, source_sha256 text, as_of date, refreshed_at timestamptz, promoted_at timestamptz)
language sql
stable
security definer
set search_path = ''
as $$
  select s.id,s.source_sha256,s.as_of,s.refreshed_at,c.promoted_at
  from public.smi_sales_current c join public.smi_sales_snapshots s on s.id=c.snapshot_id
  where c.singleton=true and auth.uid() is not null
$$;

revoke all on function public.smi_sales_stage_snapshot(text,date,timestamptz,jsonb) from public,anon,authenticated;
revoke all on function public.smi_sales_promote_snapshot(bigint) from public,anon,authenticated;
revoke all on function public.smi_sales_snapshot_metadata() from public,anon;
grant execute on function public.smi_sales_stage_snapshot(text,date,timestamptz,jsonb) to ar_current_ingest;
grant execute on function public.smi_sales_promote_snapshot(bigint) to ar_current_promoter;
grant execute on function public.smi_sales_snapshot_metadata() to authenticated,ar_current_operator;

commit;
