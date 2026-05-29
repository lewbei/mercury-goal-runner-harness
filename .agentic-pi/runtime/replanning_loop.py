#!/usr/bin/env python3
"""Replanning loop for verification-driven adaptive replanning.

Reads verification_feedback.json and adjusts the plan when gaps are found.
This implements the VMAO framework's adaptive replanning.

The replanning loop:
1. Reads verification_feedback.json
2. Identifies gaps/issues
3. Generates replanning suggestions
4. Writes replanning_suggestions.json
5. Returns whether replanning is needed

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


class ReplanningLoopError(RuntimeError):
    """Raised when replanning loop cannot continue safely."""


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


def resolve_run_dir(raw: str | None, run_id: str | None) -> Path:
    if raw:
        p = Path(raw)
        if p.is_dir():
            return p.resolve()
    if run_id:
        p = RUNS_ROOT / run_id
        if p.is_dir():
            return p.resolve()
    raise ReplanningLoopError("Provide --run-dir or --run-id with an existing run folder.")


def analyze_gaps(feedback: dict) -> list[dict]:
    """Analyze verification feedback and identify replanning needs."""
    suggestions = []
    
    for issue in feedback.get("issues", []):
        check = issue.get("check", "")
        issue_text = issue.get("issue", "")
        
        if check == "goal_contract":
            suggestions.append({
                "priority": "HIGH",
                "action": "fix_goal_contract",
                "reason": f"Goal contract issue: {issue_text}",
                "suggestion": "Review and fix goal_contract.json. Ensure all required fields are present.",
            })
        
        elif check == "plan_graph":
            suggestions.append({
                "priority": "HIGH",
                "action": "fix_plan_graph",
                "reason": f"Plan graph issue: {issue_text}",
                "suggestion": "Review plan_graph.json. Ensure nodes and edges are valid.",
            })
        
        elif check == "step_logs":
            suggestions.append({
                "priority": "MEDIUM",
                "action": "add_step_logs",
                "reason": f"Step logs issue: {issue_text}",
                "suggestion": "Add step logs to document what was done.",
            })
        
        elif check == "expected_artifacts":
            suggestions.append({
                "priority": "MEDIUM",
                "action": "add_expected_artifacts",
                "reason": f"Expected artifacts issue: {issue_text}",
                "suggestion": "Add expected_artifacts.json to document what artifacts are expected.",
            })
        
        elif check == "output_files":
            suggestions.append({
                "priority": "HIGH",
                "action": "create_output_files",
                "reason": f"Output files issue: {issue_text}",
                "suggestion": "Create the missing output files.",
            })
    
    return suggestions


def generate_replanning_plan(suggestions: list[dict], goal: dict) -> dict:
    """Generate a replanning plan from suggestions."""
    if not suggestions:
        return {
            "needs_replanning": False,
            "reason": "No gaps found",
            "actions": [],
        }
    
    # Sort by priority
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    sorted_suggestions = sorted(suggestions, key=lambda s: priority_order.get(s["priority"], 3))
    
    # Group by action
    actions = []
    for suggestion in sorted_suggestions:
        actions.append({
            "action": suggestion["action"],
            "priority": suggestion["priority"],
            "reason": suggestion["reason"],
            "suggestion": suggestion["suggestion"],
        })
    
    return {
        "needs_replanning": True,
        "reason": f"{len(actions)} gaps found",
        "actions": actions,
        "goal": goal.get("raw_user_prompt", "unknown"),
    }


def run_replanning_loop(run_dir: Path) -> dict:
    """Run the replanning loop."""
    # Load verification feedback
    feedback_path = run_dir / "verification_feedback.json"
    if not feedback_path.exists():
        return {
            "needs_replanning": False,
            "reason": "No verification feedback found",
            "actions": [],
        }
    
    feedback = load_json(feedback_path)
    
    # Load goal contract
    goal_path = run_dir / "goal_contract.json"
    goal = {}
    if goal_path.exists():
        try:
            goal = load_json(goal_path)
        except Exception:
            pass
    
    # Analyze gaps
    suggestions = analyze_gaps(feedback)
    
    # Generate replanning plan
    replanning_plan = generate_replanning_plan(suggestions, goal)
    replanning_plan["timestamp"] = utc_now()
    replanning_plan["run_id"] = goal.get("run_id", "unknown")
    
    return replanning_plan


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Replanning loop for verification-driven adaptive replanning.")
    parser.add_argument("--run-dir", help="Path to the run directory")
    parser.add_argument("--run-id", help="Run identifier (resolved under .agentic-runs/)")
    parser.add_argument("--output", help="Output path for replanning JSON (default: run_dir/replanning_suggestions.json)")
    args = parser.parse_args(argv)

    try:
        run_dir = resolve_run_dir(args.run_dir, args.run_id)
    except ReplanningLoopError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Run replanning loop
    replanning_plan = run_replanning_loop(run_dir)
    
    # Write replanning suggestions
    output_path = Path(args.output) if args.output else run_dir / "replanning_suggestions.json"
    write_json(output_path, replanning_plan)
    
    # Print summary
    if replanning_plan["needs_replanning"]:
        print(f"Replanning needed: {replanning_plan['reason']}")
        for action in replanning_plan["actions"]:
            print(f"  [{action['priority']}] {action['action']}: {action['suggestion']}")
    else:
        print(f"No replanning needed: {replanning_plan['reason']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
