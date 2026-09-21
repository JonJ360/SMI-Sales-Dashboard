"""Stage, promote, and verify an SMI Sales snapshot in Supabase."""
from __future__ import annotations

import argparse
import hashlib
from functools import partial
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def load_credentials(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "service_role_key" in data:
        raise RuntimeError("service-role credentials are forbidden")
    required = ("supabase_url", "publishable_key", "current_ar_ingestion_key", "current_ar_promotion_key", "operator_verification_key")
    missing = [name for name in required if not isinstance(data.get(name), str) or not data[name]]
    if missing:
        raise RuntimeError("credential file is missing: " + ", ".join(missing))
    return {name: data[name].rstrip("/") if name == "supabase_url" else data[name] for name in required}


def source_sha256(snapshot: dict[str, Any]) -> str:
    source = {key: value for key, value in snapshot.items() if key not in {"refreshed_at", "sha256"}}
    canonical = json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def rpc(base: str, publishable: str, token: str, name: str, payload: dict[str, Any], *, single_attempt: bool = False) -> Any:
    request = urllib.request.Request(
        f"{base}/rest/v1/rpc/{name}",
        data=json.dumps(payload, separators=(",", ":")).encode(),
        method="POST",
        headers={"apikey": publishable, "Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    attempts = 1 if single_attempt else 2
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read().decode()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            if exc.code in {502, 503, 504, 520, 521, 522} and attempt + 1 < attempts:
                time.sleep(2)
                continue
            raise RuntimeError(f"{name} failed: HTTP {exc.code} {detail[:500]}") from None
        except (TimeoutError, urllib.error.URLError):
            if attempt + 1 == attempts:
                raise
            time.sleep(2)
    raise RuntimeError(f"{name} failed without a response")


def publish(snapshot_path: Path, credential_path: Path, *, single_attempt: bool = False) -> dict[str, Any]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("sha256") != source_sha256(snapshot):
        raise RuntimeError("snapshot integrity verification failed")
    credentials = load_credentials(credential_path)
    base, key = credentials["supabase_url"], credentials["publishable_key"]
    call_rpc = partial(rpc, single_attempt=single_attempt)
    metadata = call_rpc(base, key, credentials["operator_verification_key"], "smi_sales_snapshot_metadata", {})
    current = metadata[0] if isinstance(metadata, list) and metadata else {}
    if current.get("source_sha256") == snapshot["sha256"]:
        touched = call_rpc(base, key, credentials["current_ar_promotion_key"], "smi_sales_heartbeat_snapshot", {"p_snapshot_id": current["snapshot_id"]})
        metadata = call_rpc(base, key, credentials["operator_verification_key"], "smi_sales_snapshot_metadata", {})
        row = metadata[0] if isinstance(metadata, list) and metadata else {}
        if not touched:
            return {"snapshot_id": row.get("snapshot_id"), "source_sha256": row.get("source_sha256"), "as_of": row.get("as_of"), "refreshed_at": row.get("promoted_at"), "verified": bool(row), "skipped": True, "concurrent_update": True}
        if int(row.get("snapshot_id", -1)) != int(current["snapshot_id"]) or row.get("source_sha256") != snapshot["sha256"]:
            raise RuntimeError("unchanged snapshot heartbeat verification failed")
        return {"snapshot_id": row["snapshot_id"], "source_sha256": snapshot["sha256"], "as_of": row.get("as_of"), "refreshed_at": row.get("promoted_at"), "verified": True, "skipped": True, "concurrent_update": False}
    snapshot_id = call_rpc(base, key, credentials["current_ar_ingestion_key"], "smi_sales_stage_snapshot", {
        "p_source_sha256": snapshot["sha256"], "p_as_of": snapshot["as_of"],
        "p_refreshed_at": snapshot["refreshed_at"], "p_payload": snapshot,
    })
    call_rpc(base, key, credentials["current_ar_promotion_key"], "smi_sales_promote_snapshot", {"p_snapshot_id": snapshot_id})
    metadata = call_rpc(base, key, credentials["operator_verification_key"], "smi_sales_snapshot_metadata", {})
    row = metadata[0] if isinstance(metadata, list) and metadata else {}
    if int(row.get("snapshot_id", -1)) != int(snapshot_id) or row.get("source_sha256") != snapshot["sha256"]:
        raise RuntimeError("promoted snapshot verification failed")
    return {"snapshot_id": snapshot_id, "source_sha256": snapshot["sha256"], "as_of": row.get("as_of"), "refreshed_at": row.get("promoted_at"), "verified": True, "skipped": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=Path("data/sales.json"))
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--single-attempt", action="store_true", help="Disable automatic RPC retries for a controlled publication; do not blindly rerun after failure.")
    args = parser.parse_args()
    print(json.dumps(publish(args.snapshot, args.credentials, single_attempt=args.single_attempt), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
