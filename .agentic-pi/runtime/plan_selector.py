#!/usr/bin/env python3
"""Select the best plan from generated planner outputs.

Usage:
    python .agentic-pi/runtime/plan_selector.py --run-id <run_id>
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Select best plan for a run")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument("--skill-context", default=None, help="Path to skill_context.json (QRSPI skills)")
    args = parser.parse_args()
    run_dir = Path(".agentic-runs") / args.run_id
    plans_dir = run_dir / "plans"
    if not plans_dir.is_dir():
        raise FileNotFoundError(f"Plans directory not found at {plans_dir}")
    plan_files = list(plans_dir.glob("*.json"))
    if not plan_files:
        raise FileNotFoundError("No plan JSON files found in plans directory")
    best_plan = None
    best_score = None
    for pf in plan_files:
        with open(pf, "r", encoding="utf-8") as f:
            plan = json.load(f)
        steps = plan.get("steps", [])
        score = len(steps)
        # Simple heuristic: fewer steps is better
        if best_score is None or score < best_score:
            best_score = score
            best_plan = plan
    if best_plan is None:
        raise RuntimeError("Failed to select a plan")
    selected_path = run_dir / "selected_plan.json"
    with open(selected_path, "w", encoding="utf-8") as f:
        json.dump(best_plan, f, indent=2)
    print(f"Selected plan written to {selected_path}")

if __name__ == "__main__":
    main()
