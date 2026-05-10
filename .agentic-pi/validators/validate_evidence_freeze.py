#!/usr/bin/env python3
"""Validate frozen evidence and detect post-freeze mutation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


REQUIRED_FREEZE_FIELDS = {
    "schema_version",
    "run_id",
    "freeze_id",
    "frozen_at",
    "evidence_index_path",
    "evidence_index_sha256",
    "policy_decision_path",
    "policy_decision_sha256",
    "hash_manifest_path",
    "item_count",
}
REQUIRED_MANIFEST_FIELDS = {"schema_version", "run_id", "freeze_id", "generated_at", "items"}
REQUIRED_MANIFEST_ITEM_FIELDS = {"evidence_id", "kind", "path", "sha256", "producer"}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_run_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute path is not allowed: {raw_path}")
    root = run_dir.resolve()
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {raw_path}")
    return resolved


def load_index_validator():
    path = Path(__file__).with_name("validate_evidence_index.py")
    spec = importlib.util.spec_from_file_location("validate_evidence_index", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_evidence_index"] = module
    spec.loader.exec_module(module)
    return module.validate_evidence_index


def validate_evidence_freeze(run_dir: Path) -> tuple[bool, str]:
    run_dir = Path(run_dir)
    freeze_path = run_dir / "evidence_freeze.json"
    manifest_path = run_dir / "evidence_hash_manifest.json"
    policy_path = run_dir / "policy_decision.json"

    if not policy_path.is_file():
        return False, "policy_decision.json is required before evidence freeze"
    if not freeze_path.is_file():
        return False, "evidence_freeze.json missing"
    if not manifest_path.is_file():
        return False, "evidence_hash_manifest.json missing"

    try:
        freeze = load_json(freeze_path)
        manifest = load_json(manifest_path)
    except Exception as exc:
        return False, f"evidence freeze parse failed: {exc}"

    missing_freeze = sorted(REQUIRED_FREEZE_FIELDS - set(freeze))
    if missing_freeze:
        return False, f"evidence_freeze.json missing required fields: {missing_freeze}"
    missing_manifest = sorted(REQUIRED_MANIFEST_FIELDS - set(manifest))
    if missing_manifest:
        return False, f"evidence_hash_manifest.json missing required fields: {missing_manifest}"

    if freeze.get("schema_version") != "evidence_freeze_v1":
        return False, "evidence_freeze.json schema_version must be evidence_freeze_v1"
    if manifest.get("schema_version") != "evidence_hash_manifest_v1":
        return False, "evidence_hash_manifest.json schema_version must be evidence_hash_manifest_v1"
    if freeze.get("run_id") != run_dir.name or manifest.get("run_id") != run_dir.name:
        return False, "evidence freeze run_id does not match run folder"
    if freeze.get("freeze_id") != manifest.get("freeze_id"):
        return False, "freeze_id mismatch between freeze and manifest"
    if freeze.get("policy_decision_path") != "policy_decision.json":
        return False, "evidence_freeze.json must cite policy_decision.json"
    if sha256_file(policy_path) != freeze.get("policy_decision_sha256"):
        return False, "policy_decision.json hash mismatch after freeze"

    index_path = safe_run_path(run_dir, freeze["evidence_index_path"])
    if not index_path.is_file():
        return False, "frozen evidence_index.json missing"
    if sha256_file(index_path) != freeze.get("evidence_index_sha256"):
        return False, "evidence_index.json hash mismatch after freeze"

    validate_evidence_index = load_index_validator()
    ok, message = validate_evidence_index(run_dir)
    if not ok:
        return False, message

    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        return False, "evidence_hash_manifest.json items must be a non-empty list"
    if freeze.get("item_count") != len(items):
        return False, "evidence_freeze.json item_count does not match manifest"

    seen = set()
    for item in items:
        if not isinstance(item, dict):
            return False, "evidence_hash_manifest item must be an object"
        missing_item = sorted(REQUIRED_MANIFEST_ITEM_FIELDS - set(item))
        if missing_item:
            return False, f"evidence_hash_manifest item missing required fields: {missing_item}"
        evidence_id = item["evidence_id"]
        if evidence_id in seen:
            return False, f"duplicate manifest evidence_id: {evidence_id}"
        seen.add(evidence_id)
        if not isinstance(item.get("producer"), str) or not item["producer"].strip():
            return False, f"missing producer in hash manifest for {evidence_id}"
        evidence_path = safe_run_path(run_dir, item["path"])
        if not evidence_path.is_file():
            return False, f"frozen evidence file missing: {item['path']}"
        if sha256_file(evidence_path) != item["sha256"]:
            return False, f"hash mismatch for frozen evidence {evidence_id}"

    return True, "OK"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate evidence freeze files for a run.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    ok, message = validate_evidence_freeze(Path(args.run_dir))
    print("EVIDENCE_FREEZE_VALID" if ok else "EVIDENCE_FREEZE_INVALID")
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
