#!/usr/bin/env python3
"""Validate run-local memory boundaries."""

from __future__ import annotations

import json
import sys
from pathlib import Path


AUTHORITY_FILES = {
    "final_status.json",
    "final_status.md",
    "certification.json",
    "policy_decision.json",
    "evidence_index.json",
    "evidence_freeze.json",
    "evidence_hash_manifest.json",
}

RUN_LOCAL_FILES = {
    "run_journal.jsonl",
    "phase_observations.jsonl",
    "failure_observations.jsonl",
    "repair_notes.jsonl",
    "context_updates.jsonl",
    "memory_usage_log.jsonl",
    "memory_effect_log.jsonl",
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


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


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


def path_is_memory(path_value: str) -> bool:
    normalized = path_value.replace("\\", "/").strip("/")
    return normalized == "memory" or normalized.startswith("memory/") or "/memory/" in normalized


def validate_entry(entry: dict, file_name: str, line_number: int) -> list[str]:
    errors = []
    loc = f"{file_name}:{line_number}"

    if "__json_error__" in entry:
        return [f"{loc}: invalid JSONL entry: {entry['__json_error__']}"]

    required = {
        "schema_version",
        "run_id",
        "entry_id",
        "created_at",
        "phase",
        "event_type",
        "message",
        "memory_scope",
        "durable",
        "excluded_from_evidence_index",
        "authority_level",
        "final_status_authority",
        "can_certify_done",
    }
    missing = sorted(required - set(entry))
    for key in missing:
        errors.append(f"{loc}: missing required field {key}")

    for key in FORBIDDEN_AUTHORITY_KEYS:
        if key in entry:
            errors.append(f"{loc}: memory entry contains authority-like field {key}")

    if entry.get("schema_version") != "run_journal_entry_v1":
        errors.append(f"{loc}: unexpected schema_version {entry.get('schema_version')!r}")
    if entry.get("memory_scope") != "run_local":
        errors.append(f"{loc}: memory_scope must be run_local")
    if entry.get("durable") is not False:
        errors.append(f"{loc}: run-local memory must not be durable")
    if entry.get("excluded_from_evidence_index") is not True:
        errors.append(f"{loc}: run-local memory must be excluded from evidence_index.json")
    if entry.get("authority_level") != "advisory_only":
        errors.append(f"{loc}: memory authority_level must be advisory_only")
    if entry.get("final_status_authority") != "certifier_only":
        errors.append(f"{loc}: final_status_authority must remain certifier_only")
    if entry.get("can_certify_done") is not False:
        errors.append(f"{loc}: memory cannot certify DONE")

    target = entry.get("target_file", "")
    if isinstance(target, str) and target.replace("\\", "/").split("/")[-1] in AUTHORITY_FILES:
        errors.append(f"{loc}: memory targets protected authority artifact {target}")

    return errors


def validate_run_local_memory(run_dir: Path) -> list[str]:
    run_dir = Path(run_dir)
    mem_dir = run_dir / "memory"
    errors = []
    if not mem_dir.is_dir():
        errors.append(f"memory directory missing: {mem_dir}")
        return errors

    for auth in sorted(AUTHORITY_FILES):
        if (mem_dir / auth).exists():
            errors.append(f"authority artifact {auth} found in memory directory")

    for file_name in sorted(RUN_LOCAL_FILES):
        path = mem_dir / file_name
        if not path.is_file():
            errors.append(f"run-local memory file missing: {file_name}")
            continue
        for line_number, entry in iter_jsonl(path):
            errors.extend(validate_entry(entry, file_name, line_number))

    evidence_index = run_dir / "evidence_index.json"
    if evidence_index.is_file():
        try:
            index = load_json(evidence_index)
        except Exception as exc:
            errors.append(f"cannot read evidence_index.json: {exc}")
        else:
            for item in index.get("items", []):
                path_value = item.get("path", "")
                if isinstance(path_value, str) and path_is_memory(path_value):
                    errors.append(f"memory file {path_value} listed in evidence_index.json")

    return errors


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Usage: validate_run_local_memory.py <run_dir>")
        return 2
    errors = validate_run_local_memory(Path(argv[0]))
    if errors:
        print("RUN_LOCAL_MEMORY_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("RUN_LOCAL_MEMORY_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
