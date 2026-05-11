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
import json
import subprocess
import sys
from pathlib import Path


def run_phase(script_path: Path, description: str, extra_args: list = None) -> None:
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

    # Repository root is two levels up from this file (.agentic-pi/runtime -> repo root)
    repo_root = Path(__file__).resolve().parents[2]

    run_id = args.run_id
    run_dir = repo_root / ".agentic-runs" / run_id

    # Generate project map if goal contract specifies a project_dir
    gc_path = run_dir / "goal_contract.json"
    if gc_path.exists():
        gc = json.loads(gc_path.read_text(encoding="utf-8"))
        project_dir = gc.get("project_dir")
        if project_dir:
            print(f"=== Phase project_adapter ===")
            adapter_path = repo_root / ".agentic-pi" / "runtime" / "project_adapter.py"
            map_path = run_dir / "project_map.json"
            result = subprocess.run(
                [sys.executable, str(adapter_path), "--project-dir", str(repo_root / project_dir), "--output", str(map_path)],
                cwd=repo_root, capture_output=True, text=True
            )
            print(result.stdout)
            if result.returncode != 0:
                print(f"  Warning: project map generation failed: {result.stderr}")

    # Define phase scripts (relative to repo root)
    phases = [
        ("init_run", repo_root / ".agentic-pi" / "runtime" / "init_run.py"),
        ("artifact_linker", repo_root / ".agentic-pi" / "runtime" / "artifact_linker.py"),
        ("task_graph_builder", repo_root / ".agentic-pi" / "runtime" / "task_graph_builder.py"),
        ("harness_contract_verifier", repo_root / ".agentic-pi" / "formal" / "harness_contract_verifier.py"),
        ("harness_signing", repo_root / ".agentic-pi" / "formal" / "harness_signing.py"),
        ("certify_run", repo_root / ".agentic-pi" / "validators" / "certify_run.py"),
    ]

    for name, script in phases:
        if name == "init_run" and run_dir.is_dir():
            print(f"=== Phase {name} === (skipped — run dir exists)")
            continue
        try:
            run_phase(script, f"Phase {name}", ["--run-id", run_id] if name == "init_run" else [str(run_dir)] if name in ("harness_contract_verifier", "certify_run") else ["keygen", str(run_dir)] if name == "harness_signing" else [run_id])
        except RuntimeError as e:
            print(f"PIPELINE_FAILED: {e}")
            return 1

    print("Deterministic pipeline phases completed. Read certifier-owned status artifacts before reporting success.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
