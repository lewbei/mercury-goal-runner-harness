#!/usr/bin/env python3
"""Record deterministic milestone_status.json without certifying DONE."""
import argparse
import json
import sys
from pathlib import Path


ALLOWED_STATUSES = ["planned", "active", "complete", "blocked"]


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def track_milestones(run_dir: Path) -> dict:
    plan = load_json(run_dir / "milestone_plan.json")
    statuses = []
    for milestone in plan.get("milestones", []):
        statuses.append({
            "order": milestone["order"],
            "milestone_id": milestone["milestone_id"],
            "status": "planned",
            "status_reason": "Milestone is planned; execution and certification have not changed this status.",
        })

    output = {
        "run_id": plan["run_id"],
        "generated_by": "milestone-tracker-v1.4",
        "selected_strategy": plan["selected_strategy"],
        "task_type": plan["task_type"],
        "allowed_statuses": ALLOWED_STATUSES,
        "final_status_authority": "certifier_only",
        "milestone_statuses": statuses,
    }
    write_json(run_dir / "milestone_status.json", output)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Record deterministic milestone statuses.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        output = track_milestones(Path(args.run_dir))
    except Exception as exc:
        print(f"MILESTONE_TRACK_FAILED: {exc}")
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
