#!/usr/bin/env python3
"""Planning Efficiency v2.2 cleanup checks.

This deterministic cleanup gate verifies that the Planning Efficiency v2/v2.1
path uses the shared canonical JSON writer, consumes an explicit Stage 3 runtime
preflight report as a non-executing compatibility input, and keeps the bounded
planning claim narrow. It does not execute generated plans, decide policy, or
certify completion.
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
import stage3_runtime_preflight as stage3


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOAL = ROOT / ".agentic-pi" / "runtime" / "planning_efficiency_v2_goal.json"
DEFAULT_WORK_DIR = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v2_2_cleanup"
DEFAULT_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v2_2_cleanup_report.json"
PASS_STATUS = "PLANNING_EFFICIENCY_V2_2_CLEANUP_PASS"
FAIL_STATUS = "PLANNING_EFFICIENCY_V2_2_CLEANUP_FAIL"
ARTIFACT_KEYS = [
    "stage3_preflight_report",
    "plan",
    "expected_artifacts",
    "compile_report",
    "lint_report",
    "preflight_report",
]


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
        "stage3_preflight_report": work_dir / "stage3_runtime_preflight_report_v1.json",
        "plan": work_dir / "planning_efficiency_v2_plan.json",
        "expected_artifacts": work_dir / "planning_efficiency_v2_expected_artifacts.json",
        "compile_report": work_dir / "planning_efficiency_v2_compile_report.json",
        "lint_report": work_dir / "planning_efficiency_v2_lint_report.json",
        "preflight_report": work_dir / "planning_efficiency_v2_preflight_report.json",
    }


def build_stage3_report() -> tuple[dict[str, Any], list[str]]:
    report = stage3.build_preflight_report(
        stage3.load_required_report(stage3.DEFAULT_STAGE2_REPORT, "stage2"),
        stage3.load_required_report(stage3.DEFAULT_STAGE3_REPORT, "stage3"),
        stage3.DEFAULT_STAGE2_REPORT,
        stage3.DEFAULT_STAGE3_REPORT,
    )
    return report, stage3.validate_preflight_report(report)


def write_json(path: Path, data: Any) -> dict[str, Any]:
    return canonical_json.write_json_canonical(path, data, v2.is_protected_output_name)


def write_preflight_outputs(
    paths: dict[str, Path],
    plan: dict[str, Any] | None,
    expected: dict[str, Any] | None,
    compile_report: dict[str, Any],
    lint_report: dict[str, Any] | None,
    report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    metadata["compile_report"] = write_json(paths["compile_report"], compile_report)
    if report.get("status") == preflight.PASS_STATUS and plan is not None and expected is not None and lint_report is not None:
        metadata["plan"] = write_json(paths["plan"], plan)
        metadata["expected_artifacts"] = write_json(paths["expected_artifacts"], expected)
        metadata["lint_report"] = write_json(paths["lint_report"], lint_report)
    metadata["preflight_report"] = write_json(paths["preflight_report"], report)
    return metadata


def snapshot(paths: dict[str, Path]) -> dict[str, str]:
    missing = [key for key in ARTIFACT_KEYS if not paths[key].is_file()]
    if missing:
        raise FileNotFoundError(f"missing generated cleanup artifacts: {missing}")
    return {key: canonical_json.sha256_file(paths[key]) for key in ARTIFACT_KEYS}


def all_readbacks_match(write_metadata: list[dict[str, dict[str, Any]]], paths: dict[str, Path]) -> tuple[bool, dict[str, Any]]:
    mismatches: list[str] = []
    for iteration_index, iteration in enumerate(write_metadata, start=1):
        for key, metadata in iteration.items():
            path = paths[key]
            actual = canonical_json.sha256_file(path)
            if metadata.get("writer") != canonical_json.CANONICAL_JSON_VERSION:
                mismatches.append(f"iteration {iteration_index} {key}: writer mismatch")
            if metadata.get("readback_verified") is not True:
                mismatches.append(f"iteration {iteration_index} {key}: readback not verified")
            if metadata.get("sha256") != actual:
                mismatches.append(f"iteration {iteration_index} {key}: hash mismatch")
    return not mismatches, {"iterations": len(write_metadata), "mismatches": mismatches}


def build_cleanup_report(goal_path: Path, work_dir: Path, output_path: Path) -> dict[str, Any]:
    paths = artifact_paths(work_dir)
    goal = preflight.load_required_json(goal_path, "goal")
    snapshots: list[dict[str, str]] = []
    write_metadata: list[dict[str, dict[str, Any]]] = []
    iteration_errors: list[str] = []
    final_report: dict[str, Any] = {}

    for index in range(3):
        stage3_report, stage3_errors = build_stage3_report()
        stage3_metadata = write_json(paths["stage3_preflight_report"], stage3_report)
        iteration_errors.extend(f"iteration {index + 1}: stage3 {error}" for error in stage3_errors)
        plan, expected, compile_report, lint_report, report = preflight.build_preflight(
            goal,
            paths["plan"],
            paths["expected_artifacts"],
            paths["compile_report"],
            paths["lint_report"],
            paths["preflight_report"],
            goal_path,
            stage3_report,
            paths["stage3_preflight_report"],
        )
        errors = preflight.validate_preflight_report(report)
        iteration_errors.extend(f"iteration {index + 1}: preflight {error}" for error in errors)
        if report.get("status") != preflight.PASS_STATUS:
            iteration_errors.append(f"iteration {index + 1}: preflight status {report.get('status')}")
        metadata = {"stage3_preflight_report": stage3_metadata}
        metadata.update(write_preflight_outputs(paths, plan, expected, compile_report, lint_report, report))
        write_metadata.append(metadata)
        snapshots.append(snapshot(paths))
        final_report = report

    byte_stable = bool(snapshots) and all(item == snapshots[0] for item in snapshots[1:])
    readback_ok, readback_actual = all_readbacks_match(write_metadata, paths)
    stage3_check_ok = any(
        check.get("check_id") == "stage3_runtime_preflight_usable" and check.get("status") == "PASS"
        for check in final_report.get("criteria", [])
    )
    source_reports = final_report.get("source_reports", {}) if isinstance(final_report.get("source_reports"), dict) else {}
    execution_gate = final_report.get("execution_gate", {}) if isinstance(final_report.get("execution_gate"), dict) else {}
    stage3_source_ok = source_reports.get("stage3_runtime_preflight_report") == rel_path(paths["stage3_preflight_report"])
    exact_runtime_ok = execution_gate.get("required_next_runtime") == "guarded_execution_v2" and execution_gate.get("runtime_module") == ".agentic-pi/runtime/guarded_execution_v2.py"
    no_execution = (
        final_report.get("runtime_execution", {}).get("goal_execution_attempted") is False
        and final_report.get("runtime_execution", {}).get("plan_execution_attempted") is False
        and final_report.get("runtime_execution", {}).get("guarded_execution_invoked") is False
        and final_report.get("runtime_execution", {}).get("can_certify_done") is False
    )

    checks: list[dict[str, Any]] = []
    add_check(checks, "canonical_json_writer_readback_verified", readback_ok, "all JSON writes use canonical_json_v1 and readback hashes match file bytes", readback_actual)
    add_check(checks, "three_run_byte_stability_with_stage3_input", byte_stable, "three repeated Stage 3 + planning preflight writes produce identical file bytes", snapshots)
    add_check(checks, "stage3_runtime_preflight_input_checked", stage3_check_ok and stage3_source_ok, "planning preflight checks an explicit Stage 3 runtime preflight source report", {"stage3_check_ok": stage3_check_ok, "source_reports": source_reports})
    add_check(checks, "exact_guarded_execution_v2_binding", exact_runtime_ok, "planning preflight emits an exact guarded_execution_v2 runtime binding", execution_gate)
    add_check(checks, "preflight_execution_not_attempted", no_execution, "cleanup path does not execute goals, plans, guarded execution, or certify DONE", final_report.get("runtime_execution"))
    add_check(checks, "preflight_iterations_valid", not iteration_errors, "all three cleanup iterations validate and pass", iteration_errors)

    status = PASS_STATUS if all(check["status"] == "PASS" for check in checks) else FAIL_STATUS
    return {
        "schema_version": "planning_efficiency_v2_2_cleanup_report_v1",
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
        "claim_boundary": "Planning Efficiency v2.2 cleanup proves canonical JSON readback, explicit Stage 3 preflight compatibility, exact Guarded Execution v2 binding, and byte-stability for the bounded planning preflight path. It does not execute goals, decide policy, certify DONE, or prove arbitrary runtime safety.",
    }


def validate_cleanup_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "planning_efficiency_v2_2_cleanup_report_v1":
        errors.append("schema_version must be planning_efficiency_v2_2_cleanup_report_v1")
    if report.get("authority") != v2.REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    if v2.contains_final_status_value(report):
        errors.append("cleanup report must not contain final status enum values")
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
    parser = argparse.ArgumentParser(description="Run Planning Efficiency v2.2 cleanup checks without executing the generated plan.")
    parser.add_argument("--goal", default=str(DEFAULT_GOAL))
    parser.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    try:
        output_path = Path(args.output)
        if v2.is_protected_output_name(output_path.name):
            raise ValueError(f"refusing to write protected status artifact: {output_path}")
        report = build_cleanup_report(Path(args.goal), Path(args.work_dir), output_path)
        errors = validate_cleanup_report(report)
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
    print("canonical JSON writer readback verified")
    print("three-run byte stability with Stage 3 input verified")
    print("Stage 3 runtime preflight input checked")
    print("exact guarded_execution_v2 binding verified")
    print("certifier-only authority preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
