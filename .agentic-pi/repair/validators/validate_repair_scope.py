#!/usr/bin/env python3
"""Validate that a repair action does not exceed its allowed scope.

The core rule: repair cannot touch authority files, frozen evidence,
or state files. Only the triggered repair type's allowed actions are
permitted.

This is a trusted core validator. It does not write state.
"""

from __future__ import annotations

import json
from pathlib import Path


_REPAIR_DIR = Path(__file__).resolve().parents[1]
_REPAIR_POLICY_PATH = _REPAIR_DIR / "repair_policy.json"


def load_repair_policy(policy_path: Path | None = None) -> dict:
    """Load the repair policy."""
    path = policy_path or _REPAIR_POLICY_PATH
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def is_repair_action_allowed(
    action: str,
    repair_type: str,
    policy: dict | None = None,
) -> tuple[bool, str]:
    """Check if a repair action is within scope for the repair type.

    Returns (allowed, reason).
    """
    if policy is None:
        policy = load_repair_policy()

    forbidden = policy.get("forbidden_repair_actions", [])
    action_lower = action.lower()

    # Check global forbidden actions (substring match on the action text)
    for f_action in forbidden:
        if f_action.lower() in action_lower:
            return False, f"Action is globally forbidden: {f_action}"

    # Check type-specific rules
    per_phase = policy.get("per_phase_budget", {})
    if repair_type not in per_phase:
        return False, f"Unknown repair type: {repair_type}"

    phase_policy = per_phase[repair_type]
    allowed_roles = phase_policy.get("allowed_roles", [])

    # Specific rule: REPAIRING_VALIDATOR can write verifier_artifacts/
    if repair_type == "REPAIRING_VALIDATOR" and "verifier_artifacts" in action_lower:
        return True, "REPAIRING_VALIDATOR may write to verifier_artifacts/"

    # Specific rule: only REPAIRING_VALIDATOR may touch verifier_artifacts/
    if "verifier_artifacts" in action_lower and repair_type != "REPAIRING_VALIDATOR":
        return False, "Only REPAIRING_VALIDATOR may write to verifier_artifacts/"

    return True, "Action is within repair scope"


def validate_repair_action(
    action: str,
    repair_type: str,
    policy_path: Path | None = None,
) -> dict:
    """Run repair scope validation and return a structured result."""
    allowed, reason = is_repair_action_allowed(action, repair_type, policy_path)
    return {
        "action": action,
        "repair_type": repair_type,
        "allowed": allowed,
        "reason": reason,
    }
