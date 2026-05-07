#!/usr/bin/env python3
"""Extract advisory experience from a completed run folder.

Experience can suggest future strategy preferences. It cannot certify DONE.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


STATUS_SUCCESS = {"CERTIFIED_DONE", "DONE_PASS"}
STATUS_FAILURE = {"NOT_DONE", "DONE_FAIL", "BLOCKED", "NEED_USER", "NEED_USER_STRATEGY"}
STATUS_PROVISIONAL = {"PROVISIONAL_DONE"}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def first_existing_json(run_dir: Path, names: list[str]) -> tuple[str, dict]:
    for name in names:
        path = run_dir / name
        if path.is_file():
            return name, load_json(path)
    return "", {}


def task_type_for_run(run_dir: Path) -> str:
    path = run_dir / "task_type_decision.json"
    if path.is_file():
        return load_json(path).get("task_type", "unknown")
    goal = load_json(run_dir / "goal_contract.json") if (run_dir / "goal_contract.json").is_file() else {}
    return goal.get("task_type", "unknown")


def strategy_for_run(run_dir: Path) -> str:
    selected = run_dir / "selected_strategy.json"
    if selected.is_file():
        return load_json(selected).get("strategy_id", "")
    decision = run_dir / "strategy_decision.json"
    if decision.is_file():
        return load_json(decision).get("selected_strategy", "")
    return ""


def status_for_run(run_dir: Path) -> tuple[str, str]:
    source, doc = first_existing_json(
        run_dir,
        [
            "certification.json",
            "policy_decision.json",
            "strategy_proof.json",
            "drift_proof.json",
        ],
    )
    status = doc.get("status") or doc.get("final_status") or doc.get("decision_status") or ""
    return source, status


def outcome_kind(status: str) -> str:
    if status in STATUS_SUCCESS:
        return "success"
    if status in STATUS_PROVISIONAL:
        return "provisional"
    if status in STATUS_FAILURE:
        return "failure"
    return "unknown"


def collect_smell_flags(run_dir: Path) -> list[str]:
    flags = []
    smell_dir = run_dir / "verifier_smell_reports"
    if not smell_dir.is_dir():
        return flags
    for path in sorted(smell_dir.glob("*.json")):
        try:
            report = load_json(path)
        except Exception:
            continue
        for flag in report.get("smell_flags", []):
            if flag not in flags:
                flags.append(flag)
    return flags


def drift_causes(run_dir: Path) -> list[str]:
    path = run_dir / "drift_report.json"
    if not path.is_file():
        return []
    try:
        report = load_json(path)
    except Exception:
        return ["drift_report.json unreadable"]
    return report.get("violations", [])


def trajectory_issues(run_dir: Path) -> list[str]:
    path = run_dir / "trajectory_score.json"
    if not path.is_file():
        return []
    try:
        report = load_json(path)
    except Exception:
        return ["trajectory_score.json unreadable"]
    issues = []
    for case in report.get("cases", []):
        issues.extend(case.get("violations", []))
    return issues


def principle_for(task_type: str, strategy_id: str, status: str, kind: str) -> str:
    strategy_text = strategy_id or "selected strategy"
    if kind == "success":
        return f"For {task_type} tasks, {strategy_text} worked when certifier status was {status}."
    if kind == "provisional":
        return f"For {task_type} tasks, {strategy_text} needs stronger verifier evidence before certification."
    if kind == "failure":
        return f"For {task_type} tasks, avoid relying on {strategy_text} until the recorded failure cause is fixed."
    return f"For {task_type} tasks, {strategy_text} produced an unknown outcome and should be treated cautiously."


def do_not_use_when(kind: str, status: str, weak_flags: list[str], drift: list[str], trajectory: list[str]) -> list[str]:
    conditions = []
    if kind == "success":
        conditions.append("task signals differ from source run")
    if kind == "provisional":
        conditions.append("required verifier authority is missing or weak")
    if kind == "failure":
        conditions.append(f"prior outcome status was {status}")
    conditions.extend(weak_flags)
    conditions.extend(drift)
    conditions.extend(trajectory)
    return conditions


def extract_experience(run_dir: Path) -> dict:
    run_id = run_dir.name
    task_type = task_type_for_run(run_dir)
    strategy_id = strategy_for_run(run_dir)
    status_source, status = status_for_run(run_dir)
    kind = outcome_kind(status)
    weak_flags = collect_smell_flags(run_dir)
    drift = drift_causes(run_dir)
    trajectory = trajectory_issues(run_dir)
    evidence_files = [
        name
        for name in [
            "goal_contract.json",
            "task_type_decision.json",
            "strategy_decision.json",
            "selected_strategy.json",
            status_source,
            "policy_decision.json",
            "drift_report.json",
            "trajectory_score.json",
        ]
        if name and (run_dir / name).exists()
    ]

    output = {
        "run_id": run_id,
        "generated_by": "experience-extractor-v1.7",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_type": task_type,
        "strategy_id": strategy_id,
        "outcome_status": status,
        "outcome_kind": kind,
        "principle": principle_for(task_type, strategy_id, status, kind),
        "do_not_use_when": do_not_use_when(kind, status, weak_flags, drift, trajectory),
        "weak_verifier_patterns": weak_flags,
        "drift_causes": drift,
        "tool_use_issues": trajectory,
        "evidence_files": evidence_files,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }
    write_json(run_dir / "experience_extract.json", output)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Extract advisory experience from run artifacts.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        output = extract_experience(Path(args.run_dir))
    except Exception as exc:
        print(f"EXPERIENCE_EXTRACT_FAILED: {exc}")
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
