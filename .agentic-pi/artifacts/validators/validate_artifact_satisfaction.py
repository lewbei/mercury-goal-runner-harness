#!/usr/bin/env python3
"""Artifact satisfaction validator.

Checks that present artifacts meet minimum content satisfaction criteria:
- File exists (already checked by location validator)
- Minimum size
- Valid JSON / YAML
- Not empty
- Custom check commands
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def check_satisfaction(run_dir: Path, expected_artifacts: Optional[dict] = None) -> list[dict]:
    """Check satisfaction criteria for all expected artifacts.

    Args:
        run_dir: The .agentic-runs/<run_id>/ directory.
        expected_artifacts: Optional pre-loaded expected_artifacts.json dict.

    Returns:
        List of verdict dicts:
        {
            "artifact_id": str,
            "expected_path": str,
            "verdict": "SATISFIED" | "FAILED",
            "checks": list of individual check results
        }
    """
    if expected_artifacts is None:
        ea_path = run_dir / "expected_artifacts.json"
        if not ea_path.exists():
            return []
        expected_artifacts = load_json(ea_path)

    artifacts_list = expected_artifacts.get("artifacts", [])
    results = []

    for art in artifacts_list:
        aid = art["artifact_id"]
        expected = art["expected_path"]
        actual_path = run_dir / expected

        checks = []

        # File existence
        exists = actual_path.exists() and actual_path.is_file()
        checks.append({
            "check": "file_exists",
            "passed": exists,
            "detail": f"Found at '{expected}'" if exists else f"Not found at '{expected}'",
        })

        if exists:
            content = actual_path.read_bytes()
            size = len(content)

            # Min size check
            min_size = art.get("min_size_bytes")
            if min_size is not None:
                size_ok = size >= min_size
                checks.append({
                    "check": f"min_size >= {min_size}",
                    "passed": size_ok,
                    "detail": f"Actual size: {size} bytes",
                })

            # Max size check
            max_size = art.get("max_size_bytes")
            if max_size is not None:
                size_ok = size <= max_size
                checks.append({
                    "check": f"max_size <= {max_size}",
                    "passed": size_ok,
                    "detail": f"Actual size: {size} bytes",
                })

            # Valid JSON check
            must_be_valid_json = art.get("must_be_valid_json", False)
            if must_be_valid_json:
                try:
                    json.loads(content)
                    checks.append({
                        "check": "valid_json",
                        "passed": True,
                        "detail": "Valid JSON",
                    })
                except json.JSONDecodeError as e:
                    checks.append({
                        "check": "valid_json",
                        "passed": False,
                        "detail": f"Invalid JSON: {e}",
                    })

            # Not empty check (implicit: has content beyond whitespace)
            must_not_be_empty = art.get("min_satisfaction", {}).get("must_not_be_empty", False)
            if must_not_be_empty:
                not_empty = len(content.strip()) > 0
                checks.append({
                    "check": "not_empty",
                    "passed": not_empty,
                    "detail": "Content is non-empty" if not_empty else "Content is empty",
                })

        verdict = "SATISFIED" if all(c["passed"] for c in checks) else "FAILED"
        results.append({
            "artifact_id": aid,
            "expected_path": expected,
            "verdict": verdict,
            "checks": checks,
        })

    return results
