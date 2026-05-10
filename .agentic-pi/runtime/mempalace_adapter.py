#!/usr/bin/env python3
"""Structured advisory memory storage for MemPalace-style cards.

MemPalace stores curated memory. It does not certify DONE, replace evidence, or
override policy. Durable writes are intentionally separated from normal
adapter reads; promotion is owned by memory_write_gate.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "mempalace_ace_card_v1"
DEFAULT_MEMORY_ROOT = Path(__file__).resolve().parents[1] / "memory"

VALID_WINGS = {
    "planning",
    "verification",
    "git_provenance",
    "repair",
    "anti_overclaim",
}

DEFAULT_WING_ROOMS = {
    "planning": ["plan_seed_patterns", "branch_failure_patterns", "applicability_gate_rules"],
    "verification": ["false_done_cases", "weak_oracle_patterns", "replay_mismatch_patterns"],
    "git_provenance": ["dirty_tree_cases", "worktree_rules", "patch_replay_failures"],
    "repair": ["verifier_failure_repairs", "test_failure_repairs", "context_drift_repairs"],
    "anti_overclaim": ["artifact_exists_not_done", "agent_report_not_certification", "memory_not_evidence"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def safe_segment(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    normalized = value.strip().replace("\\", "/")
    if normalized in {".", ".."} or "/" in normalized:
        raise ValueError(f"{field} must be one path segment")
    return normalized


def ensure_durable_layout(memory_root: Path = DEFAULT_MEMORY_ROOT) -> None:
    memory_root = Path(memory_root)
    for wing, rooms in DEFAULT_WING_ROOMS.items():
        for room in rooms:
            (memory_root / "durable" / wing / room).mkdir(parents=True, exist_ok=True)
    (memory_root / "index").mkdir(parents=True, exist_ok=True)
    (memory_root / "verbatim" / "run_excerpts").mkdir(parents=True, exist_ok=True)


def normalize_card(card: dict) -> dict:
    normalized = dict(card)
    normalized.setdefault("schema_version", SCHEMA_VERSION)
    normalized.setdefault("type", "mistake_pattern")
    normalized.setdefault("source_phase", "UNKNOWN")
    normalized.setdefault("helpful_count", 0)
    normalized.setdefault("harmful_count", 0)
    normalized.setdefault("last_used_run", "")
    normalized.setdefault("card_status", "durable")
    normalized.setdefault("authority_level", "advisory_only")
    normalized.setdefault("can_certify_done", False)
    normalized.setdefault("do_not_use_when", [])
    normalized.setdefault("created_at", utc_now())
    return normalized


def card_storage_path(memory_root: Path, card: dict) -> Path:
    wing = safe_segment(card.get("wing", ""), "wing")
    room = safe_segment(card.get("room", ""), "room")
    drawer = safe_segment(card.get("drawer", "cards"), "drawer")
    if wing not in VALID_WINGS:
        raise ValueError(f"unsupported memory wing: {wing}")
    root = Path(memory_root).resolve()
    path = (root / "durable" / wing / room / f"{drawer}.jsonl").resolve()
    if root != path and root not in path.parents:
        raise ValueError("memory card path escapes memory root")
    return path


def load_durable_cards(memory_root: Path = DEFAULT_MEMORY_ROOT) -> list[dict]:
    memory_root = Path(memory_root)
    durable_root = memory_root / "durable"
    cards = []
    if not durable_root.is_dir():
        return cards
    for path in sorted(durable_root.glob("**/*.jsonl")):
        cards.extend(load_jsonl(path))
    return cards


def write_durable_card(memory_root: Path, card: dict) -> Path:
    normalized = normalize_card(card)
    path = card_storage_path(memory_root, normalized)
    append_jsonl(path, normalized)
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inspect or initialize MemPalace durable memory.")
    parser.add_argument("--memory-root", default=str(DEFAULT_MEMORY_ROOT))
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--list-cards", action="store_true")
    args = parser.parse_args(argv)
    memory_root = Path(args.memory_root)
    if args.init:
        ensure_durable_layout(memory_root)
        print(f"MEMORY_LAYOUT_READY {memory_root}")
    if args.list_cards:
        print(json.dumps(load_durable_cards(memory_root), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
