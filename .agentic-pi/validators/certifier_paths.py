"""Run-local path helpers and protected certifier path constants.

This module centralizes path confinement and protected evidence/result names for
certifier checks. It performs no command execution and writes no files.
"""

from __future__ import annotations

from pathlib import Path


PROTECTED_NAMES = {
    "certification.json",
    "final_status.json",
    "final_status.md",
    "policy_decision.json",
    "trace.jsonl",
}

PROTECTED_PREFIXES = {
    "verifier_artifacts/",
    "verifier_smell_reports/",
    "verifier_strength_reports/",
}


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute path is not allowed: {raw_path}")

    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {raw_path}")
    return resolved


def run_relative(run_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(run_dir.resolve()).as_posix()


def output_candidates(run_dir: Path, output: str):
    yield resolve_run_path(run_dir, output)


def find_output(run_dir: Path, output: str):
    for candidate in output_candidates(run_dir, output):
        if candidate.exists():
            return candidate
    return None


def non_empty_string_list(value) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.strip() for item in value)
    )
