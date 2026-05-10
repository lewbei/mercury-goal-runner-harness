#!/usr/bin/env python3
"""Merge selected plan(s) into a single execution plan.

Usage:
    python .agentic-pi/runtime/plan_merger.py --run-id <run_id>
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Merge selected plan(s) for a run")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument("--skill-context", default=None, help="Path to skill_context.json (QRSPI skills)")
    args = parser.parse_args()
    run_dir = Path(".agentic-runs") / args.run_id
    selected_path = run_dir / "selected_plan.json"
    if not selected_path.is_file():
        raise FileNotFoundError(f"selected_plan.json not found at {selected_path}")
    with open(selected_path, "r", encoding="utf-8") as f:
        selected = json.load(f)
    # For now, just copy the selected plan to merged_plan.json.
    # Future implementation could combine multiple plans, deduplicate steps, etc.
    merged_path = run_dir / "merged_plan.json"
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(selected, f, indent=2)
    print(f"Merged plan written to {merged_path}")

if __name__ == "__main__":
    main()
