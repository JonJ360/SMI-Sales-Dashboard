-- SMI-only performance repair. No data, ACL, timeout or serving API changes.
begin;
set local lock_timeout='5s';
do $$ begin
  if md5(pg_get_functiondef('public.smi_sales_assemble(jsonb,integer)'::regprocedure)) <> 'acc3953919b89bde4c41c07353a61eec' then
    raise exception 'SMI assembler preimage drift';
  end if;
end $$;
create or replace function public.smi_sales_assemble(p jsonb, depth integer default 0) returns text
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
    with assembled as materialized (
      select public.smi_sales_assemble(v,depth+1) s,ord
      from jsonb_array_elements(p->1) with ordinality t(v,ord)
    )
    select '['||coalesce(string_agg(nullif(substr(s,2,length(s)-2),''),',' order by ord),'')||']' into r
    from assembled;
  elsif kind='m' then
    with entries as materialized (
      select e.key,e.value from jsonb_array_elements(p->1) t(v)
      cross join lateral json_each(public.smi_sales_assemble(v,depth+1)::json) e
    )
    select count(*),count(distinct e.key),
      '{'||coalesce(string_agg(public.smi_sales_json_key(e.key)||':'||e.value::text,',' order by e.key collate "C"),'')||'}'
    into n,u,r from entries e;
    if n<>u then raise exception 'duplicate SMI merge key'; end if;
  else raise exception 'unknown SMI recipe';
  end if;
  return r;
end $$;
commit;
