#!/usr/bin/env python3
"""Step-level verification and replanning.

After each step in the implementation phase, this module:
1. Verifies the step output (file exists, syntax valid, etc.)
2. Logs verification result
3. Checks if plan needs adjustment
4. If replanning needed, suggests plan updates

This enables adaptive implementation where the plan can be
adjusted based on what was actually produced.

It does NOT certify DONE. It does NOT write final_status.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = ROOT / ".agentic-runs"
STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}


class StepVerifierError(RuntimeError):
    """Raised when step verification cannot continue safely."""


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
    raise StepVerifierError("Provide --run-dir or --run-id with an existing run folder.")


def verify_file_exists(file_path: Path) -> dict:
    """Verify that a file exists."""
    if file_path.exists():
        return {"check": "file_exists", "passed": True, "issue": None}
    return {"check": "file_exists", "passed": False, "issue": f"File not found: {file_path}"}


def verify_python_syntax(file_path: Path) -> dict:
    """Verify that a Python file has valid syntax."""
    if not file_path.exists():
        return {"check": "python_syntax", "passed": False, "issue": "File not found"}
    
    if file_path.suffix != ".py":
        return {"check": "python_syntax", "passed": True, "issue": None, "note": "Not a Python file"}
    
    try:
        source = file_path.read_text(encoding="utf-8")
        ast.parse(source)
        return {"check": "python_syntax", "passed": True, "issue": None}
    except SyntaxError as e:
        return {"check": "python_syntax", "passed": False, "issue": f"Syntax error: {e}"}


def verify_json_valid(file_path: Path) -> dict:
    """Verify that a JSON file is valid."""
    if not file_path.exists():
        return {"check": "json_valid", "passed": False, "issue": "File not found"}
    
    if file_path.suffix != ".json":
        return {"check": "json_valid", "passed": True, "issue": None, "note": "Not a JSON file"}
    
    try:
        json.loads(file_path.read_text(encoding="utf-8-sig"))
        return {"check": "json_valid", "passed": True, "issue": None}
    except json.JSONDecodeError as e:
        return {"check": "json_valid", "passed": False, "issue": f"JSON error: {e}"}


def verify_step_output(run_dir: Path, step: dict) -> dict:
    """Verify the output of a single step."""
    checks = []
    
    # Get the file path from the step
    file_path = step.get("path")
    if file_path:
        full_path = run_dir / file_path
        checks.append(verify_file_exists(full_path))
        
        # Check syntax based on file type
        if file_path.endswith(".py"):
            checks.append(verify_python_syntax(full_path))
        elif file_path.endswith(".json"):
            checks.append(verify_json_valid(full_path))
    
    # Calculate summary
    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    issues = [c for c in checks if not c["passed"]]
    
    return {
        "step_id": step.get("step_id"),
        "checks_passed": passed,
        "checks_total": total,
        "checks": checks,
        "issues": issues,
        "has_issues": len(issues) > 0,
    }


def generate_step_suggestions(verification: dict, step: dict) -> list[dict]:
    """Generate suggestions for fixing step issues."""
    suggestions = []
    
    for issue in verification.get("issues", []):
        check = issue.get("check", "")
        issue_text = issue.get("issue", "")
        
        if check == "file_exists":
            suggestions.append({
                "action": "create_file",
                "priority": "HIGH",
                "reason": f"File missing: {issue_text}",
                "suggestion": f"Create the file at {step.get('path', 'unknown')}",
            })
        
        elif check == "python_syntax":
            suggestions.append({
                "action": "fix_syntax",
                "priority": "HIGH",
                "reason": f"Syntax error: {issue_text}",
                "suggestion": "Fix the Python syntax error",
            })
        
        elif check == "json_valid":
            suggestions.append({
                "action": "fix_json",
                "priority": "HIGH",
                "reason": f"JSON error: {issue_text}",
                "suggestion": "Fix the JSON syntax error",
            })
    
    return suggestions


def run_step_verification(run_dir: Path, step_id: int) -> dict:
    """Run verification for a single step."""
    # Load merged_plan.json
    plan_path = run_dir / "merged_plan.json"
    if not plan_path.exists():
        return {
            "step_id": step_id,
            "error": "merged_plan.json not found",
            "verification": None,
            "suggestions": [],
        }
    
    plan = load_json(plan_path)
    steps = plan.get("steps", [])
    
    # Find the step
    step = None
    for s in steps:
        if s.get("step_id") == step_id:
            step = s
            break
    
    if step is None:
        return {
            "step_id": step_id,
            "error": f"Step {step_id} not found in merged_plan.json",
            "verification": None,
            "suggestions": [],
        }
    
    # Verify the step
    verification = verify_step_output(run_dir, step)
    
    # Generate suggestions
    suggestions = generate_step_suggestions(verification, step)
    
    return {
        "step_id": step_id,
        "timestamp": utc_now(),
        "verification": verification,
        "suggestions": suggestions,
        "needs_replanning": len(suggestions) > 0,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Step-level verification and replanning.")
    parser.add_argument("--run-dir", help="Path to the run directory")
    parser.add_argument("--run-id", help="Run identifier (resolved under .agentic-runs/)")
    parser.add_argument("--step-id", type=int, required=True, help="Step ID to verify")
    parser.add_argument("--output", help="Output path for verification JSON")
    args = parser.parse_args(argv)

    try:
        run_dir = resolve_run_dir(args.run_dir, args.run_id)
    except StepVerifierError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Run verification
    result = run_step_verification(run_dir, args.step_id)
    
    # Write verification result
    output_path = Path(args.output) if args.output else run_dir / f"step_verification_{args.step_id}.json"
    write_json(output_path, result)
    
    # Print summary
    if result.get("error"):
        print(f"Error: {result['error']}")
        return 1
    
    verification = result["verification"]
    print(f"Step {args.step_id} verification: {verification['checks_passed']}/{verification['checks_total']} passed")
    
    if result["needs_replanning"]:
        print(f"Replanning needed:")
        for suggestion in result["suggestions"]:
            print(f"  [{suggestion['priority']}] {suggestion['action']}: {suggestion['suggestion']}")
    else:
        print("No replanning needed.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
