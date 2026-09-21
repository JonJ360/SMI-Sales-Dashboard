"""Hourly SMI Sales SQL-to-Supabase refresh. Silent on success."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

PYTHON = r"C:\Users\jonj\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
ROOT = Path(r"C:\Users\jonj\OneDrive\360\360 Solutions\Clients\360 Solutions LLC\A.I\GitHub\SMI-Sales-Dashboard")
DATA = ROOT / "data" / "sales.json"
CREDS = Path(r"C:\Users\jonj\AppData\Local\hermes\arcrm\credentials\current-ar.json")
LOG = Path(r"C:\Users\jonj\AppData\Local\hermes\logs\smi-sales-refresh.json")


def run(args: list[str]) -> str:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=150)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "unknown failure").strip())
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--single-attempt", action="store_true", help="Disable publisher RPC retries for a controlled run.")
    args = parser.parse_args()
    try:
        extract = run([PYTHON, "scripts/sales_sync.py", "--output", str(DATA)])
        publish_args = [PYTHON, "scripts/publish_snapshot.py", "--snapshot", str(DATA), "--credentials", str(CREDS)]
        if args.single_attempt:
            publish_args.append("--single-attempt")
        publish = run(publish_args)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text(json.dumps({"ok": True, "at": dt.datetime.now(dt.timezone.utc).isoformat(), "extract": json.loads(extract), "publish": json.loads(publish)}, indent=2), encoding="utf-8")
    except Exception as exc:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text(json.dumps({"ok": False, "at": dt.datetime.now(dt.timezone.utc).isoformat(), "error": str(exc)}, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
