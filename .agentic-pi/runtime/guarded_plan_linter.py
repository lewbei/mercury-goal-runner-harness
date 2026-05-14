#!/usr/bin/env python3
"""Guarded plan linter.

The linter is a deterministic pre-execution planning aid. It checks whether a
bounded plan is already compatible with the guarded execution contract before a
runtime attempts execution. It improves planning proficiency and efficiency by
returning exact repair hints instead of letting unsafe or malformed plans reach
execution.

It does not execute plans, decide policy, or certify completion.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import guarded_execution_v2 as v2


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = ROOT / ".agentic-pi" / "runtime" / "planning_efficiency_v1_plan.json"
DEFAULT_EXPECTED_ARTIFACTS = ROOT / ".agentic-pi" / "runtime" / "planning_efficiency_v1_expected_artifacts.json"
REQUIRED_PLAN_METADATA_KEYS = {"verifier_evidence_required", "required_verifier_checks"}


def load_required_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} missing: {path}")
    data = v2.load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return data


def write_json(path: Path, data: Any) -> None:
    if path.name in v2.PROTECTED_OUTPUT_NAMES:
        raise ValueError(f"refusing to write protected status artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def hint(code: str, message: str, target: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "target": target}


def metadata_errors(plan: dict[str, Any]) -> list[str]:
    metadata = plan.get("planning_metadata")
    errors: list[str] = []
    if not isinstance(metadata, dict):
        return ["planning_metadata must be present so verifier requirements are explicit"]
    missing = sorted(REQUIRED_PLAN_METADATA_KEYS - set(metadata))
    if missing:
        errors.append(f"planning_metadata missing required keys: {missing}")
    if metadata.get("verifier_evidence_required") is not True:
        errors.append("planning_metadata.verifier_evidence_required must be true")
    checks = metadata.get("required_verifier_checks")
    if not isinstance(checks, list) or not checks or not all(isinstance(item, str) and item.strip() for item in checks):
        errors.append("planning_metadata.required_verifier_checks must be a non-empty list of strings")
    return errors


def repair_hints_from_errors(
    contract_errors: list[str],
    plan_errors: list[str],
    match_errors: list[str],
    metadata_error_items: list[str],
    flags: dict[str, bool],
) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    for error in contract_errors:
        hints.append(hint("EXPECTED_ARTIFACTS_CONTRACT", error, "expected_artifacts"))
    for error in plan_errors:
        code = "PLAN_SHAPE"
        if "budget" in error:
            code = "ACTION_BUDGET"
        elif "raw command" in error or "command" in error:
            code = "RAW_COMMAND_SHAPE"
        elif "protected" in error:
            code = "PROTECTED_PATH"
        elif "final-status authority" in error:
            code = "AUTHORITY_LANGUAGE"
        hints.append(hint(code, error, "plan"))
    for error in match_errors:
        code = "PLAN_EXPECTED_ARTIFACT_MISMATCH"
        if "not declared" in error:
            code = "UNDECLARED_ARTIFACT"
        elif "not produced" in error:
            code = "MISSING_REQUIRED_ARTIFACT"
        hints.append(hint(code, error, "plan.actions"))
    for error in metadata_error_items:
        hints.append(hint("MISSING_VERIFIER_REQUIREMENTS", error, "plan.planning_metadata"))
    if flags.get("arbitrary_command_attempted"):
        hints.append(hint("RAW_COMMAND_SHAPE", "Remove command/cmd/shell/exec/python/bash/powershell keys from the plan.", "plan"))
    if flags.get("protected_status_write_attempted"):
        hints.append(hint("PROTECTED_PATH", "Move writes away from protected status or authority artifact names.", "plan.actions[].artifact_path"))
    if flags.get("final_status_language_denied"):
        hints.append(hint("AUTHORITY_LANGUAGE", "Remove final-status or completion-authority language from artifact content.", "plan.actions[].content"))
    if flags.get("over_budget_attempted"):
        hints.append(hint("ACTION_BUDGET", f"Reduce plan actions to at most {v2.MAX_ACTIONS}.", "plan.actions"))
    if flags.get("under_budget_attempted"):
        hints.append(hint("ACTION_BUDGET", f"Increase plan actions to at least {v2.MIN_ACTIONS}.", "plan.actions"))
    if flags.get("undeclared_path_attempted"):
        hints.append(hint("UNDECLARED_ARTIFACT", "Make every action artifact_id/path match exactly one expected_artifacts entry.", "plan.actions"))
    seen = set()
    deduped = []
    for item in hints:
        key = (item["code"], item["message"], item["target"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def lint_plan(plan: dict[str, Any], expected_artifacts: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    contract_ok, contract_errors, declared = v2.validate_expected_artifacts(expected_artifacts)
    plan_ok, plan_errors, actions = v2.validate_plan(plan)
    match_ok, match_errors, denied_from_match = (
        v2.validate_plan_against_contract(actions, declared) if contract_ok and actions else (False, ["plan cannot be matched to expected artifacts"], [])
    )
    flags = v2.unsafe_flags(plan, actions, expected_artifacts)
    flags["undeclared_path_attempted"] = any(
        "not declared" in error or "does not match expected_artifacts" in error for error in match_errors
    )
    metadata_error_items = metadata_errors(plan)
    metadata_ok = not metadata_error_items

    v2.add_check(checks, "expected_artifacts_contract_valid", contract_ok, "expected artifacts contract is valid", contract_errors)
    v2.add_check(checks, "bounded_plan_valid", plan_ok, f"plan has {v2.MIN_ACTIONS}..{v2.MAX_ACTIONS} safe actions", plan_errors)
    v2.add_check(checks, "plan_matches_expected_artifacts", match_ok, "all required expected artifacts are produced exactly once at declared paths", match_errors)
    v2.add_check(checks, "unsafe_shapes_absent", not any(flags.values()), "no raw command, protected path, budget, undeclared path, or authority-language violation", flags)
    v2.add_check(checks, "verifier_requirements_declared", metadata_ok, "plan declares verifier evidence requirements", metadata_error_items)

    repair_hints = repair_hints_from_errors(contract_errors, plan_errors, match_errors, metadata_error_items, flags)
    status = "PLAN_LINT_PASS" if all(check["status"] == "PASS" for check in checks) else "PLAN_LINT_FAIL"
    return {
        "schema_version": "guarded_plan_lint_report_v1",
        "status": status,
        "authority": v2.REQUIRED_AUTHORITY,
        "criteria": checks,
        "repair_hints": repair_hints,
        "denied_actions": denied_from_match,
        "planning_efficiency": {
            "declared_artifact_count": len(declared),
            "planned_action_count": len(actions),
            "criteria_passed": sum(1 for check in checks if check["status"] == "PASS"),
            "criteria_total": len(checks),
            "repair_hint_count": len(repair_hints),
            "ready_for_guarded_execution": status == "PLAN_LINT_PASS",
        },
        "runtime_execution": {
            "goal_execution_attempted": False,
            "plan_execution_attempted": False,
            "status_authority": "certifier_only",
            "requires_policy_certifier_for_status": True,
            "can_certify_done": False,
        },
        "claim_boundary": "Plan linting improves planning proficiency and efficiency by catching deterministic plan errors before execution. It does not execute goals, decide policy, certify DONE, or prove arbitrary runtime safety.",
    }


def validate_lint_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "guarded_plan_lint_report_v1":
        errors.append("schema_version must be guarded_plan_lint_report_v1")
    if report.get("authority") != v2.REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    runtime = report.get("runtime_execution", {})
    if runtime.get("goal_execution_attempted") is not False:
        errors.append("runtime_execution.goal_execution_attempted must be false")
    if runtime.get("plan_execution_attempted") is not False:
        errors.append("runtime_execution.plan_execution_attempted must be false")
    if runtime.get("status_authority") != "certifier_only":
        errors.append("runtime_execution.status_authority must be certifier_only")
    if runtime.get("can_certify_done") is not False:
        errors.append("runtime_execution.can_certify_done must be false")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
    else:
        expected_status = "PLAN_LINT_PASS" if all(check.get("status") == "PASS" for check in criteria) else "PLAN_LINT_FAIL"
        if report.get("status") != expected_status:
            errors.append(f"status must be {expected_status}")
    if report.get("status") == "PLAN_LINT_FAIL" and not report.get("repair_hints"):
        errors.append("failing lint reports must include repair_hints")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint a guarded execution plan without executing it.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--expected-artifacts", default=str(DEFAULT_EXPECTED_ARTIFACTS))
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        report = lint_plan(
            load_required_json(Path(args.plan), "plan"),
            load_required_json(Path(args.expected_artifacts), "expected artifacts"),
        )
        errors = validate_lint_report(report)
        if args.output:
            write_json(Path(args.output), report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report["status"] != "PLAN_LINT_PASS":
        for repair_hint in report["repair_hints"]:
            print(f"HINT: {repair_hint['code']}: {repair_hint['message']}", file=sys.stderr)
        return 1
    print(f"OK: {report['status']} ({len(report['criteria'])} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
