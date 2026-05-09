#!/usr/bin/env python3
"""Vertical slice gate validator.

Checks whether a work packet's output represents a vertical slice
(one fixture, one expected verdict, one proof command) or horizontal
output (files with no end-to-end proof).

A vertical slice must have:
  1. A fixture — a known input case
  2. An expected verdict — what the harness must decide
  3. A proof command — a runnable command that proves the verdict
  4. A test change or new test — regression coverage

This is a trusted core validator. It does not write state.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


# Patterns that indicate a vertical proof exists in task text or output
_FIXTURE_PATTERNS = [
    r"fixture",
    r"test\s+case",
    r"input\s+case",
    r"create\s+.*\.json",
    r"case_\w+",
    r"MH\.\d{3}",
    r"VS\.\d{3}",
]

_VERDICT_PATTERNS = [
    r"expected\s+(status|verdict|result|outcome)",
    r"must\s+(be|return|block|fail|pass|reject)",
    r"should\s+(not\s+)?(be|reach|become|pass)",
    r"BLOCKED_BY_",
    r"NOT_DONE",
    r"V0_PROPOSED",
    r"PROVISIONAL_DONE",
    r"CERTIFIED_DONE",
    r"DONE_PASS",
    r"DONE_FAIL",
    r"REJECTED",
    r"ACCEPTED",
    r"FAILED_",
]

_PROOF_COMMAND_PATTERNS = [
    r"python\s+(tests/|\.agentic-pi/|\.)",
    r"pytest\s+",
    r"unittest\s+",
    r"run_proof_matrix",
    r"run_meta_harness",
]

_HORIZONTAL_PATTERNS = [
    r"create all",
    r"implement (the )?whole",
    r"build (the )?entire",
    r"all schemas",
    r"all validators",
    r"all docs",
    r"full (layer|framework)",
    r"refactor (everything|all)",
    r"no passing (test|proof)",
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Core check functions
# ═══════════════════════════════════════════════════════════════════════════════

def has_fixture(text: str) -> tuple[bool, str]:
    """Check if text references a fixture or test case."""
    for pattern in _FIXTURE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, f"Fixture reference found: '{pattern}'"
    return False, "No fixture or test case reference found"


def has_expected_verdict(text: str) -> tuple[bool, str]:
    """Check if text declares an expected verdict."""
    for pattern in _VERDICT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, f"Expected verdict found: '{pattern}'"
    return False, "No expected verdict found"


def has_proof_command(text: str) -> tuple[bool, str]:
    """Check if text includes a runnable proof command."""
    for pattern in _PROOF_COMMAND_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, f"Proof command found: '{pattern}'"
    return False, "No runnable proof command found"


def has_horizontal_pattern(text: str) -> tuple[bool, str]:
    """Check if text uses horizontal-building language."""
    for pattern in _HORIZONTAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, f"Horizontal pattern detected: '{pattern}'"
    return False, ""


def has_test_file(output_files: list[str]) -> tuple[bool, str]:
    """Check if any output file is a test file."""
    for f in output_files:
        if f.startswith("tests/") or f.startswith("tests\\"):
            return True, f"Test file found: {f}"
        if "/test_" in f or "\\test_" in f:
            return True, f"Test file found: {f}"
    return False, "No test file in output"


# ═══════════════════════════════════════════════════════════════════════════════
#  Main gate check
# ═══════════════════════════════════════════════════════════════════════════════

def has_vertical_proof(
    task_description: str,
    output_files: list[str],
    proof_command: str = "",
) -> tuple[bool, list[str]]:
    """Check if a work packet's output represents a vertical slice.

    Returns (is_vertical: bool, reasons: list[str]).
    An empty reasons list means the check passed.
    """
    reasons: list[str] = []
    combined = task_description + "\n" + proof_command

    # Check 1: horizontal pattern
    is_horizontal, reason = has_horizontal_pattern(combined)
    if is_horizontal:
        reasons.append(reason)

    # Check 2: fixture
    has_fix, reason = has_fixture(combined)
    if not has_fix:
        reasons.append(reason)
    else:
        reasons.append(reason)

    # Check 3: expected verdict
    has_verdict, reason = has_expected_verdict(combined)
    if not has_verdict:
        reasons.append(reason)
    else:
        reasons.append(reason)

    # Check 4: proof command
    has_proof, reason = has_proof_command(combined)
    if not has_proof:
        reasons.append(reason)
    else:
        reasons.append(reason)

    # Check 5: test file
    has_test, reason = has_test_file(output_files)
    if not has_test:
        reasons.append(reason)
    else:
        reasons.append(reason)

    # Passes only if ALL checks pass AND no horizontal pattern detected
    is_vertical = (
        not is_horizontal
        and has_fix
        and has_verdict
        and has_proof
        and has_test
    )

    return is_vertical, reasons


def format_rejection_reason(reasons: list[str]) -> str:
    """Format rejection reasons into a single string."""
    failures = [r for r in reasons if r.startswith("No ") or r.startswith("Horizontal")]
    if not failures:
        return ""
    return "REJECTED_HORIZONTAL_OUTPUT: " + "; ".join(failures)


# ═══════════════════════════════════════════════════════════════════════════════
#  Work packet validation
# ═══════════════════════════════════════════════════════════════════════════════

def validate_work_packet_vertical(
    task_description: str,
    output_files: list[str],
    proof_command: str = "",
) -> dict:
    """Run the full vertical slice check on a work packet and return a
    structured result suitable for the supervisor's determine_phase_outcome.

    Returns:
        {"vertical_slice_passed": bool, "reason": str, "checks": dict}
    """
    passed, reasons = has_vertical_proof(task_description, output_files, proof_command)
    return {
        "vertical_slice_passed": passed,
        "reason": format_rejection_reason(reasons) if not passed else "",
        "checks": {
            "has_fixture": any("Fixture reference" in r for r in reasons),
            "has_expected_verdict": any("Expected verdict" in r for r in reasons),
            "has_proof_command": any("Proof command" in r for r in reasons),
            "has_test_file": any("Test file" in r for r in reasons),
            "no_horizontal_pattern": not any("Horizontal pattern" in r for r in reasons),
        },
    }
