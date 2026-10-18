# SMI serving repair — 2026-10-18

Scope: SMI Sales only, project `inhwadbibwkakacdvoxu`. No data deletion, publication, refresh trigger, scheduler modification, role/global timeout change, tier change, or other app change.

## Evidence
- Before: authenticated operator GET `smi_sales_current_snapshot` returned HTTP 500 / PostgreSQL `57014` in 8.455 seconds. This was a server cancellation, not a client/network timeout.
- Regression instrumentation on actual isolated PostgreSQL proved a three-node nested array recipe called the assembler seven times. Materialization reduces this to three. Merge entries are now evaluated once while preserving duplicate detection, canonical numeric spelling, and C-collation ordering.
- Production canonical assembly after repair: EXPLAIN ANALYZE 3332.967 ms. Complete JSONB conversion/serialization measured 8458.494 ms: the default 8-second budget was still insufficient.
- Added **only** `smi_sales_current_snapshot()` function-local `statement_timeout=20s` and reloaded PostgREST schema. Existing authenticated/authenticator defaults remain 8s. This is not a global/role budget change.
- Full authenticated GET succeeded twice: 13.720s and 14.009s, 71,461,850 response bytes each. Decoded payload equals local `data/sales.json` in every field except the expected unchanged-source `refreshed_at` heartbeat difference.
- Natural five-minute scheduler completed successfully at 15:07:38 CDT, with checked_at `2026-10-18T20:07:38.631513+00:00`; next due 15:12:38 CDT. No manual refresh was triggered. A third full GET after that natural completion returned HTTP 200 in 18.932s and again matched all source fields except `refreshed_at` (`smi-natural.json`).
- Source SHA256: `4bfdf36ff3fbaf265e6b9d516d42ad1146b280b89fc6042a375b13c6d067a6da`; manifest 1355, serving snapshot -1355; generation/event 1354 unchanged.

## Production readback handles
- Migration `20261018200121`, `smi_assemble_single_evaluation`.
- Migration `20261018200401`, `smi_current_snapshot_budget`.
- `md5(pg_get_functiondef('public.smi_sales_assemble(jsonb,integer)'::regprocedure))` = `7eed5157ce4f7c51f486d045fbc629ef`.
- `md5(pg_get_functiondef('public.smi_sales_current_snapshot()'::regprocedure))` = `a2259299aadafbe976e79281b4a525e5`.
- Assembler owner postgres, ACL `{postgres=X/postgres}`, invoker, config `search_path=""`.
- Serving owner postgres, ACL `{postgres=X/postgres,authenticated=X/postgres,ar_current_operator=X/postgres}`, security definer, config `search_path=""`, `statement_timeout=20s`. Body unchanged.

## Tests
- Real PostgreSQL red: expected 3 recursive calls, observed 7.
- Final: 130 passed, 1 deselected, including full private real payload, canonical source hash, duplicate merge keys, ACL denials, immutable data, concurrent publishers, rollback/CAS and lost-response tests.
- Full suite before and after also has one unrelated pre-existing failure: `SalesSyncTests.test_extract_includes_margin_exception_report` uses a September fixture and returns 0 rather than expected 1 in this environment. It failed before the repair too. Not modified; excluded only in the final confirming run. Full failing outputs retained.
- Experimental direct-JSONB assembler was slower in local full-payload test and was discarded, never deployed.

## Durable artifacts
`C:/Users/jonj/OneDrive/Hermes/Documents/Apps Repair 20261018/`
- `smi-before.json`, `smi-after.json` (assembly-only still failed), `smi-final.json`, `smi-confirmed.json`.
- `smi_verify.py`: GET-only full payload equality verification, no payload/secret persisted.
- `smi-red3/tests.txt`, `smi-green/payload-storage.json`, `smi-final-tests/tests.txt`, `smi-verified-tests/tests.txt`, `tests.xml`, `payload-storage.json`, `cleanup.json` in corresponding test directories. Isolated PostgreSQL clusters stopped after every run.
