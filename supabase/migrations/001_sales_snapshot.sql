begin;

create table if not exists public.smi_sales_snapshots (
  id bigint generated always as identity primary key,
  source_sha256 text not null unique check (source_sha256 ~ '^[0-9a-f]{64}$'),
  as_of date not null,
  refreshed_at timestamptz not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  check (jsonb_typeof(payload) = 'object')
);

create table if not exists public.smi_sales_current (
  singleton boolean primary key default true check (singleton),
  snapshot_id bigint not null references public.smi_sales_snapshots(id),
  promoted_at timestamptz not null default now()
);

alter table public.smi_sales_snapshots enable row level security;
alter table public.smi_sales_current enable row level security;

revoke all on public.smi_sales_snapshots from anon, authenticated;
revoke all on public.smi_sales_current from anon, authenticated;

create or replace function public.smi_sales_current_snapshot()
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_payload jsonb;
begin
  if auth.uid() is null then
    raise insufficient_privilege using message = 'authentication required';
  end if;
  select s.payload into v_payload
  from public.smi_sales_current c
  join public.smi_sales_snapshots s on s.id = c.snapshot_id
  where c.singleton = true;
  if v_payload is null then
    raise exception 'SMI sales snapshot is unavailable';
  end if;
  return v_payload;
end;
$$;

revoke all on function public.smi_sales_current_snapshot() from public, anon;
grant execute on function public.smi_sales_current_snapshot() to authenticated;

comment on table public.smi_sales_snapshots is 'Immutable aggregate SMI sales snapshots sourced from read-only Dynamics GP SQL.';
comment on function public.smi_sales_current_snapshot() is 'Returns the promoted aggregate sales snapshot to authenticated users only.';

commit;
