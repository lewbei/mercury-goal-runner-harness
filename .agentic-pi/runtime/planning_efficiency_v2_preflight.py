#!/usr/bin/env python3
"""Planning Efficiency v2 preflight integration.

This deterministic pre-execution gate wires the Planning Efficiency v1 compiler
and linter into the guarded runtime path. It compiles a rough goal into guarded
execution inputs, lints those inputs, records deterministic hashes, scans for
high-risk token/status leakage, and emits a gate report that tells the next
runtime whether the plan may be passed to Guarded Execution v2/v3.

It does not execute the compiled plan, run arbitrary commands, decide policy, or
certify completion.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import canonical_json
import guarded_execution_v2 as v2
import guarded_plan_compiler as compiler
import guarded_plan_linter as linter


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOAL = ROOT / ".agentic-pi" / "runtime" / "planning_efficiency_v2_goal.json"
DEFAULT_PLAN_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v2_plan.json"
DEFAULT_EXPECTED_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v2_expected_artifacts.json"
DEFAULT_COMPILE_REPORT_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v2_compile_report.json"
DEFAULT_LINT_REPORT_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v2_lint_report.json"
DEFAULT_PREFLIGHT_REPORT_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v2_preflight_report.json"
PASS_STATUS = "PLANNING_EFFICIENCY_V2_PREFLIGHT_PASS"
FAIL_STATUS = "PLANNING_EFFICIENCY_V2_PREFLIGHT_FAIL"
TOKEN_PATTERNS = [
    ("API_KEY_PATTERN", re.compile(r"\bapi[_-]?key\b", re.IGNORECASE)),
    ("SECRET_PATTERN", re.compile(r"\b(secret|client_secret|private_key|access_token|refresh_token)\b", re.IGNORECASE)),
    ("BEARER_TOKEN_PATTERN", re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)),
    ("SK_PREFIX_TOKEN_PATTERN", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")),
    ("PRIVATE_KEY_BLOCK_PATTERN", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
PROTECTED_STATUS_ARTIFACT_NAMES = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}


def load_required_json(path: Path, label: str) -> dict[str, Any]:
    return compiler.load_required_json(path, label)


def write_json(path: Path, data: Any) -> None:
    canonical_json.write_json_canonical(path, data, v2.is_protected_output_name)


def stable_json(data: Any) -> str:
    return canonical_json.stable_json(data)


def sha256_json(data: Any) -> str:
    return canonical_json.sha256_json(data)


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


def protected_output_errors(paths: list[Path]) -> list[str]:
    return [f"output path targets protected status artifact: {path}" for path in paths if v2.is_protected_output_name(path.name)]


def collect_string_locations(value: Any, root: str = "$") -> list[tuple[str, str]]:
    if isinstance(value, dict):
        found: list[tuple[str, str]] = []
        for key, child in value.items():
            key_text = str(key)
            found.append((f"{root}.<key:{key_text}>", key_text))
            found.extend(collect_string_locations(child, f"{root}.{key_text}"))
        return found
    if isinstance(value, list):
        found = []
        for index, child in enumerate(value):
            found.extend(collect_string_locations(child, f"{root}[{index}]"))
        return found
    if isinstance(value, str):
        return [(root, value)]
    return []


def token_leak_locations(objects: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for object_name, obj in objects.items():
        for location, text in collect_string_locations(obj, object_name):
            for code, pattern in TOKEN_PATTERNS:
                if pattern.search(text):
                    findings.append({"code": code, "location": location})
    return findings


def final_status_enum_locations(objects: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for object_name, obj in objects.items():
        for location, text in collect_string_locations(obj, object_name):
            for status in sorted(v2.FINAL_STATUS_VALUES):
                if re.search(rf"\b{re.escape(status)}\b", text, flags=re.IGNORECASE):
                    findings.append({"status_value": status, "location": location})
    return findings


def protected_status_artifact_name_locations(objects: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for object_name, obj in objects.items():
        for location, text in collect_string_locations(obj, object_name):
            for name in sorted(PROTECTED_STATUS_ARTIFACT_NAMES):
                if re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w.-])", text, flags=re.IGNORECASE):
                    findings.append({"artifact_name": name, "location": location})
    return findings


def generated_paths_are_declared(plan: dict[str, Any] | None, expected: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if not isinstance(plan, dict) or not isinstance(expected, dict):
        return False, ["plan and expected_artifacts must both exist"]
    contract_ok, contract_errors, declared = v2.validate_expected_artifacts(expected)
    plan_ok, plan_errors, actions = v2.validate_plan(plan)
    match_ok, match_errors, _ = v2.validate_plan_against_contract(actions, declared) if contract_ok and actions else (False, ["plan cannot be matched to expected artifacts"], [])
    errors = [*contract_errors, *plan_errors, *match_errors]
    return contract_ok and plan_ok and match_ok, errors


def build_preflight(
    goal: dict[str, Any],
    plan_output: Path,
    expected_output: Path,
    compile_report_output: Path,
    lint_report_output: Path,
    preflight_report_output: Path,
    goal_path: Path | None = None,
    stage3_preflight: dict[str, Any] | None = None,
    stage3_preflight_path: Path | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any], dict[str, Any] | None, dict[str, Any]]:
    output_errors = protected_output_errors([plan_output, expected_output, compile_report_output, lint_report_output, preflight_report_output])
    stage3_checked = stage3_preflight is not None
    if stage3_checked:
        stage3_ok, stage3_errors = v2.preflight_is_usable(stage3_preflight)
    else:
        stage3_ok, stage3_errors = True, []
    plan, expected, compile_report = compiler.compile_goal(goal)
    compile_report_errors = compiler.validate_compile_report(compile_report)
    lint_report = linter.lint_plan(plan, expected) if plan is not None and expected is not None else None
    lint_report_errors = linter.validate_lint_report(lint_report) if lint_report is not None else ["lint report was not produced"]

    replay_plan, replay_expected, replay_compile_report = compiler.compile_goal(goal)
    replay_lint_report = linter.lint_plan(replay_plan, replay_expected) if replay_plan is not None and replay_expected is not None else None
    generated_objects = {
        "plan": plan,
        "expected_artifacts": expected,
        "compile_report": compile_report,
        "lint_report": lint_report,
    }
    replay_objects = {
        "plan": replay_plan,
        "expected_artifacts": replay_expected,
        "compile_report": replay_compile_report,
        "lint_report": replay_lint_report,
    }
    generated_hashes = {name: sha256_json(obj) for name, obj in generated_objects.items() if obj is not None}
    replay_hashes = {name: sha256_json(obj) for name, obj in replay_objects.items() if obj is not None}
    deterministic_ok = generated_hashes == replay_hashes and bool(generated_hashes)

    generated_present_objects = {name: obj for name, obj in generated_objects.items() if obj is not None}
    token_findings = token_leak_locations(generated_present_objects)
    final_status_findings = final_status_enum_locations(generated_present_objects)
    protected_name_findings = protected_status_artifact_name_locations(generated_present_objects)
    paths_ok, path_errors = generated_paths_are_declared(plan, expected)
    compile_ok = compile_report.get("status") == "PLAN_COMPILE_PASS" and not compile_report_errors
    lint_ok = bool(lint_report) and lint_report.get("status") == "PLAN_LINT_PASS" and not lint_report_errors
    runtime_flags_ok = (
        compile_report.get("runtime_execution", {}).get("goal_execution_attempted") is False
        and compile_report.get("runtime_execution", {}).get("plan_execution_attempted") is False
        and (not lint_report or lint_report.get("runtime_execution", {}).get("goal_execution_attempted") is False)
        and (not lint_report or lint_report.get("runtime_execution", {}).get("plan_execution_attempted") is False)
    )

    checks: list[dict[str, Any]] = []
    add_check(checks, "output_paths_unprotected", not output_errors, "no generated output path targets protected status artifacts", output_errors)
    add_check(checks, "compiler_passed", compile_ok, "compiler returns PLAN_COMPILE_PASS and validates", compile_report_errors or compile_report.get("status"))
    add_check(checks, "linter_passed", lint_ok, "linter returns PLAN_LINT_PASS and validates", lint_report_errors or (lint_report or {}).get("status"))
    if stage3_checked:
        add_check(checks, "stage3_runtime_preflight_usable", stage3_ok, "Stage 3 runtime preflight passes before guarded execution handoff", stage3_errors)
    add_check(checks, "generated_paths_declared", paths_ok, "every generated plan action matches expected_artifacts exactly", path_errors)
    add_check(checks, "deterministic_replay_hashes_match", deterministic_ok, "same goal compiles/lints to identical JSON hashes", {"generated_hashes": generated_hashes, "replay_hashes": replay_hashes})
    add_check(checks, "sensitive_token_patterns_absent", not token_findings, "generated planning artifacts contain no high-risk token patterns", token_findings)
    add_check(checks, "final_status_enum_values_absent", not final_status_findings, "generated planning artifacts contain no final-status enum values", final_status_findings)
    add_check(checks, "protected_status_artifact_names_absent", not protected_name_findings, "generated planning artifacts contain no protected status artifact names", protected_name_findings)
    add_check(checks, "execution_not_attempted", runtime_flags_ok, "compile/lint preflight does not execute the plan or goal", {"compiler_runtime": compile_report.get("runtime_execution"), "lint_runtime": (lint_report or {}).get("runtime_execution")})

    status = PASS_STATUS if all(check["status"] == "PASS" for check in checks) else FAIL_STATUS
    repair_hints = [] if not lint_report else lint_report.get("repair_hints", [])
    if token_findings:
        repair_hints.append({"code": "TOKEN_PATTERN", "message": "Remove high-risk token-like text from generated planning artifacts before guarded execution.", "target": "plan.actions[].content"})
    if final_status_findings:
        repair_hints.append({"code": "FINAL_STATUS_ENUM_LEAK", "message": "Remove final-status enum values from generated planning artifacts before guarded execution.", "target": "generated planning artifacts"})
    if protected_name_findings:
        repair_hints.append({"code": "PROTECTED_STATUS_ARTIFACT_NAME", "message": "Remove protected status artifact filenames from generated planning artifacts before guarded execution.", "target": "generated planning artifacts"})
    if output_errors:
        repair_hints.append({"code": "PROTECTED_OUTPUT_PATH", "message": "Move preflight outputs away from protected status artifact names.", "target": "preflight output paths"})
    if stage3_checked and not stage3_ok:
        repair_hints.append({"code": "STAGE3_PREFLIGHT", "message": "Provide a passing Stage 3 runtime preflight report before guarded execution handoff.", "target": "--stage3-preflight-report"})

    source_reports = {}
    if stage3_preflight_path is not None:
        source_reports["stage3_runtime_preflight_report"] = rel_path(stage3_preflight_path)

    report = {
        "schema_version": "planning_efficiency_v2_preflight_report_v1",
        "status": status,
        "authority": v2.REQUIRED_AUTHORITY,
        "source_goal": rel_path(goal_path or DEFAULT_GOAL),
        "outputs": {
            "plan": rel_path(plan_output),
            "expected_artifacts": rel_path(expected_output),
            "compile_report": rel_path(compile_report_output),
            "lint_report": rel_path(lint_report_output),
            "preflight_report": rel_path(preflight_report_output),
        },
        "criteria": checks,
        "repair_hints": repair_hints,
        "generated_hashes": generated_hashes,
        "planning_efficiency": {
            "compiled_action_count": compile_report.get("planning_efficiency", {}).get("compiled_action_count", 0),
            "declared_artifact_count": compile_report.get("planning_efficiency", {}).get("declared_artifact_count", 0),
            "lint_status": (lint_report or {}).get("status", "NOT_RUN"),
            "criteria_passed": sum(1 for check in checks if check["status"] == "PASS"),
            "criteria_total": len(checks),
            "ready_for_guarded_execution": status == PASS_STATUS,
        },
        "source_reports": source_reports,
        "execution_gate": {
            "planning_preflight_passed": status == PASS_STATUS,
            "stage3_runtime_preflight_checked": stage3_checked,
            "may_pass_plan_to_guarded_execution": status == PASS_STATUS,
            "guarded_execution_inputs": {
                "plan": rel_path(plan_output),
                "expected_artifacts": rel_path(expected_output),
            },
            "blocked_before_execution": status != PASS_STATUS,
            "required_next_runtime": "guarded_execution_v2",
            "runtime_module": ".agentic-pi/runtime/guarded_execution_v2.py",
        },
        "runtime_execution": {
            "goal_execution_attempted": False,
            "plan_execution_attempted": False,
            "guarded_execution_invoked": False,
            "status_authority": "certifier_only",
            "requires_policy_certifier_for_status": True,
            "can_certify_done": False,
        },
        "claim_boundary": "Planning Efficiency v2 preflight wires compiler/linter outputs into guarded execution inputs before runtime. It does not execute goals, decide policy, certify DONE, or prove arbitrary runtime safety.",
    }
    return plan, expected, compile_report, lint_report, report


def validate_preflight_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "planning_efficiency_v2_preflight_report_v1":
        errors.append("schema_version must be planning_efficiency_v2_preflight_report_v1")
    if report.get("authority") != v2.REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    if v2.contains_final_status_value(report):
        errors.append("planning efficiency v2 preflight report must not contain final status enum values")
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
    if runtime.get("requires_policy_certifier_for_status") is not True:
        errors.append("runtime_execution.requires_policy_certifier_for_status must be true")
    if runtime.get("can_certify_done") is not False:
        errors.append("runtime_execution.can_certify_done must be false")
    execution_gate = report.get("execution_gate", {})
    source_reports = report.get("source_reports", {})
    if "stage3_runtime_preflight_report" in source_reports and execution_gate.get("stage3_runtime_preflight_checked") is not True:
        errors.append("stage3_runtime_preflight_checked must be true when source report is recorded")
    if execution_gate.get("required_next_runtime") not in {"guarded_execution_v2", "guarded_execution_v2_or_v3"}:
        errors.append("required_next_runtime must name a guarded execution runtime")
    if report.get("status") == PASS_STATUS:
        if execution_gate.get("may_pass_plan_to_guarded_execution") is not True:
            errors.append("passing preflight must allow passing plan to guarded execution")
        if execution_gate.get("blocked_before_execution") is not False:
            errors.append("passing preflight must not be marked blocked_before_execution")
    if report.get("status") == FAIL_STATUS and not report.get("repair_hints"):
        errors.append("failing preflight reports must include repair_hints")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Planning Efficiency v2 preflight without executing the compiled plan.")
    parser.add_argument("--goal", default=str(DEFAULT_GOAL))
    parser.add_argument("--plan-output", default=str(DEFAULT_PLAN_OUTPUT))
    parser.add_argument("--expected-output", default=str(DEFAULT_EXPECTED_OUTPUT))
    parser.add_argument("--compile-report-output", default=str(DEFAULT_COMPILE_REPORT_OUTPUT))
    parser.add_argument("--lint-report-output", default=str(DEFAULT_LINT_REPORT_OUTPUT))
    parser.add_argument("--output", default=str(DEFAULT_PREFLIGHT_REPORT_OUTPUT))
    parser.add_argument("--stage3-preflight-report")
    args = parser.parse_args(argv)

    try:
        plan_output = Path(args.plan_output)
        expected_output = Path(args.expected_output)
        compile_report_output = Path(args.compile_report_output)
        lint_report_output = Path(args.lint_report_output)
        preflight_report_output = Path(args.output)
        goal_path = Path(args.goal)
        stage3_preflight_path = Path(args.stage3_preflight_report) if args.stage3_preflight_report else None
        stage3_preflight = load_required_json(stage3_preflight_path, "Stage 3 preflight report") if stage3_preflight_path else None
        plan, expected, compile_report, lint_report, report = build_preflight(
            load_required_json(goal_path, "goal"),
            plan_output,
            expected_output,
            compile_report_output,
            lint_report_output,
            preflight_report_output,
            goal_path,
            stage3_preflight,
            stage3_preflight_path,
        )
        errors = validate_preflight_report(report)
        write_json(compile_report_output, compile_report)
        if report["status"] == PASS_STATUS and plan is not None and expected is not None and lint_report is not None:
            write_json(plan_output, plan)
            write_json(expected_output, expected)
            write_json(lint_report_output, lint_report)
        write_json(preflight_report_output, report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report["status"] != PASS_STATUS:
        for repair_hint in report.get("repair_hints", []):
            print(f"HINT: {repair_hint['code']}: {repair_hint['message']}", file=sys.stderr)
        return 1
    print(f"OK: {report['status']} ({report['planning_efficiency']['criteria_total']} checks) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
