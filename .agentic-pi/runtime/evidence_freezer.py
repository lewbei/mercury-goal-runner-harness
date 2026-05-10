#!/usr/bin/env python3
"""Freeze indexed evidence and write a hash manifest.

The freezer records a stable boundary after policy_decision.json exists. It can
block later certification through validation, but it cannot certify DONE.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "evidence_freeze_v1"
HASH_MANIFEST_SCHEMA_VERSION = "evidence_hash_manifest_v1"


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_indexer():
    path = Path(__file__).with_name("evidence_indexer.py")
    spec = importlib.util.spec_from_file_location("evidence_indexer", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["evidence_indexer"] = module
    spec.loader.exec_module(module)
    return module


def ensure_index(run_dir: Path, freeze_id: str) -> Path:
    indexer = load_indexer()
    return indexer.write_evidence_index(run_dir, freeze_id=freeze_id)


def freeze_evidence(run_dir: Path, freeze_id: str = "freeze_0001") -> tuple[Path, Path]:
    run_dir = Path(run_dir)
    if not (run_dir / "policy_decision.json").is_file():
        raise RuntimeError("policy_decision.json is required before evidence freeze")

    index_path = ensure_index(run_dir, freeze_id)
    index = load_json(index_path)
    if index.get("schema_version") != "evidence_index_v1":
        raise RuntimeError("evidence_index.json has unsupported schema_version")
    if index.get("run_id") != run_dir.name:
        raise RuntimeError("evidence_index.json run_id does not match run folder")

    item_manifest = []
    for item in index.get("items", []):
        evidence_path = run_dir / item["path"]
        if not evidence_path.is_file():
            raise RuntimeError(f"indexed evidence file is missing: {item['path']}")
        item_manifest.append(
            {
                "evidence_id": item["evidence_id"],
                "kind": item["kind"],
                "path": item["path"],
                "sha256": sha256_file(evidence_path),
                "producer": item["producer"],
            }
        )

    freeze = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "freeze_id": index["freeze_id"],
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "evidence_index_path": "evidence_index.json",
        "evidence_index_sha256": sha256_file(index_path),
        "policy_decision_path": "policy_decision.json",
        "policy_decision_sha256": sha256_file(run_dir / "policy_decision.json"),
        "hash_manifest_path": "evidence_hash_manifest.json",
        "item_count": len(item_manifest),
    }
    hash_manifest = {
        "schema_version": HASH_MANIFEST_SCHEMA_VERSION,
        "run_id": run_dir.name,
        "freeze_id": index["freeze_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": item_manifest,
    }

    freeze_path = run_dir / "evidence_freeze.json"
    manifest_path = run_dir / "evidence_hash_manifest.json"
    write_json(freeze_path, freeze)
    write_json(manifest_path, hash_manifest)
    return freeze_path, manifest_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write evidence freeze files for a run.")
    parser.add_argument("run_dir")
    parser.add_argument("--freeze-id", default="freeze_0001")
    args = parser.parse_args(argv)
    freeze_path, manifest_path = freeze_evidence(Path(args.run_dir), freeze_id=args.freeze_id)
    print(f"Wrote {freeze_path}")
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
