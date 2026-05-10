#!/usr/bin/env python3
"""Build a frozen-evidence index for a run folder.

The evidence index is a provenance map. It is not a certifier and it never
decides DONE. It records the files that deterministic policy/certification may
cite, with stable hashes and producer identities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "evidence_index_v1"
DEFAULT_FREEZE_ID = "freeze_0001"

EVIDENCE_SPECS = [
    ("TRACE", "trace.jsonl", "guarded_worker", "cmd_trace", "L2_EXECUTION_EVIDENCE"),
    ("STEP_LOG", "step_logs/*.json", "guarded_worker", "cmd_step_log", "L2_EXECUTION_EVIDENCE"),
    ("ARTIFACT", "artifacts/**/*", "guarded_worker", "cmd_artifact", "L2_EXECUTION_EVIDENCE"),
    (
        "VERIFIER_ARTIFACT",
        "verifier_artifacts/*.json",
        "verifier_provenance",
        "cmd_verifier_artifact",
        "L3_VERIFIER_EVIDENCE",
    ),
    (
        "VERIFIER_SMELL_REPORT",
        "verifier_smell_reports/*.json",
        "smell_scanner",
        "cmd_smell_scan",
        "L3_VERIFIER_QUALITY",
    ),
    (
        "VERIFIER_STRENGTH_REPORT",
        "verifier_strength_reports/*.json",
        "strength_scorer",
        "cmd_strength_score",
        "L3_VERIFIER_QUALITY",
    ),
    (
        "POLICY_DECISION",
        "policy_decision.json",
        "policy_engine",
        "cmd_policy_decision",
        "L4_AUTHORITY",
    ),
    (
        "CERTIFICATION",
        "certification.json",
        "certify_run",
        "cmd_certification",
        "L4_AUTHORITY",
    ),
    (
        "FINAL_STATUS",
        "final_status.json",
        "certify_run",
        "cmd_final_status",
        "L4_AUTHORITY",
    ),
]


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


def run_relative(run_dir: Path, path: Path) -> str:
    run_root = run_dir.resolve()
    resolved = path.resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {path}")
    return resolved.relative_to(run_root).as_posix()


def is_memory_path(relative_path: str) -> bool:
    return Path(relative_path).parts[:1] == ("memory",) or "/memory/" in relative_path


def stable_evidence_id(kind: str, relative_path: str) -> str:
    token = relative_path.replace("\\", "/").replace("/", "_").replace(".", "_")
    token = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in token)
    return f"ev_{kind.lower()}_{token}"


def policy_referenced_verifier_ids(run_dir: Path) -> set[str]:
    policy_path = run_dir / "policy_decision.json"
    if not policy_path.is_file():
        return set()
    policy = load_json(policy_path)
    referenced = set()
    for key in ("certifying_artifacts", "provisional_artifacts"):
        for value in policy.get(key, []):
            if isinstance(value, str) and value.strip():
                referenced.add(value.strip())
    return referenced


def verifier_artifact_id(path: Path) -> str:
    try:
        artifact = load_json(path)
    except Exception:
        return ""
    value = artifact.get("artifact_id")
    return value if isinstance(value, str) else ""


def collect_items(run_dir: Path) -> list[dict]:
    items = []
    referenced_verifiers = policy_referenced_verifier_ids(run_dir)

    for kind, pattern, producer, producer_command_id, trust_level in EVIDENCE_SPECS:
        for path in sorted(run_dir.glob(pattern)):
            if not path.is_file():
                continue
            relative_path = run_relative(run_dir, path)
            if is_memory_path(relative_path):
                continue

            item = {
                "evidence_id": stable_evidence_id(kind, relative_path),
                "kind": kind,
                "path": relative_path,
                "sha256": sha256_file(path),
                "producer": producer,
                "producer_command_id": producer_command_id,
                "trust_level": trust_level,
                "created_before_freeze": True,
            }

            if kind == "VERIFIER_ARTIFACT":
                artifact_id = verifier_artifact_id(path)
                if artifact_id:
                    item["artifact_id"] = artifact_id
                    item["cited_by_policy"] = artifact_id in referenced_verifiers

            items.append(item)

    return items


def build_evidence_index(run_dir: Path, freeze_id: str = DEFAULT_FREEZE_ID) -> dict:
    run_dir = Path(run_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "frozen": True,
        "freeze_id": freeze_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": collect_items(run_dir),
    }


def write_evidence_index(run_dir: Path, freeze_id: str = DEFAULT_FREEZE_ID) -> Path:
    run_dir = Path(run_dir)
    index = build_evidence_index(run_dir, freeze_id=freeze_id)
    path = run_dir / "evidence_index.json"
    write_json(path, index)
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write evidence_index.json for a run.")
    parser.add_argument("run_dir")
    parser.add_argument("--freeze-id", default=DEFAULT_FREEZE_ID)
    args = parser.parse_args(argv)
    path = write_evidence_index(Path(args.run_dir), freeze_id=args.freeze_id)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
