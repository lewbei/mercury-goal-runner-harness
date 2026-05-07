#!/usr/bin/env python3
"""Create safe delta_plan.json for repairable drift only."""
import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def create_delta_plan(run_dir: Path) -> dict:
    drift = load_json(run_dir / "drift_report.json")
    monitor = load_json(run_dir / "plan_monitor_report.json")
    level = drift.get("drift_level")

    if level in {"none", "minor"}:
        decision_status = "NO_DELTA_NEEDED"
        steps = []
        reason = "No repairable drift was detected."
    elif level == "repairable":
        decision_status = "DELTA_PLAN_CREATED"
        steps = []
        seen = set()
        for target in monitor.get("repair_targets", []):
            path = target.get("path", "")
            if path in seen:
                continue
            seen.add(path)
            steps.append({
                "delta_step_id": f"DS{len(steps) + 1:03d}",
                "task_id": f"TD.REPAIR.{len(steps) + 1:03d}",
                "action": target.get("action", "create_file"),
                "path": path,
                "content": target.get("content", ""),
                "produces": target.get("produces", []),
            })
        reason = "Repairable drift detected; delta steps recreate expected merged-plan artifacts."
    else:
        decision_status = "ABORT_REQUIRES_USER"
        steps = []
        reason = "Fatal drift detected; local replanning is not allowed."

    delta_plan = {
        "run_id": drift.get("run_id", run_dir.name),
        "generated_by": "replan-controller-v1.5",
        "decision_status": decision_status,
        "drift_level": level,
        "reason": reason,
        "final_status_authority": "certifier_only",
        "delta_steps": steps,
    }
    write_json(run_dir / "delta_plan.json", delta_plan)
    return delta_plan


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create delta_plan.json for repairable drift.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        delta_plan = create_delta_plan(Path(args.run_dir))
    except Exception as exc:
        print(f"REPLAN_CONTROL_FAILED: {exc}")
        return 1
    print(json.dumps(delta_plan, indent=2, ensure_ascii=False))
    return 0 if delta_plan["decision_status"] != "ABORT_REQUIRES_USER" else 1


if __name__ == "__main__":
    sys.exit(main())
