import copy
from unittest.mock import patch
import pytest
from scripts.publish_content import publish_content
from scripts.content_storage import build
from test_content_storage import sample

CREDS={'supabase_url':'https://inhwadbibwkakacdvoxu.supabase.co','publishable_key':'public',
       'operator_verification_key':'operator','current_ar_ingestion_key':'ingest','current_ar_promotion_key':'promoter'}


def test_publisher_uploads_only_missing_and_cas_verifies():
    p=sample(); b=build(p); missing=list(b['chunks'])[:1]; calls=[]
    states=iter([{'generation':5,'snapshot_id':1980,'storage_format':'legacy'}, {'generation':6,'snapshot_id':-7}])
    metas=iter([[{'snapshot_id':1980,'source_sha256':p['sha256']}], [{'snapshot_id':-7,'source_sha256':p['sha256'],'as_of':p['as_of'],'promoted_at':p['refreshed_at']} ]])
    def rpc(base,key,token,name,payload,**kwargs):
        assert kwargs=={'single_attempt':True}; calls.append((name,payload))
        if name=='smi_sales_storage_state': return next(states)
        if name=='smi_sales_snapshot_metadata': return next(metas)
        if name=='smi_sales_missing_chunks': return missing
        if name=='smi_sales_put_chunks': assert list(payload['p_chunks'])==missing; return 1
        if name=='smi_sales_stage_manifest': return 7
        if name=='smi_sales_publish_manifest': assert payload=={'p_manifest_id':7,'p_expected_generation':5}; return 6
        raise AssertionError(name)
    with patch('scripts.publish_content.rpc',rpc): result=publish_content(p,CREDS)
    assert result['verified'] and result['uploaded_chunks']==1


def test_failed_mutation_is_not_replayed_or_promoted():
    p=sample(); calls=[]
    def rpc(base,key,token,name,payload,**kwargs):
        calls.append(name)
        if name=='smi_sales_storage_state': return {'generation':1,'snapshot_id':1,'storage_format':'legacy'}
        if name=='smi_sales_snapshot_metadata': return [{'snapshot_id':1,'source_sha256':'a'*64}]
        if name=='smi_sales_missing_chunks': return list(build(p)['chunks'])
        if name=='smi_sales_put_chunks': raise TimeoutError('commit outcome unknown')
        raise AssertionError(name)
    with patch('scripts.publish_content.rpc',rpc),pytest.raises(TimeoutError): publish_content(p,CREDS)
    assert calls.count('smi_sales_put_chunks')==1
    assert 'smi_sales_publish_manifest' not in calls


def test_wrong_target_and_stale_baseline_fail_closed():
    c=dict(CREDS,supabase_url='https://other.supabase.co')
    with pytest.raises(RuntimeError,match='target'): publish_content(sample(),c)
    with patch('scripts.publish_content.rpc',side_effect=[{'snapshot_id':1},[{'snapshot_id':2}]]),pytest.raises(RuntimeError,match='baseline'):
        publish_content(sample(),CREDS)


def test_explicit_legacy_rollback_uses_cas_not_old_promote():
    p=sample(); states=iter([{'generation':5,'snapshot_id':-7,'storage_format':'content-v1'}, {'generation':6,'snapshot_id':1980}]); metas=iter([[{'snapshot_id':-7,'source_sha256':p['sha256']}],[{'snapshot_id':1980,'source_sha256':p['sha256'],'as_of':p['as_of'],'promoted_at':p['refreshed_at']}]])
    def rpc(base,key,token,name,payload,**kwargs):
        assert kwargs['single_attempt']
        if name=='smi_sales_storage_state': return next(states)
        if name=='smi_sales_snapshot_metadata': return next(metas)
        if name=='smi_sales_stage_snapshot': return 1980
        if name=='smi_sales_publish_legacy': assert payload=={'p_snapshot_id':1980,'p_expected_generation':5}; return 6
        raise AssertionError(name)
    with patch('scripts.publish_content.rpc',rpc): assert publish_content(p,CREDS,legacy=True)['snapshot_id']==1980
