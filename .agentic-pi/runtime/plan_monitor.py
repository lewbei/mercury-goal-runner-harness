#!/usr/bin/env python3
"""Compare execution logs against merged_plan.json and report drift signals."""
import argparse
import json
import sys
from pathlib import Path


PROTECTED_NAMES = {"final_status.md", "certification.json", "policy_decision.json"}
PROTECTED_PREFIXES = {"verifier_artifacts/", "verifier_smell_reports/", "verifier_strength_reports/"}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute path is not allowed: {raw_path}")
    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {raw_path}")
    return resolved


def run_relative(run_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(run_dir.resolve()).as_posix()


def sorted_step_logs(step_dir: Path) -> list[Path]:
    def sort_key(path: Path):
        try:
            return int(path.stem)
        except ValueError:
            return path.stem

    return sorted(step_dir.glob("*.json"), key=sort_key)


def protected_path_violation(rel_path: str) -> str:
    if Path(rel_path).name in PROTECTED_NAMES:
        return f"worker touched protected status artifact: {rel_path}"
    if any(rel_path == prefix.rstrip("/") or rel_path.startswith(prefix) for prefix in PROTECTED_PREFIXES):
        return f"worker touched protected provenance path: {rel_path}"
    return ""


def expected_repair_target(expected_step: dict, expected_rel: str) -> dict:
    produces = expected_step.get("produces", [])
    produced = produces[0] if produces and isinstance(produces[0], dict) else {}
    return {
        "task_id": expected_step.get("task_id", ""),
        "action": expected_step.get("action", "create_file"),
        "path": expected_rel,
        "content": expected_step.get("content", ""),
        "produces": [
            {
                "artifact_id": produced.get("artifact_id", "A.REPAIRED_OUTPUT"),
                "path": produced.get("path", expected_rel),
            }
        ],
    }


def monitor_run(run_dir: Path) -> dict:
    goal = load_json(run_dir / "goal_contract.json")
    merged = load_json(run_dir / "merged_plan.json")
    steps = merged.get("steps", [])
    logs = sorted_step_logs(run_dir / "step_logs") if (run_dir / "step_logs").is_dir() else []

    fatal = []
    repairable = []
    minor = []
    repair_targets = []

    if len(logs) != len(steps):
        repairable.append(f"step log count {len(logs)} does not match merged plan step count {len(steps)}")

    for index, expected_step in enumerate(steps, start=1):
        log_path = logs[index - 1] if index <= len(logs) else None
        if log_path is None:
            repairable.append(f"missing step log for merged plan step {index}")
            raw_expected_path = expected_step.get("path", "")
            if isinstance(raw_expected_path, str) and raw_expected_path:
                expected_rel = run_relative(run_dir, resolve_run_path(run_dir, raw_expected_path))
                repair_targets.append(expected_repair_target(expected_step, expected_rel))
            continue

        try:
            step_log = load_json(log_path)
        except Exception as exc:
            fatal.append(f"{log_path.name} parse failed: {exc}")
            continue

        actual_touched = set()
        for raw_path in step_log.get("files_touched", []):
            if not isinstance(raw_path, str):
                continue
            try:
                rel_path = run_relative(run_dir, resolve_run_path(run_dir, raw_path))
            except ValueError as exc:
                fatal.append(f"{log_path.name} touched path invalid: {exc}")
                continue
            actual_touched.add(rel_path)
            protected_violation = protected_path_violation(rel_path)
            if protected_violation:
                fatal.append(f"{log_path.name} {protected_violation}")

        expected_action = expected_step.get("action", "placeholder")
        if step_log.get("action_taken") != expected_action:
            repairable.append(
                f"step {index} action mismatch: expected {expected_action}, got {step_log.get('action_taken')}"
            )

        if expected_action == "create_file":
            raw_expected_path = expected_step.get("path", "")
            if not isinstance(raw_expected_path, str) or not raw_expected_path.strip():
                fatal.append(f"merged plan step {index} create_file path is empty")
                continue
            expected_rel = run_relative(run_dir, resolve_run_path(run_dir, raw_expected_path))
            expected_path = run_dir / expected_rel
            mismatch = expected_rel not in actual_touched
            missing = not expected_path.is_file()
            if mismatch:
                repairable.append(f"step {index} touched files do not include merged plan path: {expected_rel}")
            if missing:
                repairable.append(f"expected artifact missing after step {index}: {expected_rel}")
            if mismatch or missing:
                repair_targets.append(expected_repair_target(expected_step, expected_rel))

    output = {
        "run_id": goal.get("run_id", run_dir.name),
        "generated_by": "plan-monitor-v1.5",
        "expected_step_count": len(steps),
        "actual_step_count": len(logs),
        "valid": not fatal,
        "fatal_violations": fatal,
        "repairable_violations": repairable,
        "minor_notes": minor,
        "repair_targets": repair_targets,
    }
    write_json(run_dir / "plan_monitor_report.json", output)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Monitor execution against merged_plan.json.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        report = monitor_run(Path(args.run_dir))
    except Exception as exc:
        print(f"PLAN_MONITOR_FAILED: {exc}")
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
