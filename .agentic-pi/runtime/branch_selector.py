#!/usr/bin/env python3
"""Branch Selector – selects the best branch based on evidence report.

Usage:
    python .agentic-pi/runtime/branch_selector.py <run_id>
"""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print("Usage: branch_selector.py <run_id>")
        sys.exit(2)
    run_id = sys.argv[1]
    run_dir = Path(".agentic-runs") / run_id
    evidence_path = run_dir / "evidence_report.json"
    plan_path = run_dir / "plan_graph.json"
    if not evidence_path.is_file() or not plan_path.is_file():
        print("Missing evidence_report.json or plan_graph.json")
        sys.exit(1)
    evidence = json.load(evidence_path.open())
    plan = json.load(plan_path.open())
    # Simple scoring: count artifacts with evidence_obtained == True
    score = sum(1 for a in evidence.get("artifacts", []) if a.get("evidence_obtained"))
    branch = {
        "branch_id": "branch_1",
        "plan": plan,
        "evidence_score": score,
        "status": "selected",
        "reasons": []
    }
    out_path = run_dir / "selected_branch.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(branch, f, indent=2)
    print(f"Selected branch written to {out_path} with evidence_score {score}")

if __name__ == "__main__":
    main()
