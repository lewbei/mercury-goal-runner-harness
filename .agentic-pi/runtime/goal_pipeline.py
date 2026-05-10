#!/usr/bin/env python3
"""Goal Pipeline – orchestrates the full v0.5 workflow for a run.

Steps:
1. Build plan graph (plan_graph_builder.py)
2. Build artifact registry (artifact_linker.py)
3. Build task graph (task_graph_builder.py)
4. Run evidence selector (evidence_selector.py)
5. Run branch selector (branch_selector.py)
6. Validate generated JSON files against their schemas.
7. Run certify_run (existing validator) to produce final status.

Usage:
    python .agentic-pi/runtime/goal_pipeline.py <run_id>
"""
import subprocess
import sys
from pathlib import Path

# Helper to run a command and abort on failure
def run_cmd(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        print(f"ERROR: {' '.join(cmd)} failed with exit {result.returncode}")
        print(result.stdout)
        sys.exit(result.returncode)
    return result.stdout


def main():
    if len(sys.argv) != 2:
        print("Usage: goal_pipeline.py <run_id>")
        sys.exit(2)
    run_id = sys.argv[1]
    run_dir = Path(".agentic-runs") / run_id
    if not run_dir.is_dir():
        print(f"Run directory {run_dir} does not exist")
        sys.exit(1)

    # 1. Plan graph
    print("[1/7] Building plan graph...")
    run_cmd([sys.executable, ".agentic-pi/runtime/plan_graph_builder.py", run_id], cwd=Path.cwd())

    # 2. Artifact registry
    print("[2/7] Building artifact registry...")
    run_cmd([sys.executable, ".agentic-pi/runtime/artifact_linker.py", run_id], cwd=Path.cwd())

    # 3. Task graph
    print("[3/7] Building task graph...")
    run_cmd([sys.executable, ".agentic-pi/runtime/task_graph_builder.py", run_id], cwd=Path.cwd())

    # 4. Evidence selector
    print("[4/7] Running evidence selector...")
    run_cmd([sys.executable, ".agentic-pi/runtime/evidence_selector.py", run_id], cwd=Path.cwd())

    # 5. Branch selector
    print("[5/7] Selecting best branch...")
    run_cmd([sys.executable, ".agentic-pi/runtime/branch_selector.py", run_id], cwd=Path.cwd())

    # 6. Schema validation (using validate_schema.py)
    print("[6/7] Validating generated JSON files against schemas...")
    schemas_dir = Path(".agentic-pi/schemas")
    validator = Path(".agentic-pi/validators/validate_schema.py")
    # Map of file -> schema
    files_to_validate = {
        "plan_graph.json": "plan_graph.schema.json",
        "artifact_registry.json": "artifact.schema.json",
        "task_graph.json": "task_graph.schema.json",
        "evidence_report.json": "evidence.schema.json",
        "selected_branch.json": "branch.schema.json",
    }
    for fname, sname in files_to_validate.items():
        fpath = run_dir / fname
        spath = schemas_dir / sname
        if fpath.is_file() and spath.is_file():
            out = run_cmd([sys.executable, str(validator), str(spath), str(fpath)], cwd=Path.cwd())
            print(out.strip())
        else:
            print(f"Skipping validation for {fname} (missing file or schema)")

    # 7. Certification
    print("[7/7] Running certification...")
    run_cmd([sys.executable, ".agentic-pi/validators/certify_run.py", str(run_dir)], cwd=Path.cwd())
    print("Pipeline completed successfully.")

if __name__ == "__main__":
    main()
