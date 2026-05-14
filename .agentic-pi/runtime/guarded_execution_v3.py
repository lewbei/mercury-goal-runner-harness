#!/usr/bin/env python3
"""Guarded Execution v3 bounded repair loop.

This deterministic runtime validates Stage 3 preflight, rejects an unsafe initial
bounded plan without writing its plan artifacts, emits a non-authority repair
request, accepts exactly one repaired plan, revalidates from scratch, and only
then writes declared non-authority artifacts. Policy and certifier remain the
only final-status authorities.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import guarded_execution_v2 as v2


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREFLIGHT_REPORT = ROOT / ".agentic-runs" / "stage3_runtime_preflight" / "stage3_runtime_preflight_report_v1.json"
DEFAULT_INITIAL_PLAN = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v3_initial_plan.json"
DEFAULT_REPAIR_PLAN = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v3_repair_plan.json"
DEFAULT_EXPECTED_ARTIFACTS = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v3_expected_artifacts.json"
DEFAULT_RUN_ID = "guarded_execution_v3_smoke"
DEFAULT_LEDGER_NAME = "guarded_execution_v3_ledger.json"
DEFAULT_REPAIR_REQUEST_NAME = "guarded_execution_v3_repair_request.json"
MIN_REPAIR_ATTEMPTS = 1
MAX_REPAIR_ATTEMPTS = 1
SAFE_INTENTS = {"bounded_repair_then_artifact_writes", "guarded_execution_v3_smoke"}


def load_optional_json(path: Path, label: str) -> tuple[dict[str, Any], list[str]]:
    if not path.is_file():
        return {}, [f"{label} missing: {path}"]
    try:
        data = v2.load_json(path)
    except Exception as exc:
        return {}, [f"{label} could not be parsed: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"{label} must be a JSON object: {path}"]
    return data, []


def guarded_json_output_path(raw_path: str | None, default_path: Path) -> Path:
    path = Path(raw_path) if raw_path else default_path
    if path.name in v2.PROTECTED_OUTPUT_NAMES:
        raise ValueError(f"refusing to write protected status artifact: {path}")
    return path


def guarded_repair_request_path(raw_path: str | None, run_dir: Path) -> Path:
    path = Path(raw_path) if raw_path else run_dir / "artifacts" / DEFAULT_REPAIR_REQUEST_NAME
    if path.name in v2.PROTECTED_OUTPUT_NAMES:
        raise ValueError(f"refusing to write protected status artifact: {path}")
    if path.is_absolute():
        resolved = path.resolve()
        root = run_dir.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(f"repair request output escapes run folder: {path}")
        if not resolved.relative_to(root).as_posix().startswith("artifacts/"):
            raise ValueError(f"repair request output must stay under artifacts/: {path}")
        return resolved
    resolved = (run_dir / path).resolve() if not path.as_posix().startswith("artifacts/") else (run_dir / path).resolve()
    root = run_dir.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repair request output escapes run folder: {path}")
    if not resolved.relative_to(root).as_posix().startswith("artifacts/"):
        raise ValueError(f"repair request output must stay under artifacts/: {path}")
    return resolved


def intent_is_safe(intent: str) -> bool:
    normalized = str(intent).strip().lower().replace("-", "_")
    if normalized in SAFE_INTENTS:
        return True
    return v2.intent_is_safe(intent)


def collect_validation(
    plan: dict[str, Any],
    expected_artifacts: dict[str, Any],
) -> dict[str, Any]:
    contract_ok, contract_errors, declared = v2.validate_expected_artifacts(expected_artifacts)
    plan_ok, plan_errors, actions = v2.validate_plan(plan)
    match_ok, match_errors, denied_from_match = (
        v2.validate_plan_against_contract(actions, declared) if contract_ok and actions else (False, ["plan cannot be matched to expected artifacts"], [])
    )
    flags = v2.unsafe_flags(plan if isinstance(plan, dict) else {}, actions, expected_artifacts if isinstance(expected_artifacts, dict) else {})
    flags["undeclared_path_attempted"] = any(
        "not declared" in error or "does not match expected_artifacts" in error for error in match_errors
    )
    ok = contract_ok and plan_ok and match_ok and not any(flags.values())
    violations: list[str] = []
    for group in [contract_errors, plan_errors, match_errors]:
        violations.extend(str(item) for item in group)
    for key, value in sorted(flags.items()):
        if value:
            violations.append(f"{key}=true")
    return {
        "ok": ok,
        "contract_ok": contract_ok,
        "contract_errors": contract_errors,
        "plan_ok": plan_ok,
        "plan_errors": plan_errors,
        "match_ok": match_ok,
        "match_errors": match_errors,
        "declared": declared,
        "actions": actions,
        "flags": flags,
        "denied_from_match": denied_from_match,
        "violations": violations,
    }


def repair_attempts(repair_bundle: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if repair_bundle.get("schema_version") != "guarded_execution_v3_repair_plan_v1":
        errors.append("repair plan schema_version must be guarded_execution_v3_repair_plan_v1")
    attempts = repair_bundle.get("repair_attempts")
    if not isinstance(attempts, list):
        errors.append("repair_attempts must be a list")
        return [], errors
    if len(attempts) < MIN_REPAIR_ATTEMPTS:
        errors.append("one repair attempt is required when initial plan is invalid")
    if len(attempts) > MAX_REPAIR_ATTEMPTS:
        errors.append("multiple repair attempts are not allowed")
    normalized: list[dict[str, Any]] = []
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            errors.append(f"repair attempt #{index} must be a JSON object")
            continue
        repaired_plan = attempt.get("plan")
        if not isinstance(repaired_plan, dict):
            errors.append(f"repair attempt #{index} missing plan object")
            continue
        normalized.append(repaired_plan)
    return normalized, errors


def repair_request_payload(run_id: str, initial_validation: dict[str, Any], preflight_ok: bool, intent_ok: bool) -> dict[str, Any]:
    return {
        "schema_version": "guarded_execution_v3_repair_request_v1",
        "run_id": run_id,
        "authority": v2.REQUIRED_AUTHORITY,
        "status": "REPAIR_REQUESTED",
        "preflight_checked": True,
        "preflight_ok": preflight_ok,
        "initial_plan_executed": False,
        "repair_attempts_allowed": MAX_REPAIR_ATTEMPTS,
        "runtime_intent_ok": intent_ok,
        "violations": initial_validation.get("violations", []),
        "denied_actions": [
            v2.action_order_entry(action, "DENIED", "; ".join(initial_validation.get("violations", [])) or "initial plan rejected")
            for action in initial_validation.get("actions", [])
        ],
        "status_authority": "certifier_only",
        "requires_policy_certifier_for_status": True,
        "can_certify_done": False,
    }


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, expected: Any, actual: Any) -> None:
    checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "expected": expected, "actual": actual})


def make_denied_entries(actions: list[dict[str, Any]], reason: str) -> list[dict[str, Any]]:
    return [v2.action_order_entry(action, "DENIED", reason) for action in actions]


def build_execution_report(
    preflight: dict[str, Any],
    preflight_path: Path,
    initial_plan: dict[str, Any],
    initial_plan_path: Path,
    repair_bundle: dict[str, Any],
    repair_plan_path: Path,
    repair_load_errors: list[str],
    expected_artifacts: dict[str, Any],
    expected_artifacts_path: Path,
    run_id: str,
    runtime_intent: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, str]]:
    run_dir = v2.run_dir_for_id(run_id)
    preflight_ok, preflight_errors = v2.preflight_is_usable(preflight)
    intent_ok = intent_is_safe(runtime_intent)
    initial_validation = collect_validation(initial_plan, expected_artifacts)
    initial_requires_repair = not initial_validation["ok"]
    attempts, repair_bundle_errors = repair_attempts(repair_bundle) if initial_requires_repair and not repair_load_errors else ([], repair_load_errors)
    repair_attempt_count = len(attempts)
    repair_attempt_count_ok = repair_attempt_count == 1 and not repair_bundle_errors
    repair_validation = collect_validation(attempts[0], expected_artifacts) if repair_attempt_count_ok else {
        "ok": False,
        "actions": [],
        "flags": {},
        "violations": repair_bundle_errors or ["repair plan was not available for validation"],
        "plan_errors": [],
        "match_errors": [],
        "contract_errors": [],
    }
    repair_request = repair_request_payload(run_id, initial_validation, preflight_ok, intent_ok) if initial_requires_repair and preflight_ok else None

    checks: list[dict[str, Any]] = []
    permissions = v2.preflight_permissions(preflight)
    add_check(checks, "preflight_usable", preflight_ok, "Stage 3 preflight passes and preserves permissions", preflight_errors)
    add_check(
        checks,
        "preflight_allows_planning_but_not_goal_execution",
        permissions.get("may_consume_planning_evidence") is True and permissions.get("may_execute_goals") is False,
        "may_consume_planning_evidence true and may_execute_goals false",
        {"may_consume_planning_evidence": permissions.get("may_consume_planning_evidence"), "may_execute_goals": permissions.get("may_execute_goals")},
    )
    add_check(
        checks,
        "initial_plan_rejected_without_execution",
        initial_requires_repair and len(initial_validation.get("actions", [])) > 0,
        "initial plan is invalid and must not execute before repair",
        {"initial_plan_valid": initial_validation["ok"], "violations": initial_validation["violations"]},
    )
    add_check(
        checks,
        "repair_request_available",
        repair_request is not None,
        "non-authority repair request is generated after initial denial",
        "generated" if repair_request is not None else "not generated",
    )
    add_check(
        checks,
        "exactly_one_repair_attempt",
        repair_attempt_count_ok,
        "exactly one repaired plan is supplied",
        repair_bundle_errors or {"repair_attempt_count": repair_attempt_count},
    )
    add_check(
        checks,
        "repaired_plan_valid_from_scratch",
        repair_validation["ok"],
        "repaired plan independently satisfies expected_artifacts and safety checks",
        repair_validation.get("violations", []),
    )
    add_check(
        checks,
        "unsafe_runtime_shapes_absent_after_repair",
        intent_ok and repair_validation.get("ok") is True and not any(repair_validation.get("flags", {}).values()),
        "no unsafe intent, protected path, raw command, budget violation, undeclared path, or authority language after repair",
        {**repair_validation.get("flags", {}), "runtime_intent_is_safe": intent_ok},
    )

    should_execute = all(check["status"] == "PASS" for check in checks)
    artifact_hashes: dict[str, str] = {}
    final_action_order: list[dict[str, Any]] = []
    if should_execute:
        for action in repair_validation["actions"]:
            artifact_path = v2.resolve_artifact_path(run_dir, action["artifact_path"])
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(action["content"], encoding="utf-8")
            digest = v2.sha256_text(action["content"])
            artifact_hashes[action["artifact_path"]] = digest
            final_action_order.append(v2.action_order_entry(action, "EXECUTED"))
    else:
        reason = "; ".join(
            str(error)
            for check in checks
            if check["status"] != "PASS"
            for error in (check["actual"] if isinstance(check["actual"], list) else [check["actual"]])
        ) or "guarded repair loop failed closed"
        final_action_order = make_denied_entries(repair_validation.get("actions", []), reason)

    status = "GUARDED_EXECUTION_V3_PASS" if should_execute else "GUARDED_EXECUTION_V3_FAIL"
    initial_denied = repair_request.get("denied_actions", []) if repair_request else make_denied_entries(initial_validation.get("actions", []), "preflight failed before repair request" if not preflight_ok else "initial plan rejected")
    ledger = {
        "schema_version": "guarded_execution_v3_ledger_v1",
        "run_id": run_id,
        "status": status,
        "preflight_checked": True,
        "initial_plan_valid": initial_validation["ok"],
        "initial_plan_executed": False,
        "initial_denied_action_count": len(initial_denied),
        "initial_denied_actions": initial_denied,
        "repair_request_written": repair_request is not None,
        "repair_request_artifact": f"artifacts/{DEFAULT_REPAIR_REQUEST_NAME}" if repair_request is not None else "",
        "repair_attempt_count": repair_attempt_count,
        "repaired_plan_valid": repair_validation["ok"],
        "final_action_order": final_action_order,
        "artifact_hashes": artifact_hashes,
        "action_count_executed": len([item for item in final_action_order if item["status"] == "EXECUTED"]),
        "action_count_denied_after_repair": len([item for item in final_action_order if item["status"] == "DENIED"]),
        "goal_execution_attempted": False,
        "arbitrary_command_attempted": bool(initial_validation.get("flags", {}).get("arbitrary_command_attempted")) or bool(repair_validation.get("flags", {}).get("arbitrary_command_attempted")),
        "protected_status_write_attempted": bool(initial_validation.get("flags", {}).get("protected_status_write_attempted")) or bool(repair_validation.get("flags", {}).get("protected_status_write_attempted")),
        "final_status_language_denied": bool(initial_validation.get("flags", {}).get("final_status_language_denied")) or bool(repair_validation.get("flags", {}).get("final_status_language_denied")),
        "multiple_repair_attempts_denied": repair_attempt_count > MAX_REPAIR_ATTEMPTS,
        "status_authority": "certifier_only",
        "requires_policy_certifier_for_status": True,
        "can_certify_done": False,
    }
    report = {
        "schema_version": "guarded_execution_v3_report_v1",
        "status": status,
        "authority": v2.REQUIRED_AUTHORITY,
        "runtime_intent": runtime_intent,
        "source_reports": {
            "stage3_runtime_preflight_report": v2.rel_path(preflight_path),
            "initial_plan": v2.rel_path(initial_plan_path),
            "repair_plan": v2.rel_path(repair_plan_path),
            "expected_artifacts": v2.rel_path(expected_artifacts_path),
        },
        "criteria": checks,
        "repair_loop": {
            "initial_plan_valid": initial_validation["ok"],
            "initial_plan_executed": False,
            "repair_request_written": repair_request is not None,
            "repair_attempt_count": repair_attempt_count,
            "repaired_plan_valid": repair_validation["ok"],
            "repair_executed": should_execute,
        },
        "runtime_execution": {
            "run_id": run_id,
            "preflight_checked": True,
            "initial_plan_executed": False,
            "repair_request_artifact": f"artifacts/{DEFAULT_REPAIR_REQUEST_NAME}" if repair_request is not None else "",
            "ledger_artifact": f"artifacts/{DEFAULT_LEDGER_NAME}",
            "repair_attempt_count": repair_attempt_count,
            "action_count_executed": ledger["action_count_executed"],
            "artifact_hashes": artifact_hashes,
            "produced_artifact_paths": sorted(artifact_hashes),
            "goal_execution_attempted": False,
            "arbitrary_command_attempted": ledger["arbitrary_command_attempted"],
            "protected_status_write_attempted": ledger["protected_status_write_attempted"],
            "final_status_language_denied": ledger["final_status_language_denied"],
            "multiple_repair_attempts_denied": ledger["multiple_repair_attempts_denied"],
            "status_authority": "certifier_only",
            "requires_policy_certifier_for_status": True,
            "can_certify_done": False,
        },
        "summary": {
            "preflight_status": preflight.get("status"),
            "criteria_passed": sum(1 for check in checks if check["status"] == "PASS"),
            "criteria_total": len(checks),
            "initial_violation_count": len(initial_validation["violations"]),
            "repair_violation_count": len(repair_validation.get("violations", [])),
        },
        "claim_boundary": "Guarded Execution v3 proves one bounded repair cycle can reject an invalid declared plan, emit a non-authority repair request, revalidate exactly one repaired plan, and write declared artifacts after Stage 3 preflight. It does not execute arbitrary goals, decide policy, certify DONE, or prove arbitrary runtime safety.",
    }
    return report, ledger, repair_request, artifact_hashes


def validate_execution_report(report: dict[str, Any], ledger: dict[str, Any], repair_request: dict[str, Any] | None) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "guarded_execution_v3_report_v1":
        errors.append("schema_version must be guarded_execution_v3_report_v1")
    if ledger.get("schema_version") != "guarded_execution_v3_ledger_v1":
        errors.append("ledger schema_version must be guarded_execution_v3_ledger_v1")
    if report.get("authority") != v2.REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    if v2.contains_final_status_value(report) or v2.contains_final_status_value(ledger) or v2.contains_final_status_value(repair_request or {}):
        errors.append("guarded execution v3 artifacts must not contain final status enum values")
    runtime = report.get("runtime_execution", {})
    for obj_name, obj in [("runtime_execution", runtime), ("ledger", ledger), ("repair_request", repair_request or {"can_certify_done": False, "status_authority": "certifier_only", "requires_policy_certifier_for_status": True})]:
        if obj.get("goal_execution_attempted") is True:
            errors.append(f"{obj_name}.goal_execution_attempted must not be true")
        if obj.get("can_certify_done") is not False:
            errors.append(f"{obj_name}.can_certify_done must be false")
        if obj.get("status_authority") != "certifier_only":
            errors.append(f"{obj_name}.status_authority must be certifier_only")
        if obj.get("requires_policy_certifier_for_status") is not True:
            errors.append(f"{obj_name}.requires_policy_certifier_for_status must be true")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
    else:
        expected_status = "GUARDED_EXECUTION_V3_PASS" if all(check.get("status") == "PASS" for check in criteria) else "GUARDED_EXECUTION_V3_FAIL"
        if report.get("status") != expected_status:
            errors.append(f"status must be {expected_status}")
        if ledger.get("status") != expected_status:
            errors.append(f"ledger status must be {expected_status}")
    if report.get("status") == "GUARDED_EXECUTION_V3_PASS":
        if ledger.get("initial_plan_valid") is not False:
            errors.append("passing guarded execution v3 must start from an invalid initial plan")
        if ledger.get("initial_plan_executed") is not False:
            errors.append("initial plan must not execute")
        if ledger.get("repair_request_written") is not True or repair_request is None:
            errors.append("passing guarded execution v3 must write a repair request")
        if ledger.get("repair_attempt_count") != 1:
            errors.append("passing guarded execution v3 must use exactly one repair attempt")
        if ledger.get("repaired_plan_valid") is not True:
            errors.append("passing guarded execution v3 must have a valid repaired plan")
        if ledger.get("action_count_executed", 0) < v2.MIN_ACTIONS:
            errors.append("passing guarded execution v3 must execute the repaired bounded plan")
        if ledger.get("artifact_hashes") != runtime.get("artifact_hashes"):
            errors.append("report and ledger artifact hashes must match")
    else:
        if ledger.get("action_count_executed") != 0:
            errors.append("failing guarded execution v3 must execute zero repaired-plan actions")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Guarded Execution v3 bounded repair loop")
    parser.add_argument("--preflight-report", default=str(DEFAULT_PREFLIGHT_REPORT))
    parser.add_argument("--initial-plan", default=str(DEFAULT_INITIAL_PLAN))
    parser.add_argument("--repair-plan", default=str(DEFAULT_REPAIR_PLAN))
    parser.add_argument("--expected-artifacts", default=str(DEFAULT_EXPECTED_ARTIFACTS))
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--runtime-intent", default="bounded_repair_then_artifact_writes")
    parser.add_argument("--output")
    parser.add_argument("--ledger-output")
    parser.add_argument("--repair-request-output")
    args = parser.parse_args(argv)

    try:
        run_dir = v2.run_dir_for_id(args.run_id)
        report_path = guarded_json_output_path(args.output, run_dir / "guarded_execution_v3_report.json")
        ledger_path = guarded_json_output_path(args.ledger_output, run_dir / "artifacts" / DEFAULT_LEDGER_NAME)
        repair_request_path = guarded_repair_request_path(args.repair_request_output, run_dir)
        preflight = v2.load_required_json(Path(args.preflight_report), "preflight report")
        initial_plan = v2.load_required_json(Path(args.initial_plan), "initial plan")
        expected_artifacts = v2.load_required_json(Path(args.expected_artifacts), "expected artifacts")
        repair_bundle, repair_load_errors = load_optional_json(Path(args.repair_plan), "repair plan")
        report, ledger, repair_request, _ = build_execution_report(
            preflight,
            Path(args.preflight_report),
            initial_plan,
            Path(args.initial_plan),
            repair_bundle,
            Path(args.repair_plan),
            repair_load_errors,
            expected_artifacts,
            Path(args.expected_artifacts),
            args.run_id,
            args.runtime_intent,
        )
        errors = validate_execution_report(report, ledger, repair_request)
        if repair_request is not None:
            v2.write_json(repair_request_path, repair_request)
        v2.write_json(ledger_path, ledger)
        v2.write_json(report_path, report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report["status"] != "GUARDED_EXECUTION_V3_PASS":
        for check in report["criteria"]:
            if check["status"] != "PASS":
                print(f"FAIL: {check['check_id']}: expected {check['expected']}, actual {check['actual']}", file=sys.stderr)
        return 1
    print(f"OK: {report['status']} ({len(report['criteria'])} checks) -> {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
