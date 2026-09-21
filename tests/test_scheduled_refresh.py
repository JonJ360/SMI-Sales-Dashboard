"""Scheduled entrypoint must enable no-replay without changing manual defaults."""
import runpy
import sys
import types
from pathlib import Path
from unittest import mock
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'smi_sales_refresh_scheduled.py'

@pytest.mark.parametrize('fail', [False, True])
def test_scheduled_entrypoint_forces_single_attempt_and_propagates_failure(fail):
    calls = []
    def main():
        calls.append(sys.argv[:])
        if fail:
            raise RuntimeError('indeterminate publish: do not replay')
    fake = types.ModuleType('smi_sales_refresh')
    fake.main = main
    with mock.patch.dict(sys.modules, smi_sales_refresh=fake), mock.patch.object(sys, 'argv', [str(SCRIPT)]):
        if fail:
            with pytest.raises(RuntimeError, match='do not replay'):
                runpy.run_path(str(SCRIPT), run_name='__main__')
        else:
            runpy.run_path(str(SCRIPT), run_name='__main__')
    assert len(calls) == 1
    assert calls[0][1:] == ['--single-attempt']
