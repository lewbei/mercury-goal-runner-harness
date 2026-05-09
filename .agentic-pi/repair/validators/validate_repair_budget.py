#!/usr/bin/env python3
"""Validate that a repair attempt is within the allowed budget.

Budget is tracked per repair type. When max_attempts is exceeded,
the run must escalate to a blocked state.

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


def get_repair_budget(repair_type: str, policy: dict | None = None) -> dict | None:
    """Get the budget info for a repair type.

    Returns None if the repair type is not in the policy.
    """
    if policy is None:
        policy = load_repair_policy()
    per_phase = policy.get("per_phase_budget", {})
    return per_phase.get(repair_type)


def is_budget_exhausted(
    repair_type: str,
    current_attempts: int,
    policy: dict | None = None,
) -> tuple[bool, str]:
    """Check if the repair budget is exhausted.

    Returns (exhausted, reason_or_escalation_target).
    """
    if policy is None:
        policy = load_repair_policy()

    budget = get_repair_budget(repair_type, policy)
    if budget is None:
        # Unknown repair type: treat as exhausted
        return True, f"Unknown repair type: {repair_type}"

    max_attempts = budget.get("max_attempts", 1)
    global_max = policy.get("global_max_repair_attempts", 3)

    # Check per-phase budget
    if current_attempts >= max_attempts:
        escalation = budget.get("escalation_on_exhaustion", "BLOCKED")
        return True, f"Per-phase budget exhausted ({current_attempts}/{max_attempts}), escalate to {escalation}"

    # Check global budget
    if current_attempts >= global_max:
        return True, f"Global repair budget exhausted ({current_attempts}/{global_max})"

    return False, ""


def get_escalation_target(
    repair_type: str,
    policy: dict | None = None,
) -> str:
    """Get the escalation target phase when budget is exhausted."""
    if policy is None:
        policy = load_repair_policy()
    budget = get_repair_budget(repair_type, policy)
    if budget is None:
        return "BLOCKED"
    return budget.get("escalation_on_exhaustion", "BLOCKED")


def validate_repair_attempt(
    repair_type: str,
    current_attempts: int,
    policy_path: Path | None = None,
) -> dict:
    """Run repair budget validation and return a structured result."""
    exhausted, reason = is_budget_exhausted(repair_type, current_attempts, policy_path)
    escalation = get_escalation_target(repair_type, policy_path) if exhausted else ""
    return {
        "repair_type": repair_type,
        "current_attempts": current_attempts,
        "budget_exhausted": exhausted,
        "reason": reason,
        "escalation_target": escalation,
    }
