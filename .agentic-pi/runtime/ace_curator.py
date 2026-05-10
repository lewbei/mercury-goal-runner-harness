#!/usr/bin/env python3
"""ACE curator delta proposal writer.

The curator can propose memory card deltas. It cannot write durable memory.
Only memory_write_gate.py can promote a card.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_curator_delta(run_id: str, source_run_id: str, card: dict, *, action: str = "create", reason: str = "") -> dict:
    if action not in {"create", "update", "deprecate", "reject"}:
        raise ValueError(f"unsupported curator action: {action}")
    if not source_run_id:
        raise ValueError("source_run_id is required")
    return {
        "schema_version": "curator_delta_v1",
        "run_id": run_id,
        "source_run_id": source_run_id,
        "delta_id": f"{run_id}:{card.get('card_id', 'card')}:{datetime.now(timezone.utc).isoformat()}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "card": dict(card),
        "reason": reason or "ACE curator proposal",
        "can_write_durable_memory": False,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }


def write_delta_candidate(path: Path, delta: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(delta, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write an ACE curator delta candidate.")
    parser.add_argument("run_id")
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--card", required=True)
    parser.add_argument("--action", default="create")
    parser.add_argument("--reason", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    card = json.loads(Path(args.card).read_text(encoding="utf-8"))
    delta = build_curator_delta(args.run_id, args.source_run_id, card, action=args.action, reason=args.reason)
    write_delta_candidate(Path(args.output), delta)
    print(json.dumps(delta, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
