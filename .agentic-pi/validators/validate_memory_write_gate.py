#!/usr/bin/env python3
"""Validate memory_write_gate decisions."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / ".agentic-pi" / "schemas" / "memory_write_decision.schema.json"
SCHEMA_VALIDATOR_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema", SCHEMA_VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_memory_write_decision(decision: dict) -> list[str]:
    validator = load_schema_validator()
    errors = validator.validate(decision, load_json(SCHEMA_PATH))
    if not isinstance(decision, dict):
        return errors

    if decision.get("final_status_authority") != "certifier_only":
        errors.append("memory write decision final_status_authority must be certifier_only")
    if decision.get("can_certify_done") is not False:
        errors.append("memory write gate cannot certify DONE")
    if decision.get("decision") == "APPROVED":
        if decision.get("promoted") is not True:
            errors.append("APPROVED decision must set promoted=true")
        if not decision.get("target_path"):
            errors.append("APPROVED decision must include target_path")
    if decision.get("decision") == "REJECTED" and decision.get("promoted") is True:
        errors.append("REJECTED decision cannot set promoted=true")
    return sorted(set(errors))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Usage: validate_memory_write_gate.py <memory_write_decision.json>")
        return 2
    errors = validate_memory_write_decision(load_json(Path(argv[0])))
    if errors:
        print("MEMORY_WRITE_DECISION_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("MEMORY_WRITE_DECISION_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
