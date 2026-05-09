#!/usr/bin/env python3
"""Validate a command against the security command policy allowlist.

This is a trusted core validator. It does not write state.
"""

from __future__ import annotations

import json
from pathlib import Path


_EXECUTION_DIR = Path(__file__).resolve().parents[1]
_SECURITY_DIR = _EXECUTION_DIR.parent / "security"
_SECURITY_POLICY_PATH = _SECURITY_DIR / "command_policy.json"


def load_command_policy(policy_path: Path | None = None) -> dict:
    """Load the command policy from security/command_policy.json."""
    path = policy_path or _SECURITY_POLICY_PATH
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def is_command_allowed(command: str, policy: dict | None = None) -> tuple[bool, str]:
    """Check if a command is allowed under the command policy.

    Returns (allowed, reason).
    """
    if policy is None:
        policy = load_command_policy()

    command_stripped = command.strip().lower()

    # Check forbidden patterns first
    for pattern in policy.get("forbidden_patterns", []):
        if pattern.lower() in command_stripped:
            return False, f"Matches forbidden pattern: {pattern}"

    # Check safe commands (always allowed)
    for safe in policy.get("safe_commands", []):
        if command_stripped.startswith(safe.lower()):
            return True, "Safe command"

    # Check medium risk commands
    for medium in policy.get("medium_risk_commands", []):
        if command_stripped.startswith(medium.lower()):
            return True, "Medium-risk command (allowed)"

    # Check high risk commands
    for high in policy.get("high_risk_commands_require_approval", []):
        if command_stripped.startswith(high.lower()):
            return False, f"High-risk command requires approval: {high}"

    # Default: deny if default_policy is deny_risky
    default = policy.get("default_policy", "deny_risky_without_approval")
    if default == "deny":
        return False, "Command not in allowlist"
    if default == "deny_risky_without_approval":
        # Unknown commands are treated as risky
        return False, "Unknown command (treated as risky)"

    return True, "Allowed by default policy"


def validate_command(command: str, policy_path: Path | None = None) -> dict:
    """Run validation and return a structured result.

    Returns:
        {"command": str, "allowed": bool, "reason": str}
    """
    allowed, reason = is_command_allowed(command, policy_path)
    return {
        "command": command,
        "allowed": allowed,
        "reason": reason,
    }
