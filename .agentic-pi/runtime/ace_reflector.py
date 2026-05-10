#!/usr/bin/env python3
"""ACE reflector for run-memory effects.

The reflector classifies used memory as helpful, harmful, or neutral. It never
writes durable memory and never certifies DONE.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_reflection_report(
    run_id: str,
    used_cards: list[dict],
    *,
    helpful_card_ids: list[str] | None = None,
    harmful_card_ids: list[str] | None = None,
    outcome_status: str = "",
) -> dict:
    helpful_set = set(helpful_card_ids or [])
    harmful_set = set(harmful_card_ids or [])
    if not helpful_set and not harmful_set:
        if outcome_status in {"CERTIFIED_DONE", "DONE_PASS"}:
            helpful_set = {card.get("card_id", "") for card in used_cards}
        elif outcome_status in {"NOT_DONE", "DONE_FAIL"}:
            harmful_set = {card.get("card_id", "") for card in used_cards}

    helpful = []
    harmful = []
    neutral = []
    for card in used_cards:
        card_id = card.get("card_id", "")
        item = {"card_id": card_id, "reason": f"outcome={outcome_status}" if outcome_status else "explicit reflection"}
        if card_id in helpful_set:
            helpful.append(item)
        elif card_id in harmful_set:
            harmful.append(item)
        else:
            neutral.append(item)

    return {
        "schema_version": "reflection_report_v1",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "outcome_status": outcome_status,
        "helpful_cards": helpful,
        "harmful_cards": harmful,
        "neutral_cards": neutral,
        "can_write_durable_memory": False,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write an ACE reflection report.")
    parser.add_argument("run_id")
    parser.add_argument("--context-pack", required=True)
    parser.add_argument("--outcome-status", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    context_pack = json.loads(Path(args.context_pack).read_text(encoding="utf-8"))
    report = build_reflection_report(args.run_id, context_pack.get("cards", []), outcome_status=args.outcome_status)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
