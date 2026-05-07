#!/usr/bin/env python3
"""Deterministically route a goal contract to a task type."""
import argparse
import json
import sys
from pathlib import Path


TASK_PRIORITY = ["debugging", "coding", "benchmark", "experiment", "research", "writing", "unknown"]
TASK_KEYWORDS = {
    "debugging": ["fix", "bug", "error", "failing", "failure", "traceback", "repair"],
    "coding": ["cli", "script", "code", "python", "csv", "json validator", ".py"],
    "benchmark": ["benchmark", "diagnostic", "false pass", "false-pass", "metric"],
    "experiment": ["experiment", "ablation", "seed", "protocol"],
    "research": ["paper", "source", "novelty", "literature", "citation", "claim"],
    "writing": ["readme", "write", "document", "doc", "markdown", ".md"],
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def combined_goal_text(goal: dict) -> str:
    parts = []
    for key in ["raw_user_prompt", "intent", "cleaned_goal", "execution_prompt"]:
        value = goal.get(key)
        if isinstance(value, str):
            parts.append(value)
    for output in goal.get("final_outputs", []):
        if isinstance(output, str):
            parts.append(output)
    for criterion in goal.get("done_criteria", []):
        if isinstance(criterion, str):
            parts.append(criterion)
    return " ".join(parts).lower()


def route_task_type(goal: dict) -> dict:
    text = combined_goal_text(goal)
    matched = {task: [] for task in TASK_KEYWORDS}
    for task, keywords in TASK_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                matched[task].append(keyword)

    selected = "unknown"
    for task in TASK_PRIORITY:
        if task != "unknown" and matched.get(task):
            selected = task
            break

    return {
        "run_id": goal.get("run_id", ""),
        "task_type": selected,
        "confidence": "deterministic",
        "matched_signals": [f"{selected}:{item}" for item in matched.get(selected, [])],
        "notes": [
            "Task type is selected by deterministic keyword and output-path rules.",
            "This is not model confidence.",
        ],
    }


def route_run(run_dir: Path) -> dict:
    goal_path = run_dir / "goal_contract.json"
    if not goal_path.is_file():
        raise FileNotFoundError(f"goal_contract.json missing: {goal_path}")
    decision = route_task_type(load_json(goal_path))
    write_json(run_dir / "task_type_decision.json", decision)
    return decision


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Route a run to a deterministic task type.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        decision = route_run(Path(args.run_dir))
    except Exception as exc:
        print(f"TASK_TYPE_ROUTING_FAILED: {exc}")
        return 1
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
