#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent

def run_subprocess(cmd, cwd=None):
    """Run a command via subprocess, raise on error, return output."""
    result = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command {' '.join(cmd)} failed with exit {result.returncode}: {result.stdout}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description="Run a goal based on its contract")
    parser.add_argument("command", help="Command describing the goal")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument(
        "--skip-memory-update",
        action="store_true",
        help="Do not update memory files after the run",
    )
    args = parser.parse_args()
    run_dir = Path(".agentic-runs") / args.run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run folder {run_dir} does not exist")
    contract_path = run_dir / "goal_contract.json"
    if not contract_path.is_file():
        raise FileNotFoundError(f"Goal contract not found at {contract_path}")
    with contract_path.open(encoding='utf-8-sig') as f:
        contract = json.load(f)
    # Log start of run
    print(f"Running goal for run {args.run_id}: {args.command}")

    # 1. Generate plans (router)
    print("Running plan_router...")
    run_subprocess(["python", ".agentic-pi/runtime/plan_router.py", "--run-id", args.run_id])

    # 2. Select best plan
    print("Running plan_selector...")
    run_subprocess(["python", ".agentic-pi/runtime/plan_selector.py", "--run-id", args.run_id])

    # 3. Merge selected plan
    print("Running plan_merger...")
    run_subprocess(["python", ".agentic-pi/runtime/plan_merger.py", "--run-id", args.run_id])

    # 4. Build the v0.3 PlanGraph from the merged plan before execution.
    print("Running plan_graph_builder...")
    run_subprocess(["python", ".agentic-pi/runtime/plan_graph_builder.py", args.run_id])

    # 5. Execute steps via Guarded Worker
    print("Running guarded_worker...")
    run_subprocess(["python", ".agentic-pi/runtime/guarded_worker.py", "--run-id", args.run_id])

    # 6. Build post-worker artifact and task graph views.
    print("Running artifact_linker...")
    run_subprocess(["python", ".agentic-pi/runtime/artifact_linker.py", args.run_id])

    print("Running task_graph_builder...")
    run_subprocess(["python", ".agentic-pi/runtime/task_graph_builder.py", args.run_id])

    # 7. Certify run
    print("Running certifier...")
    run_subprocess(["python", ".agentic-pi/validators/certify_run.py", str(run_dir)])

    print("Run completed.")
    if not args.skip_memory_update:
        print("Updating memory from runs...")
        run_subprocess(["python", ".agentic-pi/runtime/update_memory_from_runs.py"], cwd=BASE_DIR)

if __name__ == "__main__":
    main()
