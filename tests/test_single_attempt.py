"""Offline transport regressions for the controlled publication mode."""
import importlib.util
import sys
from pathlib import Path
import io
import json
import urllib.error
from unittest import mock

import pytest
from test_publish_snapshot import publish_snapshot as publisher


@pytest.mark.parametrize("failure", [TimeoutError("timeout"), urllib.error.URLError("offline"), *[
    urllib.error.HTTPError("https://example.test", code, "unavailable", {}, io.BytesIO(b"error"))
    for code in (502, 503, 504, 520, 521, 522)
]])
def test_single_attempt_never_replays_transport(failure):
    with mock.patch.object(publisher.urllib.request, "urlopen", side_effect=failure) as send, mock.patch.object(publisher.time, "sleep") as sleep:
        with pytest.raises((RuntimeError, TimeoutError, urllib.error.URLError)):
            publisher.rpc("https://example.test", "key", "ingest", "stage", {}, single_attempt=True)
    assert send.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("failure", [TimeoutError("stage timeout"), urllib.error.HTTPError("https://example.test", 521, "down", {}, io.BytesIO(b"down"))])
def test_normal_entrypoint_single_attempt_stops_after_failed_stage(tmp_path, failure):
    from test_publish_snapshot import _Response, valid_snapshot

    wrapper_path = Path(__file__).resolve().parents[1] / "scripts/smi_sales_refresh.py"
    if not wrapper_path.exists():
        pytest.skip("local operational entrypoint is not installed on this machine")
    spec = importlib.util.spec_from_file_location("refresh_under_test", wrapper_path)
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    snapshot = valid_snapshot()
    data = tmp_path / "sales.json"
    data.write_text(json.dumps(snapshot))
    creds = tmp_path / "credentials.json"
    creds.write_text(json.dumps({"supabase_url": "https://example.test", "publishable_key": "key", "current_ar_ingestion_key": "ingest", "current_ar_promotion_key": "promote", "operator_verification_key": "verify"}))
    commands = []

    def offline_child(args):
        commands.append(args)
        if args[1] == "scripts/sales_sync.py":
            return "{}"
        with mock.patch.object(sys, "argv", args[1:]):
            publisher.main()
        pytest.fail("failed stage must abort publication")

    log = tmp_path / "refresh.json"
    with mock.patch.multiple(wrapper, DATA=data, CREDS=creds, LOG=log), mock.patch.object(wrapper, "run", side_effect=offline_child), mock.patch.object(sys, "argv", [str(wrapper_path), "--single-attempt"]), mock.patch.object(publisher.urllib.request, "urlopen", side_effect=[_Response([]), failure]) as send, mock.patch.object(publisher.time, "sleep") as sleep:
        with pytest.raises((TimeoutError, RuntimeError)):
            wrapper.main()
    assert len(commands) == 2
    assert commands[1][-1] == "--single-attempt"
    assert [call.args[0].full_url.rsplit("/", 1)[-1] for call in send.call_args_list] == ["smi_sales_snapshot_metadata", "smi_sales_stage_snapshot"]
    assert [call.args[0].get_header("Authorization") for call in send.call_args_list] == ["Bearer verify", "Bearer ingest"]
    assert json.loads(log.read_text())["ok"] is False
    sleep.assert_not_called()


@pytest.mark.parametrize("single_attempt", [False, True])
@pytest.mark.parametrize("unchanged", [False, True])
def test_success_keeps_scoped_roles_and_verification(tmp_path, single_attempt, unchanged):
    from test_publish_snapshot import valid_snapshot
    snapshot = valid_snapshot()
    path = tmp_path / "sales.json"
    path.write_text(json.dumps(snapshot))
    row = {"snapshot_id": 182, "source_sha256": snapshot["sha256"]}
    credentials = {"supabase_url": "https://example.test", "publishable_key": "key", "current_ar_ingestion_key": "ingest", "current_ar_promotion_key": "promote", "operator_verification_key": "verify"}
    responses = [[row], True, [row]] if unchanged else [[], 182, None, [row]]
    with mock.patch.object(publisher, "load_credentials", return_value=credentials), mock.patch.object(publisher, "rpc", side_effect=responses) as rpc:
        result = publisher.publish(path, tmp_path / "unused.json", single_attempt=single_attempt)
    assert result["verified"] is True
    assert result["skipped"] is unchanged
    assert [c.args[2] for c in rpc.call_args_list] == (["verify", "promote", "verify"] if unchanged else ["verify", "ingest", "promote", "verify"])
    assert all(c.kwargs == {"single_attempt": single_attempt} for c in rpc.call_args_list)


def test_normal_entrypoint_default_does_not_enable_option(tmp_path):
    wrapper_path = Path(__file__).resolve().parents[1] / "scripts/smi_sales_refresh.py"
    if not wrapper_path.exists():
        pytest.skip("local operational entrypoint is not installed on this machine")
    spec = importlib.util.spec_from_file_location("refresh_default_test", wrapper_path)
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    with mock.patch.object(sys, "argv", [str(wrapper_path)]), mock.patch.object(wrapper, "LOG", tmp_path / "log.json"), mock.patch.object(wrapper, "run", return_value="{}") as run:
        wrapper.main()
    assert run.call_count == 2
    assert "--single-attempt" not in run.call_args.args[0]

