#!/usr/bin/env python3
"""Validator for oracle strength levels.

Checks that a strength level string is valid and that the combination
of oracle type + strength meets certification requirements.
"""

import json
from pathlib import Path
from typing import Optional


_ORACLES_DIR = Path(__file__).resolve().parent.parent
_STRENGTH_PATH = _ORACLES_DIR / "oracle_strength_rules.json"
_REGISTRY_PATH = _ORACLES_DIR / "oracle_registry.json"

# Cache
_strength_data: Optional[dict] = None
_registry_data: Optional[dict] = None


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _get_strength_data() -> dict:
    global _strength_data
    if _strength_data is None:
        _strength_data = _load_json(_STRENGTH_PATH)
    return _strength_data


def _get_registry() -> dict:
    global _registry_data
    if _registry_data is None:
        _registry_data = _load_json(_REGISTRY_PATH)
    return _registry_data


def validate_strength_level(level: str) -> list[str]:
    """Validate a strength level string."""
    data = _get_strength_data()
    known_levels = {l["level"] for l in data.get("strength_levels", [])}
    if level not in known_levels:
        return [
            f"Unknown oracle strength level '{level}'. "
            f"Must be one of: {sorted(known_levels)}"
        ]
    return []


def validate_oracle_provenance(oracle_type: str, strength_level: str) -> list[dict]:
    """Validate that an oracle type + strength combination is coherent.

    Returns list of warnings/errors:
    {
        "type": "warning" | "error",
        "message": str
    }
    """
    results = []
    registry = _get_registry()

    # Get oracle info
    oracle_info = None
    for o in registry.get("oracles", []):
        if o["oracle_type"] == oracle_type:
            oracle_info = o
            break

    if oracle_info:
        # Structural oracle limitation
        if not oracle_info.get("can_certify_semantic_success", True):
            results.append({
                "type": "warning",
                "message": f"Oracle type '{oracle_type}' cannot certify semantic success "
                           f"regardless of strength level. Requires a behavioral or semantic oracle.",
            })

        # Default minimum strength
        default_min = oracle_info.get("default_minimum_strength", "P0_SELF")
        data = _get_strength_data()
        levels = {l["level"]: l["rank"] for l in data.get("strength_levels", [])}
        if levels.get(strength_level, -1) < levels.get(default_min, 0):
            results.append({
                "type": "warning",
                "message": f"Strength level '{strength_level}' is below the default "
                           f"minimum '{default_min}' for oracle type '{oracle_type}'",
            })

    return results
