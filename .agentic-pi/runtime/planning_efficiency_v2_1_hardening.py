#!/usr/bin/env python3
"""Planning Efficiency v2.1 hardening checks.

This deterministic hardening gate stress-checks Planning Efficiency v2 preflight
without executing the generated plan. It proves byte-stable preflight outputs,
scans for protected status artifact creation, checks final-status enum/name
leakage, and records certifier-only authority evidence.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import canonical_json
import guarded_execution_v2 as v2
import planning_efficiency_v2_preflight as preflight


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOAL = ROOT / ".agentic-pi" / "runtime" / "planning_efficiency_v2_goal.json"
DEFAULT_WORK_DIR = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v2_1_hardening"
DEFAULT_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v2_1_hardening_report.json"
PASS_STATUS = "PLANNING_EFFICIENCY_V2_1_HARDENING_PASS"
FAIL_STATUS = "PLANNING_EFFICIENCY_V2_1_HARDENING_FAIL"
ARTIFACT_KEYS = ["plan", "expected_artifacts", "compile_report", "lint_report", "preflight_report"]


def stable_json(data: Any) -> str:
    return canonical_json.stable_json(data)


def write_json(path: Path, data: Any) -> None:
    canonical_json.write_json_canonical(path, data, v2.is_protected_output_name)


def sha256_bytes(path: Path) -> str:
    return canonical_json.sha256_file(path)


def rel_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, expected: Any, actual: Any) -> None:
    checks.append({
        "check_id": check_id,
        "status": "PASS" if passed else "FAIL",
        "expected": expected,
        "actual": actual,
    })


def artifact_paths(work_dir: Path) -> dict[str, Path]:
    return {
        "plan": work_dir / "planning_efficiency_v2_plan.json",
        "expected_artifacts": work_dir / "planning_efficiency_v2_expected_artifacts.json",
        "compile_report": work_dir / "planning_efficiency_v2_compile_report.json",
        "lint_report": work_dir / "planning_efficiency_v2_lint_report.json",
        "preflight_report": work_dir / "planning_efficiency_v2_preflight_report.json",
    }


def run_preflight_to_paths(goal: dict[str, Any], goal_path: Path, paths: dict[str, Path]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    plan, expected, compile_report, lint_report, report = preflight.build_preflight(
        goal,
        paths["plan"],
        paths["expected_artifacts"],
        paths["compile_report"],
        paths["lint_report"],
        paths["preflight_report"],
        goal_path,
    )
    errors = preflight.validate_preflight_report(report)
    write_json(paths["compile_report"], compile_report)
    if report.get("status") == preflight.PASS_STATUS and plan is not None and expected is not None and lint_report is not None:
        write_json(paths["plan"], plan)
        write_json(paths["expected_artifacts"], expected)
        write_json(paths["lint_report"], lint_report)
    write_json(paths["preflight_report"], report)
    return plan or {}, expected or {}, compile_report, lint_report or {}, report, errors


def snapshot(paths: dict[str, Path]) -> dict[str, str]:
    missing = [key for key in ARTIFACT_KEYS if not paths[key].is_file()]
    if missing:
        raise FileNotFoundError(f"missing generated hardening artifacts: {missing}")
    return {key: sha256_bytes(paths[key]) for key in ARTIFACT_KEYS}


def protected_status_files_under(work_dir: Path) -> list[str]:
    if not work_dir.exists():
        return []
    return sorted(rel_path(path) for path in work_dir.rglob("*") if path.is_file() and v2.is_protected_output_name(path.name))


def runtime_authority_ok(objects: dict[str, Any]) -> bool:
    for obj in objects.values():
        if not isinstance(obj, dict):
            return False
        authority = obj.get("authority")
        if authority is not None and authority != v2.REQUIRED_AUTHORITY:
            return False
        runtime = obj.get("runtime_execution")
        if isinstance(runtime, dict):
            if runtime.get("goal_execution_attempted") is not False:
                return False
            if runtime.get("plan_execution_attempted") is not False:
                return False
            if runtime.get("status_authority") != "certifier_only":
                return False
            if runtime.get("can_certify_done") is not False:
                return False
    return True


def build_hardening_report(goal_path: Path, work_dir: Path, output_path: Path) -> dict[str, Any]:
    goal = preflight.load_required_json(goal_path, "goal")
    paths = artifact_paths(work_dir)
    snapshots: list[dict[str, str]] = []
    iteration_errors: list[str] = []
    final_objects: dict[str, Any] = {}
    for index in range(3):
        plan, expected, compile_report, lint_report, report, errors = run_preflight_to_paths(goal, goal_path, paths)
        iteration_errors.extend(f"iteration {index + 1}: {error}" for error in errors)
        if report.get("status") != preflight.PASS_STATUS:
            iteration_errors.append(f"iteration {index + 1}: preflight status {report.get('status')}")
        snapshots.append(snapshot(paths))
        final_objects = {
            "plan": plan,
            "expected_artifacts": expected,
            "compile_report": compile_report,
            "lint_report": lint_report,
            "preflight_report": report,
        }

    byte_stable = bool(snapshots) and all(item == snapshots[0] for item in snapshots[1:])
    protected_files = protected_status_files_under(work_dir)
    final_status_findings = preflight.final_status_enum_locations(final_objects)
    protected_name_findings = preflight.protected_status_artifact_name_locations(final_objects)
    preflight_report = final_objects.get("preflight_report", {}) if isinstance(final_objects.get("preflight_report"), dict) else {}
    preflight_no_execution = (
        preflight_report.get("runtime_execution", {}).get("goal_execution_attempted") is False
        and preflight_report.get("runtime_execution", {}).get("plan_execution_attempted") is False
        and preflight_report.get("runtime_execution", {}).get("guarded_execution_invoked") is False
    )
    authority_ok = runtime_authority_ok(final_objects)

    checks: list[dict[str, Any]] = []
    add_check(checks, "three_run_byte_stability", byte_stable, "three repeated preflight writes produce identical file bytes", snapshots)
    add_check(checks, "protected_status_artifacts_not_created", not protected_files, "no protected status artifacts are created under the hardening work directory", protected_files)
    add_check(checks, "final_status_enum_values_absent", not final_status_findings, "generated planning artifacts contain no final-status enum values", final_status_findings)
    add_check(checks, "protected_status_artifact_names_absent", not protected_name_findings, "generated planning artifacts contain no protected status artifact names", protected_name_findings)
    add_check(checks, "preflight_execution_not_attempted", preflight_no_execution, "preflight does not execute goals, plans, or guarded execution", preflight_report.get("runtime_execution"))
    add_check(checks, "certifier_only_authority_preserved", authority_ok, "generated reports preserve evaluation-only/certifier-only authority", {name: obj.get("authority") for name, obj in final_objects.items() if isinstance(obj, dict)})
    add_check(checks, "preflight_iterations_valid", not iteration_errors, "all three preflight iterations validate and pass", iteration_errors)

    status = PASS_STATUS if all(check["status"] == "PASS" for check in checks) else FAIL_STATUS
    return {
        "schema_version": "planning_efficiency_v2_1_hardening_report_v1",
        "status": status,
        "authority": v2.REQUIRED_AUTHORITY,
        "source_goal": rel_path(goal_path),
        "work_dir": rel_path(work_dir),
        "output": rel_path(output_path),
        "criteria": checks,
        "stable_artifact_hashes": snapshots[0] if snapshots else {},
        "iteration_count": len(snapshots),
        "runtime_execution": {
            "goal_execution_attempted": False,
            "plan_execution_attempted": False,
            "guarded_execution_invoked": False,
            "status_authority": "certifier_only",
            "requires_policy_certifier_for_status": True,
            "can_certify_done": False,
        },
        "claim_boundary": "Planning Efficiency v2.1 hardening proves deterministic byte-stability, status-artifact creation blocking, status-token leak checks, and certifier-only authority for the bounded v2 preflight path. It does not execute goals, decide policy, certify DONE, or prove arbitrary runtime safety.",
    }


def validate_hardening_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "planning_efficiency_v2_1_hardening_report_v1":
        errors.append("schema_version must be planning_efficiency_v2_1_hardening_report_v1")
    if report.get("authority") != v2.REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    if v2.contains_final_status_value(report):
        errors.append("hardening report must not contain final status enum values")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
    else:
        expected_status = PASS_STATUS if all(check.get("status") == "PASS" for check in criteria) else FAIL_STATUS
        if report.get("status") != expected_status:
            errors.append(f"status must be {expected_status}")
    runtime = report.get("runtime_execution", {})
    if runtime.get("goal_execution_attempted") is not False:
        errors.append("runtime_execution.goal_execution_attempted must be false")
    if runtime.get("plan_execution_attempted") is not False:
        errors.append("runtime_execution.plan_execution_attempted must be false")
    if runtime.get("guarded_execution_invoked") is not False:
        errors.append("runtime_execution.guarded_execution_invoked must be false")
    if runtime.get("status_authority") != "certifier_only":
        errors.append("runtime_execution.status_authority must be certifier_only")
    if runtime.get("can_certify_done") is not False:
        errors.append("runtime_execution.can_certify_done must be false")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Planning Efficiency v2.1 hardening checks without executing the generated plan.")
    parser.add_argument("--goal", default=str(DEFAULT_GOAL))
    parser.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    try:
        output_path = Path(args.output)
        if v2.is_protected_output_name(output_path.name):
            raise ValueError(f"refusing to write protected status artifact: {output_path}")
        report = build_hardening_report(Path(args.goal), Path(args.work_dir), output_path)
        errors = validate_hardening_report(report)
        write_json(output_path, report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report["status"] != PASS_STATUS:
        for check in report.get("criteria", []):
            if check.get("status") != "PASS":
                print(f"FAIL: {check['check_id']}: expected {check['expected']}, actual {check['actual']}", file=sys.stderr)
        return 1
    print(f"OK: {report['status']} ({len(report['criteria'])} checks) -> {args.output}")
    print("three-run byte stability verified")
    print("protected status artifacts not created")
    print("final-status enum values absent")
    print("protected status artifact names absent")
    print("certifier-only authority preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
