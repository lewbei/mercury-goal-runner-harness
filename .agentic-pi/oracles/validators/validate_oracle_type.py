#!/usr/bin/env python3
"""Validator for oracle type names.

Checks that an oracle type string is a known type from the registry.
"""

import json
from pathlib import Path
from typing import Optional


_ORACLES_DIR = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _ORACLES_DIR / "oracle_registry.json"

# Cache
_known_types: Optional[set[str]] = None


def _load_registry() -> dict:
    with _REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _get_known_types() -> set[str]:
    global _known_types
    if _known_types is None:
        registry = _load_registry()
        _known_types = {o["oracle_type"] for o in registry.get("oracles", [])}
    return _known_types


def validate_oracle_type(oracle_type: str) -> list[str]:
    """Validate a single oracle type string.

    Returns list of error strings. Empty list means valid.
    """
    known = _get_known_types()
    if oracle_type not in known:
        return [
            f"Unknown oracle type '{oracle_type}'. "
            f"Must be one of: {sorted(known)}"
        ]
    return []


def validate_oracle_types(oracle_types: list[str]) -> list[str]:
    """Validate a list of oracle type strings."""
    errors = []
    for ot in oracle_types:
        errors.extend(validate_oracle_type(ot))
    return errors
