#!/usr/bin/env python3
"""Guarded runtime integration smoke.

This is the first runtime-shaped consumer of the Stage 3 preflight gate. It
loads and validates a Stage 3 runtime preflight report before writing a
non-authority smoke report. It never executes arbitrary goals, never decides
policy, and never certifies DONE.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = ROOT / ".agentic-pi" / "runtime" / "stage3_runtime_preflight.py"
DEFAULT_PREFLIGHT_REPORT = ROOT / ".agentic-runs" / "stage3_runtime_preflight" / "stage3_runtime_preflight_report_v1.json"
DEFAULT_OUTPUT = ROOT / ".agentic-runs" / "guarded_runtime_smoke" / "guarded_runtime_smoke_report_v1.json"
PROTECTED_OUTPUT_NAMES = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}
FINAL_STATUS_VALUES = {"CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"}
REQUIRED_AUTHORITY = {"authority_level": "evaluation_only", "final_status_authority": "certifier_only", "can_certify_done": False}
SAFE_INTENTS = {"consume_planning_evidence_only", "status_report_only"}
UNSAFE_INTENT_TOKENS = {
    "execute",
    "run goal",
    "run_goal",
    "write final_status",
    "write certification",
    "write policy_decision",
    "bypass policy",
    "bypass certifier",
    "certify done",
    "mark done",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    if path.name in PROTECTED_OUTPUT_NAMES:
        raise ValueError(f"refusing to write protected status artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def load_preflight_module():
    spec = importlib.util.spec_from_file_location("stage3_runtime_preflight_for_guarded_smoke", PREFLIGHT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def contains_final_status_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_final_status_value(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_final_status_value(child) for child in value)
    if isinstance(value, str):
        return any(re.search(rf"\b{re.escape(status)}\b", value, flags=re.IGNORECASE) for status in FINAL_STATUS_VALUES)
    return False


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, expected: Any, actual: Any) -> None:
    checks.append({
        "check_id": check_id,
        "status": "PASS" if passed else "FAIL",
        "expected": expected,
        "actual": actual,
    })


def intent_is_safe(intent: str) -> bool:
    normalized = intent.strip().lower().replace("-", "_")
    if normalized in SAFE_INTENTS:
        return True
    return not any(token in normalized for token in UNSAFE_INTENT_TOKENS)


def preflight_permissions(preflight: dict[str, Any]) -> dict[str, Any]:
    permissions = preflight.get("runtime_preflight", {})
    return permissions if isinstance(permissions, dict) else {}


def build_smoke_report(preflight: dict[str, Any], preflight_path: Path, runtime_intent: str) -> dict[str, Any]:
    preflight_module = load_preflight_module()
    preflight_errors = preflight_module.validate_preflight_report(preflight)
    permissions = preflight_permissions(preflight)
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "preflight_report_validates",
        preflight_errors == [],
        "stage3_runtime_preflight.validate_preflight_report returns no errors",
        preflight_errors,
    )
    add_check(
        checks,
        "preflight_passed",
        preflight.get("schema_version") == "stage3_runtime_preflight_report_v1" and preflight.get("status") == "STAGE3_RUNTIME_PREFLIGHT_PASS",
        "preflight schema_version stage3_runtime_preflight_report_v1 and status STAGE3_RUNTIME_PREFLIGHT_PASS",
        {"schema_version": preflight.get("schema_version"), "status": preflight.get("status")},
    )
    add_check(
        checks,
        "preflight_authority_boundary",
        preflight.get("authority") == REQUIRED_AUTHORITY,
        REQUIRED_AUTHORITY,
        preflight.get("authority"),
    )
    add_check(
        checks,
        "preflight_allows_planning_evidence_only",
        permissions.get("may_consume_planning_evidence") is True and permissions.get("may_execute_goals") is False,
        "may_consume_planning_evidence true and may_execute_goals false",
        {
            "may_consume_planning_evidence": permissions.get("may_consume_planning_evidence"),
            "may_execute_goals": permissions.get("may_execute_goals"),
        },
    )
    add_check(
        checks,
        "preflight_cannot_certify_done",
        permissions.get("may_certify_done") is False and permissions.get("requires_policy_certifier_for_status") is True,
        "may_certify_done false and requires_policy_certifier_for_status true",
        {
            "may_certify_done": permissions.get("may_certify_done"),
            "requires_policy_certifier_for_status": permissions.get("requires_policy_certifier_for_status"),
        },
    )
    add_check(
        checks,
        "runtime_intent_is_non_executing",
        intent_is_safe(runtime_intent),
        "runtime intent is one of safe non-executing smoke intents or contains no unsafe runtime tokens",
        runtime_intent,
    )
    add_check(
        checks,
        "preflight_report_has_no_final_status_values",
        not contains_final_status_value(preflight),
        "preflight report contains no final status enum values",
        "clean" if not contains_final_status_value(preflight) else "final status value present",
    )

    status = "GUARDED_RUNTIME_SMOKE_PASS" if all(check["status"] == "PASS" for check in checks) else "GUARDED_RUNTIME_SMOKE_FAIL"
    runtime_smoke = {
        "preflight_checked": True,
        "planning_evidence_consumed": status == "GUARDED_RUNTIME_SMOKE_PASS",
        "goal_execution_attempted": False,
        "protected_status_write_attempted": False,
        "status_authority": "certifier_only",
        "requires_policy_certifier_for_status": True,
    }
    if status != "GUARDED_RUNTIME_SMOKE_PASS":
        runtime_smoke["planning_evidence_consumed"] = False

    return {
        "schema_version": "guarded_runtime_smoke_report_v1",
        "status": status,
        "authority": REQUIRED_AUTHORITY,
        "runtime_intent": runtime_intent,
        "preflight_report": rel_path(preflight_path),
        "criteria": checks,
        "runtime_smoke": runtime_smoke,
        "summary": {
            "preflight_status": preflight.get("status"),
            "criteria_passed": sum(1 for check in checks if check["status"] == "PASS"),
            "criteria_total": len(checks),
        },
        "claim_boundary": "This guarded runtime smoke only proves a non-executing runtime path refused to proceed without a passing Stage 3 preflight report. It does not execute goals, decide policy, certify DONE, or prove arbitrary runtime safety.",
    }


def validate_smoke_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "guarded_runtime_smoke_report_v1":
        errors.append("schema_version must be guarded_runtime_smoke_report_v1")
    if report.get("authority") != REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    if contains_final_status_value(report):
        errors.append("guarded runtime smoke report must not contain final status enum values")
    runtime_smoke = report.get("runtime_smoke", {})
    if runtime_smoke.get("goal_execution_attempted") is not False:
        errors.append("runtime_smoke.goal_execution_attempted must be false")
    if runtime_smoke.get("protected_status_write_attempted") is not False:
        errors.append("runtime_smoke.protected_status_write_attempted must be false")
    if runtime_smoke.get("status_authority") != "certifier_only":
        errors.append("runtime_smoke.status_authority must be certifier_only")
    if runtime_smoke.get("requires_policy_certifier_for_status") is not True:
        errors.append("runtime_smoke.requires_policy_certifier_for_status must be true")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
    else:
        expected_status = "GUARDED_RUNTIME_SMOKE_PASS" if all(check.get("status") == "PASS" for check in criteria) else "GUARDED_RUNTIME_SMOKE_FAIL"
        if report.get("status") != expected_status:
            errors.append(f"status must be {expected_status}")
    if report.get("status") == "GUARDED_RUNTIME_SMOKE_PASS" and runtime_smoke.get("planning_evidence_consumed") is not True:
        errors.append("passing smoke must mark planning_evidence_consumed true")
    if report.get("status") != "GUARDED_RUNTIME_SMOKE_PASS" and runtime_smoke.get("planning_evidence_consumed") is not False:
        errors.append("failing smoke must not consume planning evidence")
    return errors


def load_required_preflight(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"preflight report missing: {path}")
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"preflight report must be a JSON object: {path}")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run guarded runtime integration smoke")
    parser.add_argument("--preflight-report", default=str(DEFAULT_PREFLIGHT_REPORT))
    parser.add_argument("--runtime-intent", default="consume_planning_evidence_only")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    preflight_path = Path(args.preflight_report)
    output_path = Path(args.output)
    try:
        report = build_smoke_report(load_required_preflight(preflight_path), preflight_path, args.runtime_intent)
        errors = validate_smoke_report(report)
        write_json(output_path, report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report["status"] != "GUARDED_RUNTIME_SMOKE_PASS":
        for check in report["criteria"]:
            if check["status"] != "PASS":
                print(f"FAIL: {check['check_id']}: expected {check['expected']}, actual {check['actual']}", file=sys.stderr)
        return 1
    print(f"OK: {report['status']} ({len(report['criteria'])} checks) -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
