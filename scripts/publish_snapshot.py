"""Stage, promote, and verify an SMI Sales snapshot in Supabase."""
from __future__ import annotations

import argparse
import json
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


def rpc(base: str, publishable: str, token: str, name: str, payload: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        f"{base}/rest/v1/rpc/{name}",
        data=json.dumps(payload, separators=(",", ":")).encode(),
        method="POST",
        headers={"apikey": publishable, "Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{name} failed: HTTP {exc.code} {detail[:500]}") from None


def publish(snapshot_path: Path, credential_path: Path) -> dict[str, Any]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    credentials = load_credentials(credential_path)
    base, key = credentials["supabase_url"], credentials["publishable_key"]
    snapshot_id = rpc(base, key, credentials["current_ar_ingestion_key"], "smi_sales_stage_snapshot", {
        "p_source_sha256": snapshot["sha256"], "p_as_of": snapshot["as_of"],
        "p_refreshed_at": snapshot["refreshed_at"], "p_payload": snapshot,
    })
    rpc(base, key, credentials["current_ar_promotion_key"], "smi_sales_promote_snapshot", {"p_snapshot_id": snapshot_id})
    metadata = rpc(base, key, credentials["operator_verification_key"], "smi_sales_snapshot_metadata", {})
    row = metadata[0] if isinstance(metadata, list) and metadata else {}
    if int(row.get("snapshot_id", -1)) != int(snapshot_id) or row.get("source_sha256") != snapshot["sha256"]:
        raise RuntimeError("promoted snapshot verification failed")
    return {"snapshot_id": snapshot_id, "source_sha256": snapshot["sha256"], "as_of": row.get("as_of"), "verified": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=Path("data/sales.json"))
    parser.add_argument("--credentials", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.snapshot, args.credentials), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
