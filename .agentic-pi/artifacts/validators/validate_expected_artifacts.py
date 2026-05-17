#!/usr/bin/env python3
"""Validator for expected_artifacts.json against its schema and internal consistency.

This is a trusted core component. It never writes state.
"""

import json
import sys
from pathlib import Path
from typing import Optional

_ARTIFACTS_DIR = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _ARTIFACTS_DIR / "expected_artifacts.schema.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _load_schema() -> dict:
    return _load_json(_SCHEMA_PATH)


def _load_schema_validator():
    """Lazy-import the shared schema validator."""
    validators_dir = _ARTIFACTS_DIR.parent / "validators"
    if str(validators_dir) not in sys.path:
        sys.path.insert(0, str(validators_dir))
    from validate_schema import validate as _validate
    return _validate


def validate_expected_artifacts(artifacts: dict) -> list[str]:
    """Validate expected_artifacts.json against schema and internal rules.

    Returns a list of error strings. Empty list means valid.
    """
    errors: list[str] = []

    # Schema validation
    schema = _load_schema()
    schema_validator = _load_schema_validator()
    errors.extend(schema_validator(artifacts, schema))

    if errors:
        return errors

    # Internal consistency checks
    artifact_ids = []
    expected_paths = []
    for art in artifacts.get("artifacts", []):
        aid = art.get("artifact_id")
        if aid in artifact_ids:
            errors.append(f"Duplicate artifact_id: '{aid}'")
        artifact_ids.append(aid)

        ep = art.get("expected_path")
        if ep in expected_paths:
            errors.append(f"Duplicate expected_path: '{ep}'")
        expected_paths.append(ep)

        # Check forbidden_writers doesn't contain allowed_writers
        allowed = set(art.get("allowed_writers", []))
        forbidden = set(art.get("forbidden_writers", []))
        overlap = allowed & forbidden
        if overlap:
            errors.append(
                f"Artifact '{aid}': allowed_writers and forbidden_writers overlap: {overlap}"
            )

    return errors


def validate_file(path: Path) -> list[str]:
    """Load expected_artifacts.json from a path and validate it."""
    try:
        data = _load_json(path)
    except Exception as exc:
        return [f"Failed to load expected_artifacts.json: {exc}"]
    return validate_expected_artifacts(data)
