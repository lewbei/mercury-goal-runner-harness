#!/usr/bin/env python3
"""Validator for success criteria schema and internal consistency.

This is a trusted core component. It never writes state.
"""

import copy
import json
import sys
from pathlib import Path


_SUCCESS_DIR = Path(__file__).resolve().parent.parent
_CRITERION_SCHEMA_PATH = _SUCCESS_DIR / "success_criteria.schema.json"
_SET_SCHEMA_PATH = _SUCCESS_DIR / "success_criteria_set.schema.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _load_schema_validator():
    """Lazy-import the shared schema validator."""
    validators_dir = _SUCCESS_DIR.parent / "validators"
    if str(validators_dir) not in sys.path:
        sys.path.insert(0, str(validators_dir))
    from validate_schema import validate as _validate
    return _validate


def validate_criterion(criterion: dict) -> list[str]:
    """Validate a single success criterion against its schema."""
    schema = _load_json(_CRITERION_SCHEMA_PATH)
    validator = _load_schema_validator()
    return validator(criterion, schema)


def validate_criteria_set(criteria_set: dict) -> list[str]:
    """Validate a full success_criteria_set against schema and internal rules.

    Returns list of error strings. Empty list means valid.
    """
    errors: list[str] = []

    # Schema validation
    schema = copy.deepcopy(_load_json(_SET_SCHEMA_PATH))
    # The shared lightweight schema validator intentionally supports only
    # local $ref values. This validator performs per-criterion validation below,
    # so the set-level schema should validate container shape without following
    # the external success_criteria.schema.json reference.
    schema.get("properties", {}).get("criteria", {}).get("items", {}).pop("$ref", None)
    validator = _load_schema_validator()
    errors.extend(validator(criteria_set, schema))
    if errors:
        return errors

    criteria = criteria_set.get("criteria", [])
    ids = []
    for c in criteria:
        cid = c.get("criterion_id")
        if cid in ids:
            errors.append(f"Duplicate criterion_id: '{cid}'")
        ids.append(cid)

        # Validate each criterion individually
        errors.extend(validate_criterion(c))

    return errors


def validate_file(path: Path) -> list[str]:
    """Load a success_criteria_set.json and validate it."""
    try:
        data = _load_json(path)
    except Exception as exc:
        return [f"Failed to load: {exc}"]
    return validate_criteria_set(data)
