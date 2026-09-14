import importlib.util
import json
import socket
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "publish_snapshot.py"
SPEC = importlib.util.spec_from_file_location("publish_snapshot", MODULE_PATH)
publish_snapshot = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(publish_snapshot)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class PublishSnapshotRetryTests(unittest.TestCase):
    @mock.patch.object(publish_snapshot.time, "sleep")
    @mock.patch.object(publish_snapshot.urllib.request, "urlopen")
    def test_rpc_retries_one_transient_read_timeout(self, urlopen, sleep):
        urlopen.side_effect = [socket.timeout("timed out"), _Response(177)]

        result = publish_snapshot.rpc("https://example.test", "key", "token", "stage", {"x": 1})

        self.assertEqual(result, 177)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(2)


if __name__ == "__main__":
    unittest.main()
