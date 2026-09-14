begin;

-- Six-year comparison snapshots are approximately 12 MB. Allow the
-- role-restricted ingestion function enough time to parse and store JSONB.
alter function public.smi_sales_stage_snapshot(text, date, timestamptz, jsonb)
  set statement_timeout = '120s';

commit;
