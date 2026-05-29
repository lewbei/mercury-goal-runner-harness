#!/usr/bin/env python3
"""Verification checkpoint for planning phase.

Runs verifier during planning (not just at end) and produces feedback
that can be used for replanning. This implements verification-driven
adaptive replanning from the VMAO framework.

The checkpoint:
1. Runs lightweight verification on current plan artifacts
2. Produces verification_feedback.json with gaps/issues
3. Returns feedback for replanning loop

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
VALIDATORS = ROOT / ".agentic-pi" / "validators"
STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}


class VerificationCheckpointError(RuntimeError):
    """Raised when verification checkpoint cannot continue safely."""


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
    raise VerificationCheckpointError("Provide --run-dir or --run-id with an existing run folder.")


def check_goal_contract(run_dir: Path) -> dict:
    """Check if goal_contract.json exists and is valid."""
    goal_path = run_dir / "goal_contract.json"
    if not goal_path.exists():
        return {"check": "goal_contract", "passed": False, "issue": "goal_contract.json missing"}
    
    try:
        goal = load_json(goal_path)
        required = ["run_id", "goal_type", "raw_user_prompt", "execution_prompt"]
        missing = [f for f in required if f not in goal]
        if missing:
            return {"check": "goal_contract", "passed": False, "issue": f"missing fields: {missing}"}
        return {"check": "goal_contract", "passed": True, "issue": None}
    except Exception as e:
        return {"check": "goal_contract", "passed": False, "issue": str(e)}


def check_plan_graph(run_dir: Path) -> dict:
    """Check if plan_graph.json exists and has valid structure."""
    graph_path = run_dir / "plan_graph.json"
    if not graph_path.exists():
        return {"check": "plan_graph", "passed": False, "issue": "plan_graph.json missing"}
    
    try:
        graph = load_json(graph_path)
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        
        if not nodes:
            return {"check": "plan_graph", "passed": False, "issue": "no nodes in plan graph"}
        
        # Check for task nodes
        task_nodes = [n for n in nodes if n.get("type") == "task"]
        if not task_nodes:
            return {"check": "plan_graph", "passed": False, "issue": "no task nodes in plan graph"}
        
        # Check for cycles (simple check)
        node_ids = {n["node_id"] for n in nodes}
        for edge in edges:
            if edge["source"] not in node_ids:
                return {"check": "plan_graph", "passed": False, "issue": f"edge source {edge['source']} not in nodes"}
            if edge["target"] not in node_ids:
                return {"check": "plan_graph", "passed": False, "issue": f"edge target {edge['target']} not in nodes"}
        
        return {"check": "plan_graph", "passed": True, "issue": None, "task_count": len(task_nodes)}
    except Exception as e:
        return {"check": "plan_graph", "passed": False, "issue": str(e)}


def check_step_logs(run_dir: Path) -> dict:
    """Check if step logs exist and are valid."""
    step_logs_dir = run_dir / "step_logs"
    if not step_logs_dir.exists():
        return {"check": "step_logs", "passed": False, "issue": "step_logs directory missing"}
    
    step_logs = list(step_logs_dir.glob("*.json"))
    if not step_logs:
        return {"check": "step_logs", "passed": False, "issue": "no step logs found"}
    
    # Check first step log
    try:
        first_log = load_json(step_logs[0])
        required = ["run_id", "step_id", "status", "action_taken"]
        missing = [f for f in required if f not in first_log]
        if missing:
            return {"check": "step_logs", "passed": False, "issue": f"first step log missing fields: {missing}"}
        return {"check": "step_logs", "passed": True, "issue": None, "step_count": len(step_logs)}
    except Exception as e:
        return {"check": "step_logs", "passed": False, "issue": str(e)}


def check_expected_artifacts(run_dir: Path) -> dict:
    """Check if expected_artifacts.json exists and is valid."""
    artifacts_path = run_dir / "expected_artifacts.json"
    if not artifacts_path.exists():
        return {"check": "expected_artifacts", "passed": False, "issue": "expected_artifacts.json missing"}
    
    try:
        artifacts = load_json(artifacts_path)
        if not isinstance(artifacts, dict):
            return {"check": "expected_artifacts", "passed": False, "issue": "expected_artifacts.json is not a dict"}
        return {"check": "expected_artifacts", "passed": True, "issue": None}
    except Exception as e:
        return {"check": "expected_artifacts", "passed": False, "issue": str(e)}


def check_output_files(run_dir: Path, goal: dict) -> dict:
    """Check if expected output files exist."""
    final_outputs = goal.get("final_outputs", [])
    if not final_outputs:
        return {"check": "output_files", "passed": True, "issue": None, "note": "no final_outputs specified"}
    
    missing = []
    for output in final_outputs:
        output_path = run_dir / output
        if not output_path.exists():
            missing.append(output)
    
    if missing:
        return {"check": "output_files", "passed": False, "issue": f"missing output files: {missing}"}
    return {"check": "output_files", "passed": True, "issue": None}


def run_verification_checkpoint(run_dir: Path) -> dict:
    """Run all verification checks and produce feedback."""
    checks = []
    
    # Load goal contract
    goal_path = run_dir / "goal_contract.json"
    goal = {}
    if goal_path.exists():
        try:
            goal = load_json(goal_path)
        except Exception:
            pass
    
    # Run checks
    checks.append(check_goal_contract(run_dir))
    checks.append(check_plan_graph(run_dir))
    checks.append(check_step_logs(run_dir))
    checks.append(check_expected_artifacts(run_dir))
    checks.append(check_output_files(run_dir, goal))
    
    # Calculate summary
    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    issues = [c for c in checks if not c["passed"]]
    
    feedback = {
        "timestamp": utc_now(),
        "run_id": goal.get("run_id", "unknown"),
        "checks_passed": passed,
        "checks_total": total,
        "checks": checks,
        "issues": issues,
        "has_gaps": len(issues) > 0,
        "gap_summary": [i["issue"] for i in issues],
    }
    
    return feedback


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verification checkpoint for planning phase.")
    parser.add_argument("--run-dir", help="Path to the run directory")
    parser.add_argument("--run-id", help="Run identifier (resolved under .agentic-runs/)")
    parser.add_argument("--output", help="Output path for feedback JSON (default: run_dir/verification_feedback.json)")
    args = parser.parse_args(argv)

    try:
        run_dir = resolve_run_dir(args.run_dir, args.run_id)
    except VerificationCheckpointError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Run verification
    feedback = run_verification_checkpoint(run_dir)
    
    # Write feedback
    output_path = Path(args.output) if args.output else run_dir / "verification_feedback.json"
    write_json(output_path, feedback)
    
    # Print summary
    print(f"Verification checkpoint: {feedback['checks_passed']}/{feedback['checks_total']} passed")
    if feedback["has_gaps"]:
        print(f"Gaps found: {len(feedback['issues'])}")
        for issue in feedback["issues"]:
            print(f"  - {issue['check']}: {issue['issue']}")
    else:
        print("No gaps found.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
