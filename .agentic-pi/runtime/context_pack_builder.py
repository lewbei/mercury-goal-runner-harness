#!/usr/bin/env python3
"""Build bounded context packs from durable advisory memory cards."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import importlib.util


ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = ROOT / ".agentic-pi" / "runtime" / "mempalace_adapter.py"


def load_adapter_module():
    spec = importlib.util.spec_from_file_location("mempalace_adapter", ADAPTER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def estimate_tokens(text: str) -> int:
    return max(1, (len(text or "") + 3) // 4)


def card_is_selectable(card: dict) -> bool:
    if card.get("card_status") in {"deprecated", "rejected"}:
        return False
    if card.get("authority_level") != "advisory_only":
        return False
    if card.get("can_certify_done") is not False:
        return False
    harmful = int(card.get("harmful_count", 0) or 0)
    helpful = int(card.get("helpful_count", 0) or 0)
    if harmful > 0 and harmful >= helpful:
        return False
    if not card.get("evidence_refs"):
        return False
    return True


def build_context_pack(
    run_id: str,
    phase: str,
    target: str,
    cards: list[dict],
    *,
    max_cards: int = 5,
    max_tokens: int = 800,
) -> dict:
    selected = []
    token_budget = max_tokens
    for card in sorted(cards, key=lambda row: (-int(row.get("helpful_count", 0) or 0), row.get("card_id", ""))):
        if not card_is_selectable(card):
            continue
        content = card.get("content", "")
        cost = estimate_tokens(content)
        if len(selected) >= max_cards or cost > token_budget:
            continue
        selected.append(
            {
                "card_id": card["card_id"],
                "wing": card.get("wing", ""),
                "room": card.get("room", ""),
                "reason_selected": f"matches {target}",
                "content": content,
                "evidence_refs": list(card.get("evidence_refs", [])),
                "authority_level": "advisory_only",
                "can_certify_done": False,
            }
        )
        token_budget -= cost
    return {
        "schema_version": "context_pack_v1",
        "run_id": run_id,
        "phase": phase,
        "target": target,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cards": selected,
        "limits": {"max_cards": max_cards, "max_tokens": max_tokens},
        "forbidden_uses": [
            "memory_as_evidence",
            "memory_as_certification",
            "memory_as_policy_override",
        ],
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build a bounded advisory context pack.")
    parser.add_argument("run_id")
    parser.add_argument("--phase", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--memory-root", default=str(ROOT / ".agentic-pi" / "memory"))
    parser.add_argument("--max-cards", type=int, default=5)
    parser.add_argument("--max-tokens", type=int, default=800)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    adapter = load_adapter_module()
    cards = adapter.load_durable_cards(Path(args.memory_root))
    pack = build_context_pack(
        args.run_id,
        args.phase,
        args.target,
        cards,
        max_cards=args.max_cards,
        max_tokens=args.max_tokens,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
