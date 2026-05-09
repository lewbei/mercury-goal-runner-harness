#!/usr/bin/env python3
"""Validate that a file write path is within the allowed scope for a role.

This is a trusted core validator. It does not write state.
"""

from __future__ import annotations

import json
from pathlib import Path


_EXECUTION_DIR = Path(__file__).resolve().parents[1]
_WRITE_SCOPE_PATH = _EXECUTION_DIR / "write_scope_policy.json"


def load_write_scope_policy(policy_path: Path | None = None) -> dict:
    """Load the write scope policy."""
    path = policy_path or _WRITE_SCOPE_PATH
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def resolve_path(template: str, run_id: str) -> str:
    """Replace {run_id} placeholder in a path template."""
    return template.replace("{run_id}", run_id)


def is_write_allowed(
    file_path: str,
    role: str,
    run_id: str,
    policy: dict | None = None,
) -> tuple[bool, str]:
    """Check if writing to file_path is allowed for the given role.

    Returns (allowed, reason).
    """
    if policy is None:
        policy = load_write_scope_policy()

    roles = policy.get("roles", {})
    if role not in roles:
        return False, f"Role '{role}' is not defined in write scope policy"

    role_policy = roles[role]
    normalized_path = file_path.replace("\\", "/")

    # Check forbidden prefixes first (deny before allow)
    for prefix in role_policy.get("forbidden_prefixes", []):
        resolved = resolve_path(prefix, run_id)
        if normalized_path.startswith(resolved.replace("\\", "/")):
            return False, f"Path matches forbidden prefix: {prefix}"

    # Check allowed prefixes
    for prefix in role_policy.get("allowed_prefixes", []):
        resolved = resolve_path(prefix, run_id)
        if normalized_path.startswith(resolved.replace("\\", "/")):
            return True, f"Path matches allowed prefix: {prefix}"

    # Check authority files globally (no role may write these)
    for auth_file in policy.get("authority_files", []):
        if normalized_path.endswith(auth_file):
            return False, f"Path is an authority file: {auth_file}"

    # Check protected directories
    for protected_dir in policy.get("protected_directories", []):
        if normalized_path.startswith(protected_dir.replace("\\", "/")):
            return False, f"Path is inside protected directory: {protected_dir}"

    # Default: deny if no prefix matches
    return False, f"No allowed prefix matches path for role '{role}'"


def validate_write_scope(
    file_path: str,
    role: str,
    run_id: str,
    policy_path: Path | None = None,
) -> dict:
    """Run write scope validation and return a structured result."""
    allowed, reason = is_write_allowed(file_path, role, run_id, policy_path)
    return {
        "file_path": file_path,
        "role": role,
        "run_id": run_id,
        "allowed": allowed,
        "reason": reason,
    }
