#!/usr/bin/env python3
"""Strictly merge the selected planner output into merged_plan.json.

The selected plan must already contain executable steps. This merger refuses
all generated compatibility plan shapes and never invents missing steps.

Usage:
    python .agentic-pi/runtime/plan_merger.py --run-id <run_id>
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


#@ Requires(lambda path: isinstance(path, Path) and path.is_file(), "selected_plan.json must exist")
#@ Ensures(lambda result: isinstance(result, dict), "selected_plan must be a dict")
def load_json(path: Path) -> Dict[str, Any]:
    """Load a JSON file and return its content as a dict."""
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_step(step: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Validate one executable step and return a shallow normalized copy."""
    if not isinstance(step, dict):
        raise ValueError(f"steps[{index}] must be an object")

    task_id = step.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError(f"steps[{index}] missing task_id")

    action = step.get("action")
    if action != "create_file":
        raise ValueError(
            f"steps[{index}] has unsupported action {action!r}; strict runtime currently supports create_file"
        )

    path = step.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"steps[{index}] create_file action requires path")

    requires = step.get("requires", [])
    if not isinstance(requires, list) or not all(isinstance(item, str) and item.strip() for item in requires):
        raise ValueError(f"steps[{index}] requires must be a list of non-empty artifact IDs")

    produces = step.get("produces", [])
    if produces:
        if not isinstance(produces, list):
            raise ValueError(f"steps[{index}] produces must be a list")
        for artifact_index, artifact in enumerate(produces, start=1):
            if not isinstance(artifact, dict):
                raise ValueError(f"steps[{index}] produces[{artifact_index}] must be an object")
            artifact_id = artifact.get("artifact_id")
            artifact_path = artifact.get("path")
            if not isinstance(artifact_id, str) or not artifact_id.strip():
                raise ValueError(f"steps[{index}] produces[{artifact_index}] missing artifact_id")
            if not isinstance(artifact_path, str) or not artifact_path.strip():
                raise ValueError(f"steps[{index}] produces[{artifact_index}] missing path")

    normalized = dict(step)
    normalized["task_id"] = task_id.strip()
    normalized["action"] = action
    normalized["path"] = path.strip()
    normalized["requires"] = requires
    if produces:
        normalized["produces"] = produces
    return normalized


def build_merged_plan(selected_plan: Dict[str, Any]) -> Dict[str, Any]:
    """Build merged_plan.json from the selected planner output."""
    steps = selected_plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("selected_plan.json must contain a non-empty steps list")

    merged_steps: List[Dict[str, Any]] = [
        validate_step(step, index)
        for index, step in enumerate(steps, start=1)
    ]
    metadata = {
        key: value
        for key, value in selected_plan.items()
        if key != "steps"
    }
    return {
        "schema_version": "merged_plan_v1",
        "source": "selected_plan.json",
        "steps": merged_steps,
        "selected_plan_metadata": metadata,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Strictly merge selected planner output for a run")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument("--skill-context", default=None, help="Path to skill_context.json (QRSPI skills)")
    args = parser.parse_args()

    run_dir = Path(".agentic-runs") / args.run_id
    selected_path = run_dir / "selected_plan.json"
    if not selected_path.is_file():
        raise FileNotFoundError(f"selected_plan.json missing at {selected_path}")

    merged = build_merged_plan(load_json(selected_path))
    merged_path = run_dir / "merged_plan.json"
    with merged_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    print(f"Merged plan written to {merged_path}")
    print(f"Merged plan contains {len(merged['steps'])} executable step(s).")


if __name__ == "__main__":
    main()
