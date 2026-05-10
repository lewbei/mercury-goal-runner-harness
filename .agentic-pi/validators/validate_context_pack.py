#!/usr/bin/env python3
"""Validate advisory context packs built from durable memory."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / ".agentic-pi" / "schemas" / "context_pack.schema.json"
SCHEMA_VALIDATOR_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
REQUIRED_FORBIDDEN_USES = {
    "memory_as_evidence",
    "memory_as_certification",
    "memory_as_policy_override",
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema", SCHEMA_VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def estimate_tokens(text: str) -> int:
    return max(1, (len(text or "") + 3) // 4)


def validate_context_pack(pack: dict) -> list[str]:
    validator = load_schema_validator()
    errors = validator.validate(pack, load_json(SCHEMA_PATH))
    if not isinstance(pack, dict):
        return errors

    if pack.get("final_status_authority") != "certifier_only":
        errors.append("context pack final_status_authority must be certifier_only")
    if pack.get("can_certify_done") is not False:
        errors.append("context pack cannot certify DONE")

    forbidden_uses = set(pack.get("forbidden_uses", []))
    missing = sorted(REQUIRED_FORBIDDEN_USES - forbidden_uses)
    for item in missing:
        errors.append(f"context pack missing forbidden use: {item}")

    limits = pack.get("limits", {})
    cards = pack.get("cards", [])
    if isinstance(limits, dict) and isinstance(cards, list):
        max_cards = limits.get("max_cards")
        max_tokens = limits.get("max_tokens")
        if isinstance(max_cards, int) and len(cards) > max_cards:
            errors.append("context pack exceeds max_cards")
        if isinstance(max_tokens, int):
            total = sum(estimate_tokens(card.get("content", "")) for card in cards if isinstance(card, dict))
            if total > max_tokens:
                errors.append("context pack exceeds max_tokens")

    for idx, card in enumerate(cards if isinstance(cards, list) else []):
        loc = f"cards[{idx}]"
        if card.get("authority_level") != "advisory_only":
            errors.append(f"{loc}: authority_level must be advisory_only")
        if card.get("can_certify_done") is not False:
            errors.append(f"{loc}: memory card cannot certify DONE")
        if not card.get("evidence_refs"):
            errors.append(f"{loc}: evidence_refs required")

    return sorted(set(errors))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Usage: validate_context_pack.py <context_pack.json>")
        return 2
    errors = validate_context_pack(load_json(Path(argv[0])))
    if errors:
        print("CONTEXT_PACK_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("CONTEXT_PACK_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
