#!/usr/bin/env python3
"""Resume mechanism for interrupted runs.

After a user clears context with /new, this module helps the agent
find and resume from where it left off.

The resume module:
1. Lists available runs
2. Shows which runs are incomplete
3. Provides resume instructions
4. Loads state from disk

It does NOT certify DONE. It does NOT write final_status.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = ROOT / ".agentic-runs"
STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}


class ResumeError(RuntimeError):
    """Raised when resume cannot continue safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        if default is not None:
            return default
        raise


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def list_runs() -> list[dict]:
    """List all available runs."""
    runs = []
    
    if not RUNS_ROOT.exists():
        return runs
    
    for run_dir in sorted(RUNS_ROOT.iterdir()):
        if not run_dir.is_dir():
            continue
        
        # Skip hidden directories
        if run_dir.name.startswith("."):
            continue
        
        # Load run state
        state_path = run_dir / "run_state.json"
        state = {}
        if state_path.exists():
            try:
                state = load_json(state_path)
            except Exception:
                pass
        
        # Load goal contract
        goal_path = run_dir / "goal_contract.json"
        goal = {}
        if goal_path.exists():
            try:
                goal = load_json(goal_path)
            except Exception:
                pass
        
        # Check if certified
        has_final_status = (run_dir / "final_status.json").exists()
        
        # Load step logs
        step_logs_dir = run_dir / "step_logs"
        step_count = 0
        if step_logs_dir.exists():
            step_count = len(list(step_logs_dir.glob("*.json")))
        
        runs.append({
            "run_id": run_dir.name,
            "current_phase": state.get("current_phase", "unknown"),
            "overall_status": state.get("overall_status", "unknown"),
            "goal": goal.get("raw_user_prompt", "unknown"),
            "has_final_status": has_final_status,
            "step_count": step_count,
            "created_at": state.get("created_at", "unknown"),
            "updated_at": state.get("updated_at", "unknown"),
        })
    
    return runs


def find_incomplete_runs() -> list[dict]:
    """Find runs that are not yet certified."""
    runs = list_runs()
    return [r for r in runs if not r["has_final_status"]]


def find_latest_run() -> dict | None:
    """Find the most recent run."""
    runs = list_runs()
    if not runs:
        return None
    
    # Sort by updated_at (most recent first)
    def parse_date(date_str: str) -> datetime:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)
    
    sorted_runs = sorted(runs, key=lambda r: parse_date(r["updated_at"]), reverse=True)
    return sorted_runs[0]


def get_resume_instructions(run: dict) -> dict:
    """Get instructions for resuming a run."""
    run_id = run["run_id"]
    current_phase = run["current_phase"]
    step_count = run["step_count"]
    
    # Determine what to do next
    if current_phase == "NEW":
        next_action = "Start the run from the beginning"
        command = f"python .agentic-pi/runtime/run_goal.py --run-id {run_id} --command \"{run['goal']}\""
    elif current_phase in ["INTAKE", "QUESTIONING", "RESEARCHING", "DESIGNING", "STRUCTURING", "PLANNING"]:
        next_action = f"Continue from {current_phase} phase"
        command = f"python .agentic-pi/runtime/run_goal.py --run-id {run_id} --command \"{run['goal']}\""
    elif current_phase in ["IMPLEMENTING", "VALIDATOR_BUILDING", "VALIDATING"]:
        next_action = f"Continue from {current_phase} phase (step {step_count} completed)"
        command = f"python .agentic-pi/runtime/run_goal.py --run-id {run_id} --command \"{run['goal']}\""
    elif current_phase in ["CERTIFYING", "REPORTING", "MEMORY_CONSOLIDATING"]:
        next_action = f"Continue from {current_phase} phase"
        command = f"python .agentic-pi/runtime/run_goal.py --run-id {run_id} --command \"{run['goal']}\""
    else:
        next_action = "Check status and continue"
        command = f"python .agentic-pi/runtime/pi_cli.py goal-status {run_id}"
    
    return {
        "run_id": run_id,
        "current_phase": current_phase,
        "step_count": step_count,
        "next_action": next_action,
        "command": command,
        "goal": run["goal"],
    }


def run_resume(run_id: str | None = None) -> dict:
    """Run resume mechanism."""
    if run_id:
        # Resume specific run
        runs = list_runs()
        run = next((r for r in runs if r["run_id"] == run_id), None)
        if not run:
            return {"error": f"Run {run_id} not found"}
        return get_resume_instructions(run)
    else:
        # Find latest incomplete run
        incomplete = find_incomplete_runs()
        if not incomplete:
            return {"message": "No incomplete runs found", "runs": list_runs()}
        
        # Get the most recent incomplete run
        latest = incomplete[0]
        return get_resume_instructions(latest)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Resume mechanism for interrupted runs.")
    parser.add_argument("--run-id", help="Specific run ID to resume")
    parser.add_argument("--list", action="store_true", help="List all runs")
    parser.add_argument("--incomplete", action="store_true", help="List incomplete runs")
    args = parser.parse_args(argv)

    if args.list:
        runs = list_runs()
        print(f"Available runs ({len(runs)}):")
        for run in runs:
            status = "CERTIFIED" if run["has_final_status"] else "INCOMPLETE"
            print(f"  {run['run_id']}: {status} - {run['goal'][:50]}...")
        return 0
    
    if args.incomplete:
        incomplete = find_incomplete_runs()
        print(f"Incomplete runs ({len(incomplete)}):")
        for run in incomplete:
            print(f"  {run['run_id']}: {run['current_phase']} - {run['goal'][:50]}...")
        return 0
    
    # Run resume
    result = run_resume(args.run_id)
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return 1
    
    if "message" in result:
        print(result["message"])
        if "runs" in result:
            print(f"\nAvailable runs ({len(result['runs'])}):")
            for run in result["runs"]:
                status = "CERTIFIED" if run["has_final_status"] else "INCOMPLETE"
                print(f"  {run['run_id']}: {status}")
        return 0
    
    # Print resume instructions
    print(f"Resume run: {result['run_id']}")
    print(f"  Goal: {result['goal']}")
    print(f"  Current phase: {result['current_phase']}")
    print(f"  Steps completed: {result['step_count']}")
    print(f"  Next action: {result['next_action']}")
    print(f"\nCommand to resume:")
    print(f"  {result['command']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
