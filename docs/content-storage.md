# SMI content-addressed storage v1

Scope: SMI Sales only, shared project `inhwadbibwkakacdvoxu`. No UI, calculation, source SQL, AR/GL, or scheduler changes. No historical deletion or disk-reclaim claim.

## Contract

The unchanged complete SELECT-only extract checks every historical period on each refresh. `content_storage.py` encodes immutable monthly invoice document/line chunks plus other top-level sections. SHA-256 addresses canonical ASCII JSON text, retaining order and number spelling. Changed old periods are detected, not assumed closed. Only missing chunks are uploaded; an immutable recipe manifest references the complete chunk closure.

`005_content_storage.sql` preimage-guards five existing SMI RPCs. New objects are SMI-only, RLS enabled, and inaccessible directly to anon/authenticated/ingest/promoter/operator/service_role. SECURITY DEFINER functions use empty search_path, fully qualified targets, role/UID checks and scoped EXECUTE grants. No default privileges or shared role timeout changes. The stage timeout follows the existing ingestion function; the outer serving statement budget remains 8 seconds.

A row-locked singleton serializes generation-CAS publication and rollback. Every pointer transition records old/new immutable references in an append-only event. Rollback requires the current event ID and advances generation, preventing stale/ABA requests. First content promotion fences old non-CAS legacy promotion. Explicit `--storage legacy` uses protected generation-CAS and a full snapshot; do not blindly revert to the old publisher. Existing metadata and serving RPC shape remains unchanged; negative snapshot IDs identify manifests. Frontend never dereferences IDs directly.

Current plus two distinct preceding promoted versions is the minimum intended rollback set. This release preserves **all** legacy rows, chunks, manifests and events; no retention purge is implemented. Retained history is not an off-site backup.

## Publisher integration and activation

`publish_snapshot.py` CLI defaults to `content-v1`; its Python compatibility entrypoint retains legacy-v1 default for existing callers/tests. Runtime invokes the CLI through unchanged `smi_sales_refresh_scheduled.py -> smi_sales_refresh.py --single-attempt`. Content protocol always sends each mutation once, even in manual invocations. A failed response is indeterminate: read storage state, metadata, manifest and events before deciding what to do. Never automatically replay publication.

Apply the additive migration first, compare ledger statement SHA-256 with this file, read back ACLs/RLS/functions, stage a shadow manifest through existing scoped identities, and compare the entire payload. Measure production SQL under the unchanged 8-second budget before activating canonical CLI code. Whole-response network transfer/JSON parsing is separate from SQL statement duration and may exceed 8 seconds for the 62MB payload.

## Verified release evidence

Private operator evidence: `C:/Users/jonj/AppData/Local/hermes/reports/smi-dedup-20260928/`.
- Latest complete isolated native PostgreSQL run: 126 passed, including full real source payload, concurrency, privileges, missing closure, lost-response, CAS and rollback tests. `run-final/tests.xml`; fixture cluster stopped.
- Full local payload compact size 62,424,179 bytes, 446 chunks, 43,122-byte manifest. Local complete serving 3.797 seconds under enforced 8-second statement timeout.
- Production migration `20260929033447`, `smi_content_storage_v1`. Exact ledger/local SHA-256 `8440b2b3d44b6707e1c590d302203c37ee1336e95f3b96549f0db7423833d8ed`.
- Shadow manifest 1: all 446 chunks read back present; complete recursive payload equality; legacy current 1980 remained unchanged. Production assembly/JSONB execution 4.566534 seconds with `statement_timeout=8s`; full authenticated HTTP transfer plus parse 10.484 seconds. Staging 7.297 seconds. These are bounded measurements, not a peak-load guarantee.
- Source hash `f6392f5fded57f46a4685b6dc23c6161d531b8ff0c7475fa54b5148bcb626216`.
- Enabled by fast-forwarding the canonical runtime to code commit `475f8198d22a4afef9171c6b7aea1b8af5558f95`, without editing or manually firing cron. Natural builtin execution `8fe170146d064c6aa6f59b4a5f32fc39` promoted manifest 1 (snapshot -1), event/generation 1 at `2026-09-29T03:40:50.230448Z`, reusing all 446 shadow chunks and uploading zero content bytes. Prior legacy snapshot 1980 is pinned in the event.
- Following builtin execution `6b4de268b4bb4a2f9ed9937b69c1ba4b` completed at `2026-09-29T03:47:40.053588Z`, verified unchanged-source heartbeat with no new manifest/event/chunk. All 955 historical legacy rows remain. Full business equality after both runs; the only local/stored difference is expected `refreshed_at`.
- Final serving HTTP response headers at 6.748 seconds, full transfer 8.973 seconds, complete parse 10.378 seconds. SQL remains under its 8-second budget; **end-to-end delivery is not under 8 seconds**. No timeout/auth changes were made.
- Scheduler remains enabled, five-minute interval, existing single-attempt adapter, last status OK, failure streak zero. Database postmaster remained `2026-09-22T12:21:54.945111Z`. Static index and both referenced JS assets remain byte-equivalent after newline normalization; UI version stays 1.19.
- Canonical architecture source override, SMI Markdown/HTML, and manifest entry were updated in the private 360 Architecture library; all 16 unrelated app entries and 34 unrelated app/master files were unchanged. Diagram renderer passed 18 pages, with SMI diagram visually inspected. No new signed-in browser walkthrough or production rollback was performed.

Local one-cent current-period change experiment added one 55,580-byte compressed chunk plus manifest/ref rows instead of a 30,959,846-byte compressed full snapshot. This is an isolated estimate, not measured production savings, free space, or reclaim.

## Reproduce local database gate

Run `tools/run_storage_tests.py --bin <portable-pg-bin> --deps <psycopg-deps> --work <NEW-isolated-directory> --payload <private-sales.json>` with the approved Python interpreter. No production credentials are accepted. The harness initializes loopback-only PostgreSQL, loads historical SMI migrations, applies the proposal, runs all tests, and stops/verifies the cluster. Real payload test is skipped without `--payload`; do not claim complete acceptance on the skipped run.
