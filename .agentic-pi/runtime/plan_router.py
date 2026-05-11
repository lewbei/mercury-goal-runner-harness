#!/usr/bin/env python3
"""Strict plan router.

This runtime does not synthesize plans from goal complexity. Plans must be
produced by planner agents or deterministic proof runners before this router is
called. The router only confirms that a goal contract exists and that at least
one planner-owned plan file already exists.
"""

import argparse
import json
import sys
from pathlib import Path


def load_contract(run_dir: Path) -> dict:
    contract_path = run_dir / "goal_contract.json"
    if not contract_path.is_file():
        raise FileNotFoundError(f"Goal contract not found at {contract_path}")
    with contract_path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def existing_plan_files(run_dir: Path) -> list[Path]:
    plans_dir = run_dir / "plans"
    if not plans_dir.is_dir():
        return []
    return sorted(path for path in plans_dir.glob("*_plan.json") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that planner-generated plan files already exist."
    )
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument(
        "--skill-context",
        default=None,
        help="Accepted for pipeline compatibility; this strict router does not read it.",
    )
    args = parser.parse_args()

    run_dir = Path(".agentic-runs") / args.run_id
    contract = load_contract(run_dir)
    plan_files = existing_plan_files(run_dir)

    if not plan_files:
        print("STRICT_PLAN_ROUTER_REQUIRES_EXISTING_PLAN")
        print(f"Run: {args.run_id}")
        print(f"Goal type: {contract.get('goal_type', contract.get('complexity_level', 'unknown'))}")
        print("Expected planner output: .agentic-runs/<run_id>/plans/*_plan.json")
        print("No generated compatibility plan was created.")
        return 1

    print(f"Found {len(plan_files)} existing planner plan file(s):")
    for path in plan_files:
        print(f"- {path.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
