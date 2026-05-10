#!/usr/bin/env python3
"""Reject memory objects that try to act as evidence, policy, or certification."""

from __future__ import annotations

import json
import sys
from pathlib import Path


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


def iter_objects(obj):
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from iter_objects(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from iter_objects(value)


def validate_memory_authority(obj: dict | list) -> list[str]:
    errors = []
    for item in iter_objects(obj):
        if not isinstance(item, dict):
            continue
        for key in sorted(AUTHORITY_LEAK_FIELDS):
            if key in item:
                errors.append(f"memory object contains authority-leak field: {key}")
        if item.get("can_certify_done") is not None and item.get("can_certify_done") is not False:
            errors.append("memory object cannot certify DONE")
        if item.get("final_status_authority") is not None and item.get("final_status_authority") != "certifier_only":
            errors.append("memory object final_status_authority must be certifier_only")
        if item.get("authority_level") is not None and item.get("authority_level") != "advisory_only":
            errors.append("memory object authority_level must be advisory_only")
    return sorted(set(errors))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Usage: validate_memory_authority.py <memory-object.json>")
        return 2
    errors = validate_memory_authority(load_json(Path(argv[0])))
    if errors:
        print("MEMORY_AUTHORITY_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("MEMORY_AUTHORITY_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
