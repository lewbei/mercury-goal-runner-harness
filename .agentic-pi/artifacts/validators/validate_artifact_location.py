#!/usr/bin/env python3
"""Artifact location validator — the core check for Phase 3.

Given a run directory, loads expected_artifacts.json and checks each
expected artifact exists at its declared expected_path (relative to run_dir).

Returns structured verdicts:
- ACCEPTED: artifact found at correct path
- BLOCKED_BY_ARTIFACT_MISPLACEMENT: artifact exists but at wrong path
- NOT_DONE: required artifact missing entirely
- FAILED_AUTHORITY_VIOLATION: artifact written by forbidden role
"""

import json
import sys
from pathlib import Path
from typing import Optional


_RUN_KERNEL_DIR = Path(__file__).resolve().parents[2] / "run_kernel"
if str(_RUN_KERNEL_DIR) not in sys.path:
    sys.path.insert(0, str(_RUN_KERNEL_DIR))


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


# ─── Core validation ──────────────────────────────────────────────────────────


def scan_artifacts(run_dir: Path) -> list[dict]:
    """Scan all files in the run directory and categorize them.

    Returns a list of dicts with path, rel_path, and size.
    """
    found = []
    if not run_dir.is_dir():
        return found
    for fpath in run_dir.rglob("*"):
        if fpath.is_file():
            rel = fpath.relative_to(run_dir).as_posix()
            found.append({
                "path": fpath,
                "rel_path": rel,
                "size": fpath.stat().st_size,
            })
    return found


def validate_artifact_location(run_dir: Path, expected_artifacts: Optional[dict] = None) -> list[dict]:
    """Validate artifact locations for a run.

    Args:
        run_dir: The .agentic-runs/<run_id>/ directory.
        expected_artifacts: Optional pre-loaded expected_artifacts.json dict.
            If None, loads from run_dir/expected_artifacts.json.

    Returns:
        A list of verdict dicts, one per expected artifact:
        {
            "artifact_id": str,
            "expected_path": str,
            "verdict": "ACCEPTED" | "BLOCKED_BY_ARTIFACT_MISPLACEMENT" | "NOT_DONE",
            "actual_path": str or None,
            "error": str or None
        }
    """
    if expected_artifacts is None:
        ea_path = run_dir / "expected_artifacts.json"
        if not ea_path.exists():
            return [{
                "artifact_id": "__no_expected_artifacts__",
                "expected_path": "expected_artifacts.json",
                "verdict": "NOT_DONE",
                "actual_path": None,
                "error": "expected_artifacts.json not found in run directory",
            }]
        expected_artifacts = load_json(ea_path)

    artifacts_list = expected_artifacts.get("artifacts", [])
    if not artifacts_list:
        return [{
            "artifact_id": "__empty_expected_list__",
            "expected_path": "",
            "verdict": "NOT_DONE",
            "actual_path": None,
            "error": "expected_artifacts.json contains no artifact entries",
        }]

    # Scan filesystem once
    found_files = scan_artifacts(run_dir)
    found_map = {f["rel_path"]: f for f in found_files}

    verdicts = []
    for art in artifacts_list:
        aid = art["artifact_id"]
        expected = art["expected_path"]
        required = art.get("required", True)

        if expected in found_map:
            # Exact match at expected path
            verdicts.append({
                "artifact_id": aid,
                "expected_path": expected,
                "verdict": "ACCEPTED",
                "actual_path": expected,
                "error": None,
            })
        else:
            # Check if artifact exists at a wrong/free path (same basename)
            basename = Path(expected).name
            wrong_paths = [
                f["rel_path"] for f in found_files
                if Path(f["rel_path"]).name == basename and f["rel_path"] != expected
            ]
            if wrong_paths:
                verdicts.append({
                    "artifact_id": aid,
                    "expected_path": expected,
                    "verdict": "BLOCKED_BY_ARTIFACT_MISPLACEMENT",
                    "actual_path": wrong_paths[0],
                    "error": f"Found at '{wrong_paths[0]}' instead of '{expected}'",
                })
            elif required:
                verdicts.append({
                    "artifact_id": aid,
                    "expected_path": expected,
                    "verdict": "NOT_DONE",
                    "actual_path": None,
                    "error": f"Required artifact '{aid}' not found at '{expected}'",
                })
            else:
                # Optional artifact missing: not an error
                verdicts.append({
                    "artifact_id": aid,
                    "expected_path": expected,
                    "verdict": "ACCEPTED",
                    "actual_path": None,
                    "error": None,
                })

    return verdicts


def has_misplacement(verdicts: list[dict]) -> bool:
    """Return True if any verdict is BLOCKED_BY_ARTIFACT_MISPLACEMENT."""
    return any(v["verdict"] == "BLOCKED_BY_ARTIFACT_MISPLACEMENT" for v in verdicts)


def has_missing_required(verdicts: list[dict]) -> bool:
    """Return True if any required artifact is missing (NOT_DONE)."""
    return any(v["verdict"] == "NOT_DONE" for v in verdicts)


def all_accepted(verdicts: list[dict]) -> bool:
    """Return True if all verdicts are ACCEPTED."""
    return all(v["verdict"] == "ACCEPTED" for v in verdicts)
