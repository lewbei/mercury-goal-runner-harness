#!/usr/bin/env python3
"""Validate that no file write targets a protected path or authority artifact.

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


def is_protected_path(file_path: str, policy: dict | None = None) -> tuple[bool, str]:
    """Check if a file path is protected (authority file or protected directory).

    Returns (is_protected, reason).
    """
    if policy is None:
        policy = load_write_scope_policy()

    normalized_path = file_path.replace("\\", "/")

    # Check authority files
    for auth_file in policy.get("authority_files", []):
        if normalized_path.endswith(auth_file):
            return True, f"Path is an authority file: {auth_file}"

    # Check protected directories
    for protected_dir in policy.get("protected_directories", []):
        if normalized_path.startswith(protected_dir.replace("\\", "/")):
            return True, f"Path is inside protected directory: {protected_dir}"

    # Check verifier artifacts (special protected prefix)
    if "/verifier_artifacts/" in normalized_path and "verifier_artifacts" in normalized_path:
        # Only ValidatorEngineer may write here; all others are protected
        return True, "Path is in verifier_artifacts/ (role-gated)"

    return False, ""


def validate_protected_file(
    file_path: str,
    policy_path: Path | None = None,
) -> dict:
    """Run protected file validation and return a structured result."""
    is_protected, reason = is_protected_path(file_path, policy_path)
    return {
        "file_path": file_path,
        "protected": is_protected,
        "reason": reason,
    }
