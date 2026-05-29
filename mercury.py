#!/usr/bin/env python3
"""mercury — simple interface for the Mercury Goal Runner Harness.

Usage:
    mercury run "Build a todo app"
    mercury run "Create a REST API" --output api-server
    mercury status <run_id>
    mercury health

This is the only command an agent needs to know.
"""

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".agentic-pi" / "runtime"
RUNS_DIR = ROOT / ".agentic-runs"
OUTPUT_DIR = ROOT / "output"


def generate_run_id() -> str:
    """Generate a short, readable run ID."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:6]
    return f"run_{ts}_{short_id}"


def goal_to_contract(goal: str, run_id: str, output_dir: str = None) -> dict:
    """Convert a plain-text goal into a goal_contract.json."""
    # Infer app name from goal
    if output_dir:
        app_name = output_dir
    else:
        # Simple heuristic: use first few words
        words = goal.lower().split()[:3]
        app_name = "-".join(w for w in words if w.isalnum())
        if not app_name:
            app_name = "app"

    return {
        "run_id": run_id,
        "goal_type": "coding",
        "raw_user_prompt": goal,
        "execution_prompt": goal,
        "final_outputs": [],
        "done_criteria": [
            f"Output files exist in output/{app_name}/",
            "Code is syntactically valid",
        ],
        "constraints": [],
        "output_directory": f"output/{app_name}",
        "app_name": app_name,
    }


def cmd_run(args):
    """Run a goal through the harness."""
    run_id = args.run_id or generate_run_id()
    goal = args.goal
    output_dir = args.output

    print(f"Mercury Goal Runner Harness")
    print(f"{'=' * 50}")
    print(f"Goal:    {goal}")
    print(f"Run ID:  {run_id}")
    print()

    # 1. Init run
    print("[1/4] Initializing run...")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "step_logs").mkdir(exist_ok=True)

    # Write run_state.json
    run_state = {
        "run_id": run_id,
        "current_phase": "NEW",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "run_state.json").write_text(json.dumps(run_state, indent=2))

    # 2. Write goal contract
    print("[2/4] Writing goal contract...")
    contract = goal_to_contract(goal, run_id, output_dir)
    (run_dir / "goal_contract.json").write_text(json.dumps(contract, indent=2))

    # 3. Run pipeline
    print("[3/4] Running pipeline...")
    print()
    result = subprocess.run(
        [sys.executable, str(RUNTIME / "pi_cli.py"), "goal-run", run_id,
         "--command", goal],
        cwd=str(ROOT),
    )

    # 4. Check status
    print()
    print("[4/4] Checking status...")
    cert_path = run_dir / "final_status.json"
    if cert_path.exists():
        status = json.loads(cert_path.read_text(encoding="utf-8-sig"))
        print(f"Status:  {status.get('status', 'UNKNOWN')}")
        print(f"Source:  {cert_path}")
    else:
        print("Status:  UNKNOWN (no final_status.json)")

    # Show output location
    app_name = contract.get("app_name", "app")
    output_path = OUTPUT_DIR / app_name
    if output_path.exists():
        print(f"Output:  {output_path}/")
    else:
        print(f"Output:  {output_path}/ (not created yet)")

    return 0 if result.returncode == 0 else 1


def cmd_status(args):
    """Check status of a run."""
    run_id = args.run_id
    run_dir = RUNS_DIR / run_id

    if not run_dir.exists():
        print(f"Run not found: {run_id}")
        return 1

    cert_path = run_dir / "final_status.json"
    if cert_path.exists():
        status = json.loads(cert_path.read_text(encoding="utf-8-sig"))
        print(f"Run:     {run_id}")
        print(f"Status:  {status.get('status', 'UNKNOWN')}")
        print(f"Checks:  {status.get('checks_passed', 0)}/{status.get('checks_total', 0)}")
        print(f"Source:  {cert_path}")
    else:
        print(f"Run:     {run_id}")
        print(f"Status:  NOT_CERTIFIED (no final_status.json)")

    return 0


def cmd_health(args):
    """Run harness health check."""
    result = subprocess.run(
        [sys.executable, str(RUNTIME / "harness_health.py")],
        cwd=str(ROOT),
    )
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        prog="mercury",
        description="Mercury Goal Runner Harness — simple interface",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # run
    run_parser = subparsers.add_parser("run", help="Run a goal")
    run_parser.add_argument("goal", help="Goal description (plain text)")
    run_parser.add_argument("--run-id", default=None, help="Run identifier (auto-generated if not provided)")
    run_parser.add_argument("--output", default=None, help="Output directory name")

    # status
    status_parser = subparsers.add_parser("status", help="Check run status")
    status_parser.add_argument("run_id", help="Run identifier")

    # health
    subparsers.add_parser("health", help="Run harness health check")

    args = parser.parse_args()

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "health":
        return cmd_health(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
