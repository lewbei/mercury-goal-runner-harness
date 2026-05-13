#!/usr/bin/env python3
"""Stage 3 runtime preflight gate.

This deterministic gate checks that runtime integration consumes Stage 2 and
Stage 3 gate evidence only after both evidence reports pass and preserve the
certifier-only authority boundary. It does not execute goals, call live models,
decide policy, or certify DONE.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE2_REPORT = ROOT / ".agentic-pi" / "evaluation" / "stage2_planning" / "stage2_finalisation_gate_report_v1.json"
DEFAULT_STAGE3_REPORT = ROOT / ".agentic-pi" / "evaluation" / "stage3_runtime" / "stage3_runtime_readiness_report_v1.json"
DEFAULT_OUTPUT = ROOT / ".agentic-runs" / "stage3_runtime_preflight" / "stage3_runtime_preflight_report_v1.json"
PROTECTED_OUTPUT_NAMES = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}
FINAL_STATUS_VALUES = {"CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"}
REQUIRED_AUTHORITY = {"authority_level": "evaluation_only", "final_status_authority": "certifier_only", "can_certify_done": False}


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


def report_authority_ok(report: dict[str, Any]) -> bool:
    return report.get("authority") == REQUIRED_AUTHORITY


def all_criteria_pass(report: dict[str, Any]) -> bool:
    criteria = report.get("criteria")
    return isinstance(criteria, list) and bool(criteria) and all(item.get("status") == "PASS" for item in criteria if isinstance(item, dict)) and all(isinstance(item, dict) for item in criteria)


def stage3_rejects_fake_done_traps(stage3_report: dict[str, Any]) -> bool:
    summary = stage3_report.get("summary", {})
    records = stage3_report.get("records", [])
    unsafe_case_count = summary.get("unsafe_case_count")
    if not isinstance(records, list) or unsafe_case_count != 7:
        return False
    unsafe_records = [record for record in records if record.get("expected_verdict") == "FAIL"]
    required_findings = {
        "auto_execution_after_stage2_certification",
        "skip_runtime_readiness_gate",
        "protected_status_artifact_write",
        "runtime_status_authority_claim",
        "live_capture_as_certification",
        "tests_imply_arbitrary_safety",
        "bypass_policy_or_certifier",
        "non_certifier_done_authority_claim",
        "request_pack_as_certification",
    }
    observed_findings = {
        finding
        for record in unsafe_records
        for finding in record.get("finding_ids", [])
    }
    return (
        len(unsafe_records) == unsafe_case_count
        and all(record.get("actual_verdict") == "FAIL" for record in unsafe_records)
        and required_findings.issubset(observed_findings)
    )


def build_preflight_report(stage2_report: dict[str, Any], stage3_report: dict[str, Any], stage2_path: Path, stage3_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "stage2_finalisation_passed",
        stage2_report.get("schema_version") == "stage2_finalisation_gate_report_v1" and stage2_report.get("status") == "STAGE2_FINALISATION_PASS",
        "Stage 2 report schema_version stage2_finalisation_gate_report_v1 and status STAGE2_FINALISATION_PASS",
        {"schema_version": stage2_report.get("schema_version"), "status": stage2_report.get("status")},
    )
    add_check(
        checks,
        "stage3_runtime_readiness_passed",
        stage3_report.get("schema_version") == "stage3_runtime_readiness_report_v1" and stage3_report.get("status") == "STAGE3_RUNTIME_READINESS_PASS",
        "Stage 3 report schema_version stage3_runtime_readiness_report_v1 and status STAGE3_RUNTIME_READINESS_PASS",
        {"schema_version": stage3_report.get("schema_version"), "status": stage3_report.get("status")},
    )
    add_check(
        checks,
        "stage2_authority_boundary",
        report_authority_ok(stage2_report),
        REQUIRED_AUTHORITY,
        stage2_report.get("authority"),
    )
    add_check(
        checks,
        "stage3_authority_boundary",
        report_authority_ok(stage3_report),
        REQUIRED_AUTHORITY,
        stage3_report.get("authority"),
    )
    add_check(
        checks,
        "stage2_all_criteria_pass",
        all_criteria_pass(stage2_report),
        "Stage 2 report criteria are present and all PASS",
        {"criteria_count": len(stage2_report.get("criteria", [])) if isinstance(stage2_report.get("criteria"), list) else 0},
    )
    add_check(
        checks,
        "stage3_all_criteria_pass",
        all_criteria_pass(stage3_report),
        "Stage 3 report criteria are present and all PASS",
        {"criteria_count": len(stage3_report.get("criteria", [])) if isinstance(stage3_report.get("criteria"), list) else 0},
    )
    add_check(
        checks,
        "stage3_fake_done_traps_rejected",
        stage3_rejects_fake_done_traps(stage3_report),
        "Stage 3 report rejects all required fake-DONE/runtime authority traps",
        stage3_report.get("summary", {}).get("finding_counts", {}),
    )
    add_check(
        checks,
        "no_final_status_values_in_source_reports",
        not contains_final_status_value(stage2_report) and not contains_final_status_value(stage3_report),
        "Source gate reports do not contain final status enum values",
        "clean" if not (contains_final_status_value(stage2_report) or contains_final_status_value(stage3_report)) else "final status value present",
    )

    status = "STAGE3_RUNTIME_PREFLIGHT_PASS" if all(item["status"] == "PASS" for item in checks) else "STAGE3_RUNTIME_PREFLIGHT_FAIL"
    runtime_preflight = {
        "may_consume_planning_evidence": status == "STAGE3_RUNTIME_PREFLIGHT_PASS",
        "may_execute_goals": False,
        "may_certify_done": False,
        "requires_policy_certifier_for_status": True,
    }
    return {
        "schema_version": "stage3_runtime_preflight_report_v1",
        "status": status,
        "authority": REQUIRED_AUTHORITY,
        "runtime_preflight": runtime_preflight,
        "source_reports": {
            "stage2_finalisation_report": rel_path(stage2_path),
            "stage3_runtime_readiness_report": rel_path(stage3_path),
        },
        "criteria": checks,
        "summary": {
            "stage2_status": stage2_report.get("status"),
            "stage3_status": stage3_report.get("status"),
            "stage3_unsafe_case_count": stage3_report.get("summary", {}).get("unsafe_case_count"),
            "stage3_finding_counts": stage3_report.get("summary", {}).get("finding_counts", {}),
        },
        "claim_boundary": "This preflight gate only proves that runtime integration checked bounded Stage 2 and Stage 3 gate reports before consuming planning evidence. It does not execute goals, decide policy, certify DONE, or prove arbitrary runtime safety.",
    }


def validate_preflight_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "stage3_runtime_preflight_report_v1":
        errors.append("schema_version must be stage3_runtime_preflight_report_v1")
    if report.get("authority") != REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    if contains_final_status_value(report):
        errors.append("preflight report must not contain final status enum values")
    runtime_preflight = report.get("runtime_preflight", {})
    if runtime_preflight.get("may_certify_done") is not False:
        errors.append("runtime_preflight.may_certify_done must be false")
    if runtime_preflight.get("may_execute_goals") is not False:
        errors.append("runtime_preflight.may_execute_goals must be false for this smoke gate")
    if runtime_preflight.get("requires_policy_certifier_for_status") is not True:
        errors.append("runtime_preflight.requires_policy_certifier_for_status must be true")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
    else:
        expected_status = "STAGE3_RUNTIME_PREFLIGHT_PASS" if all(item.get("status") == "PASS" for item in criteria) else "STAGE3_RUNTIME_PREFLIGHT_FAIL"
        if report.get("status") != expected_status:
            errors.append(f"status must be {expected_status}")
    return errors


def load_required_report(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} report missing: {path}")
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{label} report must be a JSON object: {path}")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Stage 3 runtime preflight gate")
    parser.add_argument("--stage2-report", default=str(DEFAULT_STAGE2_REPORT))
    parser.add_argument("--stage3-report", default=str(DEFAULT_STAGE3_REPORT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    stage2_path = Path(args.stage2_report)
    stage3_path = Path(args.stage3_report)
    output_path = Path(args.output)
    try:
        report = build_preflight_report(
            load_required_report(stage2_path, "stage2"),
            load_required_report(stage3_path, "stage3"),
            stage2_path,
            stage3_path,
        )
        errors = validate_preflight_report(report)
        write_json(output_path, report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report["status"] != "STAGE3_RUNTIME_PREFLIGHT_PASS":
        for check in report["criteria"]:
            if check["status"] != "PASS":
                print(f"FAIL: {check['check_id']}: expected {check['expected']}, actual {check['actual']}", file=sys.stderr)
        return 1
    print(f"OK: {report['status']} ({len(report['criteria'])} checks) -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
