"""Scoped SMI content publisher. Every mutation is sent once, never replayed."""
from functools import partial

try:
    from .content_storage import build, batches
    from .publish_snapshot import rpc
except ImportError:  # direct scripts/publish_snapshot.py entrypoint
    from content_storage import build, batches
    from publish_snapshot import rpc


def publish_content(snapshot, credentials, *, legacy=False):
    base, key = credentials['supabase_url'], credentials['publishable_key']
    if base != 'https://inhwadbibwkakacdvoxu.supabase.co':
        raise RuntimeError('SMI content target mismatch')
    # This protocol is deliberately single-attempt even for manual invocations.
    call = partial(rpc, single_attempt=True)
    def invoke(role, name, payload):
        return call(base, key, credentials[role], name, payload)
    operator = 'operator_verification_key'
    ingest = 'current_ar_ingestion_key'
    promoter = 'current_ar_promotion_key'
    baseline = invoke(operator, 'smi_sales_storage_state', {})
    metadata = invoke(operator, 'smi_sales_snapshot_metadata', {})
    current = metadata[0] if isinstance(metadata, list) and metadata else {}
    if current.get('snapshot_id') != baseline.get('snapshot_id'):
        raise RuntimeError('SMI current changed during baseline read; no publication attempted')
    desired_format = 'legacy' if legacy else 'content-v1'
    if baseline.get('storage_format') == desired_format and current.get('source_sha256') == snapshot['sha256']:
        touched = invoke(promoter, 'smi_sales_heartbeat_snapshot', {'p_snapshot_id': current['snapshot_id']})
        rows = invoke(operator, 'smi_sales_snapshot_metadata', {})
        row = rows[0] if rows else {}
        if not touched or row.get('snapshot_id') != current['snapshot_id'] or row.get('source_sha256') != snapshot['sha256']:
            raise RuntimeError('SMI content heartbeat raced; no replay')
        return dict(snapshot_id=row['snapshot_id'], source_sha256=row['source_sha256'], as_of=row['as_of'],
                    refreshed_at=row['promoted_at'], verified=True, skipped=True, storage_format=desired_format)
    if legacy:
        snapshot_id = invoke(ingest, 'smi_sales_stage_snapshot', {
            'p_source_sha256': snapshot['sha256'], 'p_as_of': snapshot['as_of'],
            'p_refreshed_at': snapshot['refreshed_at'], 'p_payload': snapshot})
        generation = invoke(promoter, 'smi_sales_publish_legacy', {
            'p_snapshot_id': snapshot_id, 'p_expected_generation': baseline['generation']})
        after = invoke(operator, 'smi_sales_storage_state', {})
        rows = invoke(operator, 'smi_sales_snapshot_metadata', {})
        row = rows[0] if rows else {}
        if after.get('generation') != generation or after.get('snapshot_id') != snapshot_id or row.get('snapshot_id') != snapshot_id or row.get('source_sha256') != snapshot['sha256']:
            raise RuntimeError('SMI legacy publication readback mismatch; no replay')
        return dict(snapshot_id=snapshot_id, source_sha256=row['source_sha256'], as_of=row['as_of'],
                    refreshed_at=row['promoted_at'], verified=True, skipped=False, storage_format='legacy', generation=generation)
    content = build(snapshot)
    missing = invoke(ingest, 'smi_sales_missing_chunks', {'p_hashes': list(content['chunks'])})
    if not isinstance(missing, list) or set(missing) - content['chunks'].keys():
        raise RuntimeError('invalid SMI missing-chunk response')
    upload_bytes = 0
    for batch in batches({h: content['chunks'][h] for h in missing}):
        invoke(ingest, 'smi_sales_put_chunks', {'p_chunks': batch})
        upload_bytes += sum(len(text.encode('utf8')) for text in batch.values())
    manifest_id = invoke(ingest, 'smi_sales_stage_manifest', {
        'p_source_sha256': snapshot['sha256'], 'p_as_of': snapshot['as_of'],
        'p_refreshed_at': snapshot['refreshed_at'], 'p_manifest_sha256': content['manifest_sha256'],
        'p_manifest_text': content['manifest_text']})
    generation = invoke(promoter, 'smi_sales_publish_manifest', {
        'p_manifest_id': manifest_id, 'p_expected_generation': baseline['generation']})
    after = invoke(operator, 'smi_sales_storage_state', {})
    rows = invoke(operator, 'smi_sales_snapshot_metadata', {})
    row = rows[0] if rows else {}
    if after.get('generation') != generation or after.get('snapshot_id') != -manifest_id or row.get('snapshot_id') != -manifest_id or row.get('source_sha256') != snapshot['sha256']:
        raise RuntimeError('SMI content publication readback mismatch; no replay')
    return dict(snapshot_id=-manifest_id, source_sha256=row['source_sha256'], as_of=row['as_of'],
                refreshed_at=row['promoted_at'], verified=True, skipped=False, storage_format='content-v1',
                generation=generation, chunk_count=len(content['chunks']), uploaded_chunks=len(missing),
                uploaded_content_bytes=upload_bytes, manifest_bytes=len(content['manifest_text'].encode('utf8')))
