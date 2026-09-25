"""Execute the production JS model, including all real-snapshot branch scopes."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_branch_model():
    result = subprocess.run(['node', '--test', 'tests/branch-model.test.cjs'], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
