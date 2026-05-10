#!/usr/bin/env python3
"""Success Criteria Compiler — converts a goal contract into a set of
measurable success criteria.

This is a trusted core component. It never writes state directly;
it returns the compiled criteria set.
"""

import json
from pathlib import Path
from typing import Optional

# ─── Helpers ──────────────────────────────────────────────────────────────────


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


# ─── Compiler ─────────────────────────────────────────────────────────────────


def compile_from_goal_contract(goal_contract: dict, run_id: str) -> dict:
    """Compile a success_criteria_set from a goal contract.

    For goals with explicit success criteria, those are extracted directly.
    For goals without explicit criteria, sensible defaults are derived
    based on the goal type.

    Returns a success_criteria_set_v1 dict.
    """
    goal_id = goal_contract.get("goal_id", "")

    # Try to extract explicit criteria from contract
    explicit = goal_contract.get("success_criteria", [])
    if explicit:
        criteria = _normalize_explicit_criteria(explicit)
    else:
        # Derive criteria from goal type
        criteria = _derive_criteria_from_goal(goal_contract)

    return {
        "schema_version": "success_criteria_set_v1",
        "run_id": run_id,
        "source_goal_id": goal_id,
        "criteria": criteria,
        "compilation_timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "compilation_strategy": "extracted" if explicit else "derived",
    }


def _normalize_explicit_criteria(explicit: list) -> list:
    """Normalize explicit success criteria from a goal contract.

    Each entry can be a string (description only) or a full criterion dict.
    """
    criteria = []
    for i, entry in enumerate(explicit):
        if isinstance(entry, str):
            criteria.append({
                "criterion_id": f"SC.{i+1:03d}",
                "description": entry,
                "measurable_indicator": {"type": "oracle_output"},
                "required": True,
                "priority": "MEDIUM",
                "oracle_types": ["STRUCTURAL_ORACLE", "BEHAVIORAL_ORACLE"],
                "minimum_oracle_strength": "P1_VISIBLE",
            })
        elif isinstance(entry, dict):
            criterion = dict(entry)
            criterion.setdefault("criterion_id", f"SC.{i+1:03d}")
            criterion.setdefault("required", True)
            criterion.setdefault("priority", "MEDIUM")
            criterion.setdefault("oracle_types", ["STRUCTURAL_ORACLE", "BEHAVIORAL_ORACLE"])
            criterion.setdefault("minimum_oracle_strength", "P1_VISIBLE")
            criterion.setdefault("measurable_indicator", {"type": "oracle_output"})
            criteria.append(criterion)
    return criteria


def _derive_criteria_from_goal(goal_contract: dict) -> list:
    """Derive default criteria from the goal contract when none are explicit.

    Uses goal type and description to produce sensible defaults.
    """
    goal_type = goal_contract.get("goal_type", "generic")
    description = goal_contract.get("description", "")
    criteria = []

    # Common criterion: goal produces output
    criteria.append({
        "criterion_id": "SC.001",
        "description": f"Goal '{goal_type}' produces expected output",
        "measurable_indicator": {"type": "oracle_output"},
        "required": True,
        "priority": "HIGH",
        "oracle_types": ["STRUCTURAL_ORACLE", "BEHAVIORAL_ORACLE"],
        "minimum_oracle_strength": "P1_VISIBLE",
    })

    # Add type-specific criteria
    if goal_type in ("coding", "implementation"):
        criteria.append({
            "criterion_id": "SC.002",
            "description": "Implementation produces valid source files",
            "measurable_indicator": {"type": "file_exists"},
            "required": True,
            "priority": "HIGH",
            "oracle_types": ["STRUCTURAL_ORACLE"],
            "minimum_oracle_strength": "P0_SELF",
        })
        criteria.append({
            "criterion_id": "SC.003",
            "description": "Implementation passes basic validation",
            "measurable_indicator": {"type": "command_passes"},
            "required": True,
            "priority": "MEDIUM",
            "oracle_types": ["BEHAVIORAL_ORACLE"],
            "minimum_oracle_strength": "P1_VISIBLE",
        })
    elif goal_type in ("test", "verification"):
        criteria.append({
            "criterion_id": "SC.002",
            "description": "Test suite is defined and runnable",
            "measurable_indicator": {"type": "file_exists"},
            "required": True,
            "priority": "HIGH",
            "oracle_types": ["STRUCTURAL_ORACLE"],
            "minimum_oracle_strength": "P0_SELF",
        })

    return criteria
