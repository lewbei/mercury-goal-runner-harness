#!/usr/bin/env python3
"""Materialize the canonical strict P2 golden run.

This script creates `.agentic-runs/golden_strict_p2_minimal/` from the tracked
fixture template. It prepares only non-final derived evidence needed by the
current strict runner. It never writes certifier-owned final status artifacts;
`full_verify.py` / `certify_run.py` remain the only final-status authority.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


RUN_ID = "golden_strict_p2_minimal"
PROTECTED_FINAL_STATUS_FILES = {
    "certification.json",
    "final_status.json",
    "final_status.md",
    "policy_decision.json",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def run_command(root: Path, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        raise SystemExit(result.returncode)
    if result.stdout.strip():
        print(result.stdout.strip())


def assert_no_final_status_artifacts(run_dir: Path) -> None:
    present = sorted(name for name in PROTECTED_FINAL_STATUS_FILES if (run_dir / name).exists())
    if present:
        raise RuntimeError(
            "materializer must not create certifier-owned final status artifacts: "
            + ", ".join(present)
        )


def materialize() -> Path:
    root = repo_root()
    template = Path(__file__).with_name("run_template")
    if not template.is_dir():
        raise FileNotFoundError(f"missing template directory: {template}")

    runs_root = root / ".agentic-runs"
    run_dir = runs_root / RUN_ID
    if run_dir.resolve() == runs_root.resolve() or run_dir.name != RUN_ID:
        raise RuntimeError(f"refusing unsafe run directory: {run_dir}")

    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template, run_dir)

    assert_no_final_status_artifacts(run_dir)

    # Non-final replay/audit prerequisites. These do not certify DONE.
    run_command(root, ".agentic-pi/runtime/audit_run.py", str(run_dir))
    assert_no_final_status_artifacts(run_dir)

    # Verifier-quality certification only; the final run status is still owned
    # by certify_run.py through full_verify.py.
    run_command(root, ".agentic-pi/validators/validator_factory.py", str(run_dir))
    assert_no_final_status_artifacts(run_dir)

    print(f"Materialized {run_dir}")
    return run_dir


if __name__ == "__main__":
    materialize()
