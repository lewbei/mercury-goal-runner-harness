#!/usr/bin/env python3
"""Validate prompt-compiler seed eval cases.

These cases are diagnostic fixtures for prompt improvement. They are not final
certification evidence and they do not prove arbitrary prompt coverage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "schema_version": str,
    "case_id": str,
    "title": str,
    "raw_prompt": str,
    "target_model": str,
    "task_type": str,
    "expected_behavior": str,
    "failure_traps": list,
    "scoring_checks": list,
}

VALID_SCHEMA_VERSION = "prompt_eval_case_v1"


class PromptEvalCaseError(ValueError):
    """Raised when a prompt eval case is malformed."""


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def validate_case(data: dict, *, source: str = "<case>") -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"{source}: case must be a JSON object"]

    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"{source}: missing required field {field}")
            continue
        if not isinstance(data[field], expected_type):
            errors.append(f"{source}: field {field} must be {expected_type.__name__}")

    if data.get("schema_version") != VALID_SCHEMA_VERSION:
        errors.append(f"{source}: schema_version must be {VALID_SCHEMA_VERSION}")

    for field in ("case_id", "title", "raw_prompt", "target_model", "task_type", "expected_behavior"):
        value = data.get(field)
        if isinstance(value, str) and not value.strip():
            errors.append(f"{source}: field {field} must be non-empty")

    traps = data.get("failure_traps", [])
    if isinstance(traps, list):
        if not traps:
            errors.append(f"{source}: failure_traps must be non-empty")
        for idx, trap in enumerate(traps, start=1):
            if not isinstance(trap, str) or not trap.strip():
                errors.append(f"{source}: failure_traps[{idx}] must be a non-empty string")

    hard_fails = data.get("automatic_fail_rules", [])
    if hard_fails is not None:
        if not isinstance(hard_fails, list):
            errors.append(f"{source}: automatic_fail_rules must be a list when present")
        else:
            for idx, rule in enumerate(hard_fails, start=1):
                if not isinstance(rule, str) or not rule.strip():
                    errors.append(f"{source}: automatic_fail_rules[{idx}] must be a non-empty string")

    checks = data.get("scoring_checks", [])
    if isinstance(checks, list):
        if not checks:
            errors.append(f"{source}: scoring_checks must be non-empty")
        seen_ids = set()
        total_points = 0
        for idx, check in enumerate(checks, start=1):
            loc = f"{source}: scoring_checks[{idx}]"
            if not isinstance(check, dict):
                errors.append(f"{loc} must be an object")
                continue
            check_id = check.get("check_id")
            if not isinstance(check_id, str) or not check_id.strip():
                errors.append(f"{loc}.check_id must be non-empty")
            elif check_id in seen_ids:
                errors.append(f"{loc}.check_id is duplicated: {check_id}")
            else:
                seen_ids.add(check_id)
            points = check.get("points")
            if not isinstance(points, int) or points <= 0:
                errors.append(f"{loc}.points must be a positive integer")
            else:
                total_points += points
            keywords = check.get("must_include_any")
            if not isinstance(keywords, list) or not keywords:
                errors.append(f"{loc}.must_include_any must be a non-empty list")
            else:
                for key_idx, keyword in enumerate(keywords, start=1):
                    if not isinstance(keyword, str) or not keyword.strip():
                        errors.append(f"{loc}.must_include_any[{key_idx}] must be non-empty")
            if "hard_fail" in check and not isinstance(check["hard_fail"], bool):
                errors.append(f"{loc}.hard_fail must be boolean when present")
        if total_points <= 0:
            errors.append(f"{source}: scoring_checks total points must be positive")

    return errors


def iter_case_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(path.glob("*.json"))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Usage: validate_prompt_eval_case.py <case.json|cases_dir>")
        return 2

    target = Path(argv[0])
    if not target.exists():
        print(f"PROMPT_EVAL_CASE_INVALID: path not found: {target}")
        return 1

    errors: list[str] = []
    files = iter_case_files(target)
    if not files:
        errors.append(f"{target}: no JSON case files found")

    for path in files:
        try:
            data = load_json(path)
        except Exception as exc:
            errors.append(f"{path}: cannot parse JSON: {exc}")
            continue
        errors.extend(validate_case(data, source=str(path)))

    if errors:
        print("PROMPT_EVAL_CASE_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PROMPT_EVAL_CASE_VALID")
    print(f"validated_cases={len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
