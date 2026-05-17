#!/usr/bin/env python3
"""Fallback artifact checker.

This validator ensures that if an expected artifact declares a specific path,
a fallback artifact (same basename but different directory) does not satisfy
the contract. E.g., expected artifacts/report.json cannot be satisfied by
report.json at the run root.
"""

import json
from pathlib import Path
from typing import Optional


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def check_no_fallback_artifacts(run_dir: Path, expected_artifacts: Optional[dict] = None) -> list[dict]:
    """Check for fallback artifacts that could mistakenly satisfy a contract.

    Args:
        run_dir: The .agentic-runs/<run_id>/ directory.
        expected_artifacts: Optional pre-loaded expected_artifacts.json dict.

    Returns:
        List of warning dicts:
        {
            "artifact_id": str,
            "expected_path": str,
            "fallback_path": str,
            "message": str
        }
    """
    if expected_artifacts is None:
        ea_path = run_dir / "expected_artifacts.json"
        if not ea_path.exists():
            return []
        expected_artifacts = load_json(ea_path)

    artifacts_list = expected_artifacts.get("artifacts", [])
    if not artifacts_list:
        return []

    warnings = []
    for art in artifacts_list:
        aid = art["artifact_id"]
        expected = art["expected_path"]
        basename = Path(expected).name

        # Check all ancestor directories for the same basename
        parent = Path(expected).parent
        if parent.as_posix() == ".":
            continue  # expected at root, no fallback possible

        # Check if a file with the same basename exists at any parent level
        path_parts = expected.split("/")
        for i in range(1, len(path_parts)):
            ancestor_path = "/".join(path_parts[i:])
            candidate = run_dir / ancestor_path
            if candidate.exists() and candidate.is_file():
                warnings.append({
                    "artifact_id": aid,
                    "expected_path": expected,
                    "fallback_path": ancestor_path,
                    "message": f"Fallback artifact '{ancestor_path}' exists alongside expected path '{expected}'. "
                               f"This could satisfy a naive existence check.",
                    "severity": "WARNING",
                })

    return warnings
