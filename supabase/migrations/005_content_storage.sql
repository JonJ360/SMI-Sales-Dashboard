-- SMI ONLY. Additive content storage; no existing snapshot is rewritten/deleted.
-- Current RPC shape/payload stays unchanged. Positive IDs are legacy, negative
-- IDs identify immutable manifests. No client layout or financial transform.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '120s';

-- Fail closed if the deployed five-function preimage differs from reviewed SQL.
do $$
declare x record;
begin
  for x in select * from (values
    ('smi_sales_current_snapshot()', '9ddd002cf47f81f754b465acbfc0bc57'),
    ('smi_sales_heartbeat_snapshot(bigint)', '05a5f80aa206f7093501790deb5143b8'),
    ('smi_sales_promote_snapshot(bigint)', '71d89e49c9cef62d94c5e2876400fbb0'),
    ('smi_sales_snapshot_metadata()', '7a3fcd41195950bb4de11da4b92a05c7'),
    ('smi_sales_stage_snapshot(text,date,timestamp with time zone,jsonb)', 'd2cf0b59e6582657743152eefd76e915')
  ) q(signature, expected) loop
    if md5(pg_get_functiondef(('public.'||x.signature)::regprocedure)) <> x.expected then
      raise exception 'SMI schema preimage drift: %', x.signature;
    end if;
  end loop;
end $$;

create table public.smi_sales_chunks (
  sha256 text primary key check(sha256 ~ '^[0-9a-f]{64}$'),
  content text not null,
  created_at timestamptz not null default now(),
  check(encode(sha256(convert_to(content,'UTF8')),'hex') = sha256),
  check(content::jsonb is not null)
);
create table public.smi_sales_manifests (
  id bigint generated always as identity primary key,
  source_sha256 text not null unique check(source_sha256 ~ '^[0-9a-f]{64}$'),
  manifest_sha256 text not null check(manifest_sha256 ~ '^[0-9a-f]{64}$'),
  manifest_text text not null,
  as_of date not null,
  refreshed_at timestamptz not null,
  created_at timestamptz not null default now(),
  check(encode(sha256(convert_to(manifest_text,'UTF8')),'hex') = manifest_sha256)
);
create table public.smi_sales_manifest_chunks (
  manifest_id bigint not null references public.smi_sales_manifests(id),
  chunk_sha256 text not null references public.smi_sales_chunks(sha256),
  primary key(manifest_id,chunk_sha256)
);
create table public.smi_sales_publications (
  id bigint generated always as identity primary key,
  generation bigint not null unique,
  legacy_id bigint references public.smi_sales_snapshots(id),
  manifest_id bigint references public.smi_sales_manifests(id),
  prior_legacy_id bigint references public.smi_sales_snapshots(id),
  prior_manifest_id bigint references public.smi_sales_manifests(id),
  prior_event_id bigint references public.smi_sales_publications(id),
  rollback_of bigint references public.smi_sales_publications(id),
  published_at timestamptz not null default now(),
  check(num_nonnulls(legacy_id,manifest_id)=1),
  check(num_nonnulls(prior_legacy_id,prior_manifest_id)=1)
);
create table public.smi_sales_storage_current (
  singleton boolean primary key default true check(singleton),
  legacy_id bigint references public.smi_sales_snapshots(id),
  manifest_id bigint references public.smi_sales_manifests(id),
  generation bigint not null default 0,
  legacy_writes_enabled boolean not null default true,
  event_id bigint references public.smi_sales_publications(id),
  checked_at timestamptz not null default now(),
  check(num_nonnulls(legacy_id,manifest_id)=1)
);
-- Lock the existing pointer across bootstrap, not an assumed latest-created row.
lock table public.smi_sales_current in share row exclusive mode;
insert into public.smi_sales_storage_current(legacy_id,checked_at)
select snapshot_id,promoted_at from public.smi_sales_current where singleton;
do $$ begin
  if not exists(select 1 from public.smi_sales_storage_current) then
    raise exception 'SMI current baseline is missing';
  end if;
end $$;

create function public.smi_sales_immutable() returns trigger language plpgsql set search_path='' as $$
begin raise exception 'SMI content and provenance are immutable'; end $$;
create trigger immutable before update or delete on public.smi_sales_chunks for each row execute function public.smi_sales_immutable();
create trigger immutable before update or delete on public.smi_sales_manifests for each row execute function public.smi_sales_immutable();
create trigger immutable before update or delete on public.smi_sales_manifest_chunks for each row execute function public.smi_sales_immutable();
create trigger immutable before update or delete on public.smi_sales_publications for each row execute function public.smi_sales_immutable();

