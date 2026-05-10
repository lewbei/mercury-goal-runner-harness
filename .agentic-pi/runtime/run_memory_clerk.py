#!/usr/bin/env python3
"""Append run-local advisory memory for the active run.

Run-local memory is useful for repair and context tracking inside one run. It
is deliberately not evidence, not durable memory, and not final-status
authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "run_journal_entry_v1"

PROTECTED_AUTHORITY_FILES = {
    "final_status.json",
    "final_status.md",
    "certification.json",
    "policy_decision.json",
    "evidence_index.json",
    "evidence_freeze.json",
    "evidence_hash_manifest.json",
}

PHASE_TARGETS = {
    "planning": ("run_journal.jsonl", "phase_observations.jsonl"),
    "execution": ("run_journal.jsonl", "phase_observations.jsonl"),
    "verifier_failure": ("run_journal.jsonl", "failure_observations.jsonl"),
    "repair": ("run_journal.jsonl", "repair_notes.jsonl"),
    "context_update": ("run_journal.jsonl", "context_updates.jsonl"),
    "memory_usage": ("run_journal.jsonl", "memory_usage_log.jsonl"),
    "memory_effect": ("run_journal.jsonl", "memory_effect_log.jsonl"),
}

ALL_MEMORY_FILES = sorted({name for names in PHASE_TARGETS.values() for name in names})


class RunMemoryError(ValueError):
    """Raised when a memory append would cross an authority boundary."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_target(target_file: str | None) -> str:
    if target_file is None:
        return ""
    normalized = target_file.replace("\\", "/").strip("/")
    if normalized.split("/")[-1] in PROTECTED_AUTHORITY_FILES:
        raise RunMemoryError(f"run-local memory cannot target authority artifact: {target_file}")
    return normalized


def load_details(raw_details: str | None) -> dict:
    if not raw_details:
        return {}
    try:
        parsed = json.loads(raw_details)
    except json.JSONDecodeError as exc:
        raise RunMemoryError(f"details must be JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RunMemoryError("details must be JSON object")
    return parsed


def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def ensure_memory_files(memory_dir: Path) -> None:
    memory_dir.mkdir(parents=True, exist_ok=True)
    for name in ALL_MEMORY_FILES:
        (memory_dir / name).touch(exist_ok=True)


def build_entry(
    run_dir: Path,
    phase: str,
    message: str,
    *,
    target_file: str | None = None,
    details: dict | None = None,
) -> dict:
    if phase not in PHASE_TARGETS:
        raise RunMemoryError(f"unsupported run-local memory phase: {phase}")
    if not message.strip():
        raise RunMemoryError("message is required")

    normalized_target = normalize_target(target_file)
    created_at = utc_now()
    entry_id = f"{run_dir.name}:{phase}:{created_at}"
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "entry_id": entry_id,
        "created_at": created_at,
        "phase": phase,
        "event_type": f"{phase}_observation",
        "message": message,
        "target_file": normalized_target,
        "details": details or {},
        "memory_scope": "run_local",
        "durable": False,
        "excluded_from_evidence_index": True,
        "authority_level": "advisory_only",
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }


def append_run_memory(
    run_dir: Path,
    phase: str,
    message: str,
    *,
    target_file: str | None = None,
    details: dict | None = None,
) -> dict:
    run_dir = Path(run_dir)
    memory_dir = run_dir / "memory"
    ensure_memory_files(memory_dir)
    entry = build_entry(run_dir, phase, message, target_file=target_file, details=details)
    for file_name in PHASE_TARGETS[phase]:
        append_jsonl(memory_dir / file_name, entry)
    return entry


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Append run-local advisory memory.")
    parser.add_argument("run_dir")
    parser.add_argument("--phase", required=True, choices=sorted(PHASE_TARGETS))
    parser.add_argument("--message", required=True)
    parser.add_argument("--target-file", default="")
    parser.add_argument("--details", default="")
    args = parser.parse_args(argv)
    try:
        entry = append_run_memory(
            Path(args.run_dir),
            args.phase,
            args.message,
            target_file=args.target_file or None,
            details=load_details(args.details),
        )
    except RunMemoryError as exc:
        print(f"RUN_MEMORY_REJECTED: {exc}")
        return 1
    except Exception as exc:
        print(f"RUN_MEMORY_CLERK_ERROR: {exc}")
        return 1
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
