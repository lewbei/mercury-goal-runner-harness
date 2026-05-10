#!/usr/bin/env python3
"""Measurability validator for success criteria.

Checks that each criterion has a measurable indicator that can be
deterministically checked. Rejects vague, non-measurable criteria.
"""

from pathlib import Path
from typing import Optional

# Indicators that are inherently measurable
_MEASURABLE_INDICATORS = {
    "file_exists",
    "file_contains",
    "command_passes",
    "test_passes",
    "metric_threshold",
    "schema_valid",
    "oracle_output",
}

# Vague patterns in descriptions that suggest non-measurability
_VAGUE_PATTERNS = [
    "should work",
    "should be better",
    "user should feel",
    "should be intuitive",
    "as fast as possible",
    "high quality",
    "clean code",
    "properly",
    "nicely",
    "well designed",
    "good enough",
    "as expected",
]


def validate_measurability(criteria_set: dict) -> list[dict]:
    """Check each criterion for measurable indicators.

    Returns list of result dicts:
    {
        "criterion_id": str,
        "measurable": bool,
        "indicator_type": str or None,
        "warnings": list[str]
    }
    """
    criteria = criteria_set.get("criteria", [])
    results = []

    for c in criteria:
        cid = c.get("criterion_id", "?")
        indicator = c.get("measurable_indicator", {})
        indicator_type = indicator.get("type")
        description = c.get("description", "")
        warnings = []

        # Check indicator type is known
        if indicator_type not in _MEASURABLE_INDICATORS:
            warnings.append(f"Unknown or missing measurable_indicator type: '{indicator_type}'")

        # Check description for vague language
        desc_lower = description.lower()
        for pattern in _VAGUE_PATTERNS:
            if pattern in desc_lower:
                warnings.append(f"Description contains potentially vague language: '{pattern}'")

        # Commands need a specific command
        if indicator_type == "command_passes" and not indicator.get("command"):
            warnings.append("command_passes indicator missing 'command' field")

        # File checks need a path
        if indicator_type in ("file_exists", "file_contains") and not indicator.get("target_path"):
            warnings.append(f"{indicator_type} indicator missing 'target_path' field")

        results.append({
            "criterion_id": cid,
            "measurable": len(warnings) == 0,
            "indicator_type": indicator_type,
            "warnings": warnings,
        })

    return results


def all_measurable(results: list[dict]) -> bool:
    """Return True if all criteria are measurable."""
    return all(r["measurable"] for r in results)
