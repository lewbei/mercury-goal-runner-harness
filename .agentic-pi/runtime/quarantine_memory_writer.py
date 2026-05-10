#!/usr/bin/env python3
"""Write quarantine learning candidates for one run.

Quarantine memory is neither durable nor retrievable by future runs. It is a
holding area for later memory governance slices.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "learning_candidate_v1"

QUARANTINE_FILES = [
    "learning_candidates.jsonl",
    "curator_delta_candidates.jsonl",
    "rejected_learning_candidates.jsonl",
    "pending_memory_promotions.jsonl",
]


class QuarantineMemoryError(ValueError):
    """Raised when a quarantine candidate would cross the memory boundary."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def ensure_quarantine_files(memory_dir: Path) -> None:
    memory_dir.mkdir(parents=True, exist_ok=True)
    for name in QUARANTINE_FILES:
        (memory_dir / name).touch(exist_ok=True)


def parse_evidence_refs(raw_refs: str | None) -> list[str]:
    if not raw_refs:
        return []
    return [part.strip() for part in raw_refs.split(",") if part.strip()]


def build_learning_candidate(
    run_dir: Path,
    source_run_id: str,
    principle: str,
    *,
    candidate_type: str = "run_local_lesson",
    evidence_refs: list[str] | None = None,
) -> dict:
    if not source_run_id.strip():
        raise QuarantineMemoryError("source_run_id is required")
    if not principle.strip():
        raise QuarantineMemoryError("principle is required")

    created_at = utc_now()
    candidate_id = f"{run_dir.name}:candidate:{created_at}"
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "source_run_id": source_run_id,
        "candidate_id": candidate_id,
        "created_at": created_at,
        "candidate_type": candidate_type,
        "principle": principle,
        "evidence_refs": evidence_refs or [],
        "memory_scope": "quarantine",
        "durable": False,
        "retrievable_by_future_runs": False,
        "authority_level": "advisory_only",
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }


def write_quarantine_candidate(
    run_dir: Path,
    source_run_id: str,
    principle: str,
    *,
    candidate_type: str = "run_local_lesson",
    evidence_refs: list[str] | None = None,
) -> dict:
    run_dir = Path(run_dir)
    memory_dir = run_dir / "memory"
    ensure_quarantine_files(memory_dir)
    candidate = build_learning_candidate(
        run_dir,
        source_run_id,
        principle,
        candidate_type=candidate_type,
        evidence_refs=evidence_refs,
    )
    append_jsonl(memory_dir / "learning_candidates.jsonl", candidate)
    append_jsonl(memory_dir / "pending_memory_promotions.jsonl", candidate)
    return candidate


def retrieve_quarantine_candidates_for_future_run(*_args, **_kwargs) -> list[dict]:
    """Return no candidates by design.

    Future-run retrieval is reserved for durable memory after v3.7 governance.
    Quarantine candidates stay local to the source run.
    """

    return []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write non-durable quarantine memory.")
    parser.add_argument("run_dir")
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--principle", required=True)
    parser.add_argument("--candidate-type", default="run_local_lesson")
    parser.add_argument("--evidence-refs", default="")
    args = parser.parse_args(argv)
    try:
        candidate = write_quarantine_candidate(
            Path(args.run_dir),
            args.source_run_id,
            args.principle,
            candidate_type=args.candidate_type,
            evidence_refs=parse_evidence_refs(args.evidence_refs),
        )
    except QuarantineMemoryError as exc:
        print(f"QUARANTINE_MEMORY_REJECTED: {exc}")
        return 1
    except Exception as exc:
        print(f"QUARANTINE_MEMORY_ERROR: {exc}")
        return 1
    print(json.dumps(candidate, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
