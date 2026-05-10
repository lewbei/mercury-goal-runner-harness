#!/usr/bin/env python3
"""
Clean deterministic orchestrator for a QRSPI run.

Runs the following phases in order:
1. init_run
2. artifact_linker
3. task_graph_builder
4. harness_contract_verifier
5. harness_signing
6. certify_run

Each phase is a separate Python script located under .agentic-pi/runtime
(or .agentic-pi/formal for verification and signing). The orchestrator
uses subprocess.run to execute them, prints the return code and any
output, and aborts on failure.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional


def run_phase(script_path: Path, description: str, extra_args: Optional[list[str]] = None) -> None:
    """Run a phase script via subprocess.run, raising on failure."""
    if not script_path.is_file():
        raise RuntimeError(f"{description} script not found at {script_path}")
    cmd = [sys.executable, str(script_path)]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    print(f"=== {description} ===")
    print(f"Return code: {result.returncode}")
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        raise RuntimeError(f"{description} failed with code {result.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic QRSPI pipeline.")
    parser.add_argument("--run-id", required=True, help="Identifier for the run")
    args = parser.parse_args()

    run_id = args.run_id

    # Repository root is two levels up from this file (.agentic-pi/runtime -> repo root)
    repo_root = Path(__file__).resolve().parents[2]
    run_dir = repo_root / ".agentic-runs" / run_id

    # Define phase scripts (relative to repo root) with their CLI arguments
    phases = [
        (
            "init_run",
            repo_root / ".agentic-pi" / "runtime" / "init_run.py",
            ["--run-id", run_id],
        ),
        (
            "artifact_linker",
            repo_root / ".agentic-pi" / "runtime" / "artifact_linker.py",
            [run_id],
        ),
        (
            "task_graph_builder",
            repo_root / ".agentic-pi" / "runtime" / "task_graph_builder.py",
            [run_id],
        ),
        (
            "harness_contract_verifier",
            repo_root / ".agentic-pi" / "formal" / "harness_contract_verifier.py",
            [str(run_dir)],
        ),
        (
            "harness_signing",
            repo_root / ".agentic-pi" / "formal" / "harness_signing.py",
            ["keygen", str(run_dir)],
        ),
        (
            "certify_run",
            repo_root / ".agentic-pi" / "validators" / "certify_run.py",
            [str(run_dir)],
        ),
    ]

    for name, script, phase_args in phases:
        run_phase(script, f"Phase {name}", phase_args)

    print("Deterministic pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
