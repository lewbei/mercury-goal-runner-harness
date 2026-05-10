#!/usr/bin/env python3
"""Validate simple MemPalace card contradiction rules."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def validate_memory_contradictions(card: dict) -> list[str]:
    errors = []
    if not isinstance(card, dict):
        return ["memory card must be a JSON object"]

    helpful = card.get("helpful_count", 0)
    harmful = card.get("harmful_count", 0)
    if isinstance(helpful, int) and isinstance(harmful, int):
        if harmful > 0 and harmful >= helpful and card.get("card_status") == "durable":
            errors.append("harmful durable card must be deprecated or rejected before retrieval")

    content = (card.get("content") or "").lower()
    if "certify done" in content and "cannot certify" not in content and card.get("authority_level") == "advisory_only":
        errors.append("advisory memory content appears to claim certification authority")

    do_not_use_when = card.get("do_not_use_when", [])
    if do_not_use_when and not isinstance(do_not_use_when, list):
        errors.append("do_not_use_when must be a list")
    return errors


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Usage: validate_memory_contradictions.py <card.json>")
        return 2
    errors = validate_memory_contradictions(load_json(Path(argv[0])))
    if errors:
        print("MEMORY_CONTRADICTIONS_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("MEMORY_CONTRADICTIONS_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
