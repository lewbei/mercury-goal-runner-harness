#!/usr/bin/env python3
"""Validate evidence_index.json.

This validator checks structural shape and cross-file authority rules that JSON
Schema alone cannot express in this repo's lightweight schema validator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED_TOP_LEVEL = {"schema_version", "run_id", "frozen", "freeze_id", "generated_at", "items"}
REQUIRED_ITEM_FIELDS = {
    "evidence_id",
    "kind",
    "path",
    "sha256",
    "producer",
    "producer_command_id",
    "trust_level",
    "created_before_freeze",
}
ALLOWED_KINDS = {
    "TRACE",
    "STEP_LOG",
    "ARTIFACT",
    "VERIFIER_ARTIFACT",
    "VERIFIER_SMELL_REPORT",
    "VERIFIER_STRENGTH_REPORT",
    "POLICY_DECISION",
    "CERTIFICATION",
    "FINAL_STATUS",
}


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
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("path must be a non-empty string")
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute path is not allowed: {raw_path}")
    root = run_dir.resolve()
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {raw_path}")
    return resolved


def is_memory_path(raw_path: str) -> bool:
    normalized = raw_path.replace("\\", "/")
    return normalized == "memory" or normalized.startswith("memory/") or "/memory/" in normalized


def policy_references(policy: dict) -> set[str]:
    refs = set()
    for key in ("certifying_artifacts", "provisional_artifacts"):
        for value in policy.get(key, []):
            if isinstance(value, str) and value.strip():
                refs.add(value.strip())
    return refs


def validate_evidence_index(run_dir: Path) -> tuple[bool, str]:
    run_dir = Path(run_dir)
    path = run_dir / "evidence_index.json"
    if not path.is_file():
        return False, "evidence_index.json missing"

    try:
        index = load_json(path)
    except Exception as exc:
        return False, f"evidence_index.json parse failed: {exc}"

    missing = sorted(REQUIRED_TOP_LEVEL - set(index))
    if missing:
        return False, f"evidence_index.json missing required fields: {missing}"
    if index.get("schema_version") != "evidence_index_v1":
        return False, "evidence_index.json schema_version must be evidence_index_v1"
    if index.get("run_id") != run_dir.name:
        return False, "evidence_index.json run_id does not match run folder"
    if index.get("frozen") is not True:
        return False, "evidence_index.json must be marked frozen"
    if not isinstance(index.get("items"), list) or not index["items"]:
        return False, "evidence_index.json items must be a non-empty list"

    seen_ids = set()
    seen_paths = set()
    kinds = set()
    verifier_artifact_ids = set()

    for item in index["items"]:
        if not isinstance(item, dict):
            return False, "evidence item must be an object"
        missing_item_fields = sorted(REQUIRED_ITEM_FIELDS - set(item))
        if missing_item_fields:
            return False, f"evidence item missing required fields: {missing_item_fields}"

        evidence_id = item["evidence_id"]
        if evidence_id in seen_ids:
            return False, f"duplicate evidence_id: {evidence_id}"
        seen_ids.add(evidence_id)

        kind = item["kind"]
        if kind not in ALLOWED_KINDS:
            return False, f"unsupported evidence kind: {kind}"
        kinds.add(kind)

        producer = item.get("producer")
        if not isinstance(producer, str) or not producer.strip():
            return False, f"missing producer for evidence {evidence_id}"
        if not isinstance(item.get("producer_command_id"), str) or not item["producer_command_id"].strip():
            return False, f"missing producer_command_id for evidence {evidence_id}"
        if item.get("created_before_freeze") is not True:
            return False, f"evidence {evidence_id} was not created before freeze"

        raw_path = item["path"]
        if is_memory_path(raw_path):
            return False, f"memory file cannot enter evidence_index.json: {raw_path}"
        try:
            evidence_path = safe_run_path(run_dir, raw_path)
        except ValueError as exc:
            return False, str(exc)
        if raw_path in seen_paths:
            return False, f"duplicate evidence path: {raw_path}"
        seen_paths.add(raw_path)
        if not evidence_path.is_file():
            return False, f"indexed evidence file missing: {raw_path}"
        if sha256_file(evidence_path) != item["sha256"]:
            return False, f"sha256 mismatch for evidence {evidence_id}"

        if kind == "VERIFIER_ARTIFACT":
            artifact = load_json(evidence_path)
            artifact_id = artifact.get("artifact_id")
            if isinstance(artifact_id, str) and artifact_id.strip():
                verifier_artifact_ids.add(artifact_id)
                indexed_artifact_id = item.get("artifact_id")
                if indexed_artifact_id and indexed_artifact_id != artifact_id:
                    return False, f"artifact_id mismatch for evidence {evidence_id}"

    required_kinds = {"TRACE", "STEP_LOG", "POLICY_DECISION"}
    missing_kinds = sorted(required_kinds - kinds)
    if missing_kinds:
        return False, f"evidence_index.json missing required evidence kinds: {missing_kinds}"

    policy_path = run_dir / "policy_decision.json"
    if policy_path.is_file():
        policy = load_json(policy_path)
        refs = policy_references(policy)
        missing_refs = sorted(ref for ref in refs if ref not in verifier_artifact_ids)
        if missing_refs:
            return False, f"policy_decision.json cites verifier artifacts not in frozen evidence: {missing_refs}"

    return True, "OK"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate evidence_index.json for a run.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    ok, message = validate_evidence_index(Path(args.run_dir))
    print("EVIDENCE_INDEX_VALID" if ok else "EVIDENCE_INDEX_INVALID")
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
