#!/usr/bin/env python3
"""Validator for the mapping between success criteria and oracle types.

Each success criterion declares the oracle types that can verify it.
This validator checks:
1. Every criterion has at least one oracle type.
2. Every declared oracle type is recognized.
3. The oracle strength is sufficient for the criterion's priority.
4. Structural oracle alone cannot certify semantic success.
"""

from pathlib import Path
from typing import Optional

# Known oracle types (from oracle_registry.json)
_KNOWN_ORACLE_TYPES = {
    "STRUCTURAL_ORACLE",
    "BEHAVIORAL_ORACLE",
    "SEMANTIC_ORACLE",
    "COMPARATIVE_ORACLE",
    "NEGATIVE_ORACLE",
    "REPLAY_ORACLE",
    "EXTERNAL_ORACLE",
}

# Oracle strengths ordered weakest to strongest
_STRENGTH_ORDER = {
    "P0_SELF": 0,
    "P1_VISIBLE": 1,
    "P2_INDEPENDENT": 2,
    "P3_EXTERNAL": 3,
}

# Priority -> minimum recommended strength
_PRIORITY_MIN_STRENGTH = {
    "CRITICAL": "P2_INDEPENDENT",
    "HIGH": "P1_VISIBLE",
    "MEDIUM": "P1_VISIBLE",
    "LOW": "P0_SELF",
}


def validate_oracle_mapping(criteria_set: dict) -> list[dict]:
    """Validate the oracle mapping for each criterion.

    Returns list of result dicts:
    {
        "criterion_id": str,
        "valid": bool,
        "warnings": list[str],
        "errors": list[str]
    }
    """
    criteria = criteria_set.get("criteria", [])
    results = []

    for c in criteria:
        cid = c.get("criterion_id", "?")
        oracle_types = c.get("oracle_types", [])
        min_strength = c.get("minimum_oracle_strength", "P1_VISIBLE")
        priority = c.get("priority", "MEDIUM")
        errors = []
        warnings = []

        # 1. Must have at least one oracle type
        if not oracle_types:
            errors.append("No oracle types declared")

        # 2. Each oracle type must be recognized
        for ot in oracle_types:
            if ot not in _KNOWN_ORACLE_TYPES:
                errors.append(f"Unknown oracle type: '{ot}'")

        # 3. Structural oracle alone cannot certify semantic success
        if set(oracle_types) == {"STRUCTURAL_ORACLE"}:
            warnings.append(
                "STRUCTURAL_ORACLE alone cannot certify semantic success. "
                "Add a BEHAVIORAL_ORACLE or SEMANTIC_ORACLE for higher confidence."
            )

        # 4. Strength must be sufficient for priority
        required_strength = _PRIORITY_MIN_STRENGTH.get(priority, "P1_VISIBLE")
        if _STRENGTH_ORDER.get(min_strength, 0) < _STRENGTH_ORDER.get(required_strength, 1):
            warnings.append(
                f"Minimum oracle strength '{min_strength}' is below recommended "
                f"'{required_strength}' for priority '{priority}'"
            )

        results.append({
            "criterion_id": cid,
            "valid": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
        })

    return results


def all_valid(results: list[dict]) -> bool:
    """Return True if all mappings are valid (no errors)."""
    return all(r["valid"] for r in results)