-- Python ensure_ascii=True for object keys only. Numeric JSON text never passes
-- through JSONB until the complete, hash-verified business representation exists.
create function public.smi_sales_json_key(p text) returns text language plpgsql immutable strict set search_path='' as $$
declare c text; n integer; r text := ''; i integer;
begin
  if p !~ '[^\x01-\x7f]' then return to_json(p)::text; end if;
  for i in 1..length(p) loop
    c:=substr(p,i,1); n:=ascii(c);
    if n<128 then r:=r||substr(to_json(c)::text,2,length(to_json(c)::text)-2);
    elsif n<=65535 then r:=r||'\u'||lpad(to_hex(n),4,'0');
    else n:=n-65536; r:=r||'\u'||lpad(to_hex(55296+n/1024),4,'0')||'\u'||lpad(to_hex(56320+n%1024),4,'0');
    end if;
  end loop;
  return '"'||r||'"';
end $$;

create function public.smi_sales_assemble(p jsonb, depth integer default 0) returns text
language plpgsql stable set search_path='' as $$
declare kind text; r text; n bigint; u bigint;
begin
  if depth>16 or jsonb_typeof(p) is distinct from 'array' or jsonb_array_length(p)<>2 then raise exception 'invalid SMI recipe'; end if;
  kind:=p->>0;
  if kind='c' then
    select content into r from public.smi_sales_chunks where sha256=p->>1;
    if r is null then raise exception 'missing SMI chunk'; end if;
  elsif kind='v' then
    r:=p->>1;
    if r is null or jsonb_typeof(r::jsonb) in ('array','object') then raise exception 'invalid SMI scalar'; end if;
  elsif kind='o' then
    select count(*),count(distinct ((v->>0)::jsonb #>> '{}')) into n,u from jsonb_array_elements(p->1) as t(v);
    if n<>u then raise exception 'duplicate SMI object key'; end if;
    select '{'||coalesce(string_agg((v->>0)||':'||public.smi_sales_assemble(v->1,depth+1),',' order by ord),'')||'}' into r
    from jsonb_array_elements(p->1) with ordinality as t(v,ord);
  elsif kind='a' then
    select '['||coalesce(string_agg(nullif(substr(s,2,length(s)-2),''),',' order by ord),'')||']' into r
    from (select public.smi_sales_assemble(v,depth+1) s,ord from jsonb_array_elements(p->1) with ordinality t(v,ord)) q;
  elsif kind='m' then
    select count(*),count(distinct e.key) into n,u from jsonb_array_elements(p->1) t(v)
    cross join lateral json_each(public.smi_sales_assemble(v,depth+1)::json) e;
    if n<>u then raise exception 'duplicate SMI merge key'; end if;
    select '{'||coalesce(string_agg(public.smi_sales_json_key(e.key)||':'||e.value::text,',' order by e.key collate "C"),'')||'}' into r
    from jsonb_array_elements(p->1) t(v) cross join lateral json_each(public.smi_sales_assemble(v,depth+1)::json) e;
  else raise exception 'unknown SMI recipe';
  end if;
  return r;
end $$;

create function public.smi_sales_chunk_refs(p jsonb) returns setof text language plpgsql immutable set search_path='' as $$
declare child jsonb;
begin
  if p->>0='c' then return next p->>1;
  elsif p->>0='o' then
    for child in select v->1 from jsonb_array_elements(p->1) t(v) loop return query select * from public.smi_sales_chunk_refs(child); end loop;
  elsif p->>0 in ('a','m') then
    for child in select v from jsonb_array_elements(p->1) t(v) loop return query select * from public.smi_sales_chunk_refs(child); end loop;
  end if;
end $$;

create function public.smi_sales_missing_chunks(p_hashes text[]) returns text[] language plpgsql security definer set search_path='' as $$
begin
  if coalesce(auth.jwt()->>'role','')<>'ar_current_ingest' then raise insufficient_privilege; end if;
  if cardinality(p_hashes)>10000 then raise exception 'SMI chunk batch too large'; end if;
  return array(select h from unnest(p_hashes) h where not exists(select 1 from public.smi_sales_chunks c where c.sha256=h));
end $$;
create function public.smi_sales_put_chunks(p_chunks jsonb) returns integer language plpgsql security definer set search_path='' as $$
declare x record; n integer:=0;
begin
  if coalesce(auth.jwt()->>'role','')<>'ar_current_ingest' then raise insufficient_privilege; end if;
  if jsonb_typeof(p_chunks) is distinct from 'object' or octet_length(p_chunks::text)>12000000 then raise exception 'invalid SMI chunk batch'; end if;
  for x in select * from jsonb_each_text(p_chunks) loop
    if encode(sha256(convert_to(x.value,'UTF8')),'hex')<>x.key then raise exception 'SMI chunk hash mismatch'; end if;
    insert into public.smi_sales_chunks(sha256,content) values(x.key,x.value) on conflict do nothing;
    if not exists(select 1 from public.smi_sales_chunks where sha256=x.key and content=x.value) then raise exception 'SMI chunk collision'; end if;
    n:=n+1;
  end loop;
  return n;
end $$;

create function public.smi_sales_stage_manifest(p_source_sha256 text,p_as_of date,p_refreshed_at timestamptz,p_manifest_sha256 text,p_manifest_text text)
returns bigint language plpgsql security definer set search_path='' set statement_timeout='120s' as $$
declare recipe jsonb; business jsonb; full_text text; source_text text; payload jsonb; v_id bigint;
begin
  if coalesce(auth.jwt()->>'role','')<>'ar_current_ingest' then raise insufficient_privilege; end if;
  if p_source_sha256 is null or p_manifest_sha256 is null or p_manifest_text is null or p_as_of is null or p_refreshed_at is null
     or encode(sha256(convert_to(p_manifest_text,'UTF8')),'hex')<>p_manifest_sha256 then raise exception 'SMI manifest hash mismatch'; end if;
  if (p_manifest_text::jsonb)->>'format' is distinct from '1' then raise exception 'SMI manifest format'; end if;
  recipe:=(p_manifest_text::jsonb)->'recipe';
  if recipe->>0 is distinct from 'o' then raise exception 'SMI root must be an object'; end if;
  full_text:=public.smi_sales_assemble(recipe);
  select jsonb_build_array('o',jsonb_agg(v order by ord)) into business
  from jsonb_array_elements(recipe->1) with ordinality t(v,ord) where (v->>0)::jsonb #>> '{}' not in ('sha256','refreshed_at');
  source_text:=public.smi_sales_assemble(business);
  if encode(sha256(convert_to(source_text,'UTF8')),'hex')<>p_source_sha256 then raise exception 'SMI source hash mismatch'; end if;
  payload:=full_text::jsonb;
  if payload->>'sha256' is distinct from p_source_sha256 or (payload->>'as_of')::date is distinct from p_as_of or (payload->>'refreshed_at')::timestamptz is distinct from p_refreshed_at then raise exception 'SMI metadata mismatch'; end if;
  insert into public.smi_sales_manifests(source_sha256,manifest_sha256,manifest_text,as_of,refreshed_at)
  values(p_source_sha256,p_manifest_sha256,p_manifest_text,p_as_of,p_refreshed_at) on conflict do nothing returning id into v_id;
  if v_id is null then select id into v_id from public.smi_sales_manifests where source_sha256=p_source_sha256;
  else
    insert into public.smi_sales_manifest_chunks select v_id,h from (select distinct public.smi_sales_chunk_refs(recipe) h) q;
  end if;
  return v_id;
end $$;

create function public.smi_sales_storage_state() returns jsonb language plpgsql stable security definer set search_path='' as $$
begin
  if auth.uid() is null then raise insufficient_privilege; end if;
  return (select jsonb_build_object('generation',generation,'snapshot_id',coalesce(legacy_id,-manifest_id),'event_id',event_id,'storage_format',case when manifest_id is null then 'legacy' else 'content-v1' end) from public.smi_sales_storage_current where singleton);
end $$;

-- All publication paths (legacy, v2, rollback) share this serialized transition.
-- Generation is never reset, so A->B->A does not authorize a stale publisher.
create function public.smi_sales_transition(p_legacy bigint,p_manifest bigint,p_expected bigint,p_rollback bigint default null)
returns bigint language plpgsql set search_path='' as $$
declare s public.smi_sales_storage_current%rowtype; event bigint;
begin
  perform pg_advisory_xact_lock(736491028);
  select * into strict s from public.smi_sales_storage_current where singleton for update;
  if p_expected is not null and s.generation<>p_expected then raise exception 'stale SMI publication generation'; end if;
  if num_nonnulls(p_legacy,p_manifest)<>1 then raise exception 'invalid SMI publication target'; end if;
  insert into public.smi_sales_publications(generation,legacy_id,manifest_id,prior_legacy_id,prior_manifest_id,prior_event_id,rollback_of)
  values(s.generation+1,p_legacy,p_manifest,s.legacy_id,s.manifest_id,s.event_id,p_rollback) returning id into event;
  update public.smi_sales_storage_current set legacy_id=p_legacy,manifest_id=p_manifest,generation=s.generation+1,event_id=event,checked_at=now(),legacy_writes_enabled=legacy_writes_enabled and p_manifest is null where singleton;
  if p_legacy is not null then
    update public.smi_sales_current set snapshot_id=p_legacy,promoted_at=now() where singleton;
  end if;
  return s.generation+1;
end $$;
create function public.smi_sales_publish_manifest(p_manifest_id bigint,p_expected_generation bigint) returns bigint language plpgsql security definer set search_path='' as $$
begin
  if coalesce(auth.jwt()->>'role','')<>'ar_current_promoter' then raise insufficient_privilege; end if;
  if p_expected_generation is null or p_manifest_id is null then raise exception 'SMI CAS parameters required'; end if;
  return public.smi_sales_transition(null,p_manifest_id,p_expected_generation);
end $$;
create function public.smi_sales_rollback(p_expected_generation bigint) returns bigint language plpgsql security definer set search_path='' as $$
declare s public.smi_sales_storage_current%rowtype; e public.smi_sales_publications%rowtype;
begin
  if coalesce(auth.jwt()->>'role','')<>'ar_current_promoter' then raise insufficient_privilege; end if;
  perform pg_advisory_xact_lock(736491028);
  select * into strict s from public.smi_sales_storage_current where singleton;
  if p_expected_generation is null or s.generation<>p_expected_generation then raise exception 'stale SMI rollback generation'; end if;
  select * into strict e from public.smi_sales_publications where id=s.event_id;
  return public.smi_sales_transition(e.prior_legacy_id,e.prior_manifest_id,s.generation,s.event_id);
end $$;

create function public.smi_sales_publish_legacy(p_snapshot_id bigint,p_expected_generation bigint) returns bigint language plpgsql security definer set search_path='' as $$
begin
  if coalesce(auth.jwt()->>'role','')<>'ar_current_promoter' then raise insufficient_privilege; end if;
  if p_snapshot_id is null or p_expected_generation is null then raise exception 'SMI CAS parameters required'; end if;
  return public.smi_sales_transition(p_snapshot_id,null,p_expected_generation);
end $$;

create or replace function public.smi_sales_promote_snapshot(p_snapshot_id bigint) returns void language plpgsql security definer set search_path='' as $$
begin
  if coalesce(auth.jwt()->>'role','')<>'ar_current_promoter' then raise insufficient_privilege using message='SMI sales promotion role required'; end if;
  perform pg_advisory_xact_lock(736491028);
  if not (select legacy_writes_enabled from public.smi_sales_storage_current where singleton) then raise exception 'SMI legacy publisher retired; use CAS-protected legacy publication'; end if;
  perform public.smi_sales_transition(p_snapshot_id,null,null);
end $$;
create or replace function public.smi_sales_heartbeat_snapshot(p_snapshot_id bigint) returns boolean language plpgsql security definer set search_path='' as $$
declare touched boolean;
begin
  if coalesce(auth.jwt()->>'role','')<>'ar_current_promoter' then raise insufficient_privilege using message='SMI sales promotion role required'; end if;
  perform pg_advisory_xact_lock(736491028);
  update public.smi_sales_storage_current set checked_at=now() where singleton and coalesce(legacy_id,-manifest_id)=p_snapshot_id;
  touched:=found;
  if touched and p_snapshot_id>0 then update public.smi_sales_current set promoted_at=now() where singleton and snapshot_id=p_snapshot_id; end if;
  return touched;
end $$;
create or replace function public.smi_sales_snapshot_metadata()
returns table(snapshot_id bigint,source_sha256 text,as_of date,refreshed_at timestamptz,promoted_at timestamptz)
language sql stable security definer set search_path='' as $$
  select coalesce(c.legacy_id,-c.manifest_id),coalesce(s.source_sha256,m.source_sha256),coalesce(s.as_of,m.as_of),coalesce(s.refreshed_at,m.refreshed_at),c.checked_at
  from public.smi_sales_storage_current c left join public.smi_sales_snapshots s on s.id=c.legacy_id left join public.smi_sales_manifests m on m.id=c.manifest_id
  where c.singleton and auth.uid() is not null
$$;
create or replace function public.smi_sales_current_snapshot() returns jsonb language plpgsql stable security definer set search_path='' as $$
declare p jsonb;
begin
  if auth.uid() is null then raise insufficient_privilege using message='authentication required'; end if;
  select case when c.legacy_id is not null then s.payload else public.smi_sales_assemble(m.manifest_text::jsonb->'recipe')::jsonb end into p
  from public.smi_sales_storage_current c left join public.smi_sales_snapshots s on s.id=c.legacy_id left join public.smi_sales_manifests m on m.id=c.manifest_id where c.singleton;
  if p is null then raise exception 'SMI sales snapshot is unavailable'; end if;
  return p;
end $$;

-- RLS with no policies, no direct data grants. Default function PUBLIC execute
-- is removed explicitly, including internal helpers. Legacy ACLs are retained.
create function public.smi_sales_manifest_payload(p_manifest_id bigint) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare p jsonb;
begin
  if coalesce(auth.jwt()->>'role','')<>'ar_current_operator' or auth.uid() is null then raise insufficient_privilege; end if;
  select public.smi_sales_assemble(manifest_text::jsonb->'recipe')::jsonb into p from public.smi_sales_manifests where id=p_manifest_id;
  if p is null then raise exception 'SMI manifest unavailable'; end if;
  return p;
end $$;
revoke all on function public.smi_sales_manifest_payload(bigint) from public,anon,authenticated,ar_current_ingest,ar_current_promoter,service_role;
grant execute on function public.smi_sales_manifest_payload(bigint) to ar_current_operator;

alter table public.smi_sales_chunks enable row level security;
alter table public.smi_sales_manifests enable row level security;
alter table public.smi_sales_manifest_chunks enable row level security;
alter table public.smi_sales_publications enable row level security;
alter table public.smi_sales_storage_current enable row level security;
revoke all on public.smi_sales_chunks,public.smi_sales_manifests,public.smi_sales_manifest_chunks,public.smi_sales_publications,public.smi_sales_storage_current from public,anon,authenticated,ar_current_ingest,ar_current_promoter,ar_current_operator;
revoke all on function public.smi_sales_immutable(),public.smi_sales_json_key(text),public.smi_sales_assemble(jsonb,integer),public.smi_sales_chunk_refs(jsonb),public.smi_sales_transition(bigint,bigint,bigint,bigint),public.smi_sales_missing_chunks(text[]),public.smi_sales_put_chunks(jsonb),public.smi_sales_stage_manifest(text,date,timestamptz,text,text),public.smi_sales_storage_state(),public.smi_sales_publish_manifest(bigint,bigint),public.smi_sales_rollback(bigint) from public,anon,authenticated,ar_current_ingest,ar_current_promoter,ar_current_operator;
grant execute on function public.smi_sales_missing_chunks(text[]),public.smi_sales_put_chunks(jsonb),public.smi_sales_stage_manifest(text,date,timestamptz,text,text) to ar_current_ingest;
grant execute on function public.smi_sales_publish_manifest(bigint,bigint),public.smi_sales_rollback(bigint) to ar_current_promoter;
grant execute on function public.smi_sales_storage_state() to ar_current_operator;
revoke all on function public.smi_sales_publish_legacy(bigint,bigint) from public,anon,authenticated,ar_current_ingest,ar_current_operator;
grant execute on function public.smi_sales_publish_legacy(bigint,bigint) to ar_current_promoter;
-- Supabase may apply broad default privileges to newly-created objects.
revoke all on public.smi_sales_chunks,public.smi_sales_manifests,public.smi_sales_manifest_chunks,public.smi_sales_publications,public.smi_sales_storage_current from service_role;
revoke all on sequence public.smi_sales_manifests_id_seq,public.smi_sales_publications_id_seq from public,anon,authenticated,ar_current_ingest,ar_current_promoter,ar_current_operator,service_role;
revoke all on function public.smi_sales_immutable(),public.smi_sales_json_key(text),public.smi_sales_assemble(jsonb,integer),public.smi_sales_chunk_refs(jsonb),public.smi_sales_transition(bigint,bigint,bigint,bigint),public.smi_sales_missing_chunks(text[]),public.smi_sales_put_chunks(jsonb),public.smi_sales_stage_manifest(text,date,timestamptz,text,text),public.smi_sales_storage_state(),public.smi_sales_publish_manifest(bigint,bigint),public.smi_sales_rollback(bigint),public.smi_sales_publish_legacy(bigint,bigint) from service_role;
comment on table public.smi_sales_publications is 'Immutable SMI-only promotion/rollback provenance. Current and last two distinct prior promoted versions are the deliberate instant rollback set; no deletion authorized by this migration.';
comment on table public.smi_sales_chunks is 'Verified canonical UTF-8 content, reused across SMI refreshes; historical corrections produce new hashes. No cleanup or expiry.';
notify pgrst, 'reload schema';
commit;
