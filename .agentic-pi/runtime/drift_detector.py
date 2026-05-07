#!/usr/bin/env python3
"""Turn plan_monitor_report.json into drift_report.json."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def decide_drift_level(monitor: dict) -> str:
    if monitor.get("fatal_violations"):
        return "fatal"
    if monitor.get("repairable_violations"):
        return "repairable"
    if monitor.get("minor_notes"):
        return "minor"
    return "none"


def recommended_action(level: str) -> str:
    if level == "none":
        return "continue"
    if level == "minor":
        return "continue_with_note"
    if level == "repairable":
        return "generate_delta_plan"
    return "abort_requires_user"


def detect_drift(run_dir: Path) -> dict:
    monitor = load_json(run_dir / "plan_monitor_report.json")
    level = decide_drift_level(monitor)
    violations = []
    for key in ["fatal_violations", "repairable_violations", "minor_notes"]:
        violations.extend(monitor.get(key, []))

    report = {
        "run_id": monitor.get("run_id", run_dir.name),
        "generated_by": "drift-detector-v1.5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "valid": True,
        "drift_level": level,
        "blocking": level in {"repairable", "fatal"},
        "recommended_action": recommended_action(level),
        "violations": violations,
    }
    write_json(run_dir / "drift_report.json", report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Detect drift from plan monitor report.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        report = detect_drift(Path(args.run_dir))
    except Exception as exc:
        print(f"DRIFT_DETECT_FAILED: {exc}")
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["drift_level"] != "fatal" else 1


if __name__ == "__main__":
    sys.exit(main())
