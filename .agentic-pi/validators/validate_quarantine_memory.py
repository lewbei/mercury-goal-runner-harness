#!/usr/bin/env python3
"""Validate quarantine memory boundaries."""

from __future__ import annotations

import json
import sys
from pathlib import Path


QUARANTINE_FILES = {
    "learning_candidates.jsonl",
    "curator_delta_candidates.jsonl",
    "rejected_learning_candidates.jsonl",
    "pending_memory_promotions.jsonl",
}

FORBIDDEN_AUTHORITY_KEYS = {
    "status",
    "final_status",
    "policy_status",
    "certification_status",
    "policy_decision_status",
    "certified_done",
    "authority_status",
}


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                yield line_number, json.loads(line)
            except json.JSONDecodeError as exc:
                yield line_number, {"__json_error__": str(exc)}


def validate_entry(entry: dict, file_name: str, line_number: int) -> list[str]:
    errors = []
    loc = f"{file_name}:{line_number}"

    if "__json_error__" in entry:
        return [f"{loc}: invalid JSONL entry: {entry['__json_error__']}"]

    required = {
        "schema_version",
        "run_id",
        "source_run_id",
        "candidate_id",
        "created_at",
        "candidate_type",
        "principle",
        "memory_scope",
        "durable",
        "retrievable_by_future_runs",
        "authority_level",
        "final_status_authority",
        "can_certify_done",
    }
    missing = sorted(required - set(entry))
    for key in missing:
        errors.append(f"{loc}: missing required field {key}")

    for key in FORBIDDEN_AUTHORITY_KEYS:
        if key in entry:
            errors.append(f"{loc}: quarantine entry contains authority-like field {key}")

    if entry.get("schema_version") != "learning_candidate_v1":
        errors.append(f"{loc}: unexpected schema_version {entry.get('schema_version')!r}")
    if not str(entry.get("source_run_id", "")).strip():
        errors.append(f"{loc}: source_run_id is required")
    if entry.get("memory_scope") != "quarantine":
        errors.append(f"{loc}: memory_scope must be quarantine")
    if entry.get("durable") is not False:
        errors.append(f"{loc}: quarantine memory must not be durable")
    if entry.get("retrievable_by_future_runs") is not False:
        errors.append(f"{loc}: quarantine memory cannot be retrieved by future runs")
    if entry.get("authority_level") != "advisory_only":
        errors.append(f"{loc}: memory authority_level must be advisory_only")
    if entry.get("final_status_authority") != "certifier_only":
        errors.append(f"{loc}: final_status_authority must remain certifier_only")
    if entry.get("can_certify_done") is not False:
        errors.append(f"{loc}: quarantine memory cannot certify DONE")

    return errors


def validate_quarantine_memory(run_dir: Path) -> list[str]:
    run_dir = Path(run_dir)
    mem_dir = run_dir / "memory"
    errors = []
    if not mem_dir.is_dir():
        errors.append(f"memory directory missing: {mem_dir}")
        return errors

    for file_name in sorted(QUARANTINE_FILES):
        path = mem_dir / file_name
        if not path.is_file():
            errors.append(f"quarantine file missing: {file_name}")
            continue
        for line_number, entry in iter_jsonl(path):
            errors.extend(validate_entry(entry, file_name, line_number))

    return errors


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Usage: validate_quarantine_memory.py <run_dir>")
        return 2
    errors = validate_quarantine_memory(Path(argv[0]))
    if errors:
        print("QUARANTINE_MEMORY_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("QUARANTINE_MEMORY_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
