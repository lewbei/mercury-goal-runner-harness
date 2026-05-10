#!/usr/bin/env python3
"""Validate durable MemPalace/ACE memory cards.

Memory cards are advisory. They can guide planning and repair, but they cannot
certify DONE, override policy, or replace frozen evidence.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / ".agentic-pi" / "schemas" / "mempalace_card.schema.json"
SCHEMA_VALIDATOR_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"

VALID_WINGS = {"planning", "verification", "git_provenance", "repair", "anti_overclaim"}
VALID_CARD_STATUS = {"durable", "candidate", "deprecated", "rejected"}
AUTHORITY_LEAK_FIELDS = {
    "final_status",
    "final_status_json",
    "policy_status",
    "policy_decision_status",
    "certification_status",
    "certified_done",
    "done_status",
    "policy_override",
    "can_override_policy",
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema", SCHEMA_VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_one_safe_segment(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.strip().replace("\\", "/")
    return normalized not in {".", ".."} and "/" not in normalized


def validate_memory_card(card: dict) -> list[str]:
    errors = []
    validator = load_schema_validator()
    errors.extend(validator.validate(card, load_json(SCHEMA_PATH)))

    if not isinstance(card, dict):
        return errors

    for key in sorted(AUTHORITY_LEAK_FIELDS):
        if key in card:
            errors.append(f"memory card contains authority-leak field: {key}")

    if card.get("schema_version") != "mempalace_ace_card_v1":
        errors.append("schema_version must be mempalace_ace_card_v1")
    if card.get("wing") not in VALID_WINGS:
        errors.append(f"unsupported wing: {card.get('wing')!r}")
    for field in ["wing", "room", "drawer"]:
        if not is_one_safe_segment(card.get(field)):
            errors.append(f"{field} must be a single safe path segment")

    evidence_refs = card.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append("memory card requires at least one evidence_ref")
    elif any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs):
        errors.append("memory card evidence_refs must be non-empty strings")

    if card.get("authority_level") != "advisory_only":
        errors.append("memory card authority_level must be advisory_only")
    if card.get("can_certify_done") is not False:
        errors.append("memory card cannot certify DONE")
    if card.get("card_status") not in VALID_CARD_STATUS:
        errors.append(f"unsupported card_status: {card.get('card_status')!r}")

    helpful = card.get("helpful_count")
    harmful = card.get("harmful_count")
    if not isinstance(helpful, int) or helpful < 0:
        errors.append("helpful_count must be a non-negative integer")
    if not isinstance(harmful, int) or harmful < 0:
        errors.append("harmful_count must be a non-negative integer")

    return sorted(set(errors))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Usage: validate_memory_card.py <card.json>")
        return 2
    errors = validate_memory_card(load_json(Path(argv[0])))
    if errors:
        print("MEMORY_CARD_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("MEMORY_CARD_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
