#!/usr/bin/env python3
"""Guarded plan compiler.

The compiler turns a small rough-goal specification into the exact bounded plan
and expected-artifacts contract consumed by guarded execution. It then runs the
plan linter immediately, so planning errors are caught before runtime execution.

This is a planning-efficiency tool only. It does not execute plans, decide
policy, or certify completion.
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
import guarded_plan_linter as linter


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOAL = ROOT / ".agentic-pi" / "runtime" / "planning_efficiency_v1_goal.json"
DEFAULT_PLAN_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v1_plan.json"
DEFAULT_EXPECTED_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v1_expected_artifacts.json"
DEFAULT_COMPILE_REPORT_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v1_compile_report.json"
DEFAULT_LINT_REPORT_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v1_lint_report.json"
SLUG_RE = re.compile(r"[^a-z0-9_]+")


def load_required_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} missing: {path}")
    data = v2.load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return data


def write_json(path: Path, data: Any) -> None:
    canonical_json.write_json_canonical(path, data, v2.is_protected_output_name)


def slugify(value: str, fallback: str) -> str:
    slug = SLUG_RE.sub("_", value.lower()).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or fallback


def safe_artifact_path(raw_path: str, label: str) -> tuple[str, list[str]]:
    errors: list[str] = []
    normalized = raw_path.replace("\\", "/")
    try:
        v2.resolve_artifact_path(Path("/tmp/guarded-plan-compiler"), normalized)
    except ValueError as exc:
        errors.append(f"{label}: {exc}")
    return normalized, errors


def default_artifact_specs(goal: dict[str, Any]) -> list[dict[str, Any]]:
    rough_goal = str(goal.get("rough_goal", "bounded planning task")).strip() or "bounded planning task"
    return [
        {
            "artifact_id": "A.PLAN_SUMMARY",
            "name": "plan_summary",
            "content": f"Summary artifact for the bounded planning task: {rough_goal[:180]}",
        },
        {
            "artifact_id": "A.PLAN_STEPS",
            "name": "plan_steps",
            "content": "Plan steps artifact produced by the compiler for guarded execution compatibility.",
        },
        {
            "artifact_id": "A.PLAN_BOUNDARY",
            "name": "plan_boundary",
            "content": "Boundary artifact states this plan is advisory evidence text and not a policy decision.",
        },
    ]


def verifier_requirements() -> list[str]:
    return [
        "every action path matches expected_artifacts exactly",
        "no protected status artifact is targeted",
        "no arbitrary command shape is present",
        "action count remains within guarded execution budget",
        "artifact content contains no completion-authority language",
        "policy and certifier remain responsible for final status",
    ]


def hint(code: str, message: str, target: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "target": target}


def dedupe_repair_hints(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, str]] = []
    for item in items:
        key = (str(item.get("code", "")), str(item.get("message", "")), str(item.get("target", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"code": key[0], "message": key[1], "target": key[2]})
    return deduped


def compile_goal(goal: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    errors: list[str] = []
    repair_hints: list[dict[str, str]] = []
    if goal.get("schema_version") != "planning_efficiency_goal_v1":
        message = "goal schema_version must be planning_efficiency_goal_v1"
        errors.append(message)
        repair_hints.append(hint("GOAL_SCHEMA", message, "goal.schema_version"))
    rough_goal = str(goal.get("rough_goal", "")).strip()
    if not rough_goal:
        message = "rough_goal must be a non-empty string"
        errors.append(message)
        repair_hints.append(hint("MISSING_ROUGH_GOAL", message, "goal.rough_goal"))
    if v2.contains_forbidden_content_language(rough_goal):
        message = "rough_goal contains final-status authority language"
        errors.append(message)
        repair_hints.append(hint("AUTHORITY_LANGUAGE", message, "goal.rough_goal"))
    specs = goal.get("artifact_specs")
    if specs is None:
        specs = default_artifact_specs(goal)
    if not isinstance(specs, list):
        message = "artifact_specs must be a list when provided"
        errors.append(message)
        repair_hints.append(hint("ARTIFACT_SPECS_SHAPE", message, "goal.artifact_specs"))
        specs = []
    if len(specs) < v2.MIN_ACTIONS:
        message = f"artifact_specs must provide at least {v2.MIN_ACTIONS} artifacts"
        errors.append(message)
        repair_hints.append(hint("ACTION_BUDGET", message, "goal.artifact_specs"))
    if len(specs) > v2.MAX_ACTIONS:
        message = f"artifact_specs must provide at most {v2.MAX_ACTIONS} artifacts"
        errors.append(message)
        repair_hints.append(hint("ACTION_BUDGET", message, "goal.artifact_specs"))

    actions: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, raw_spec in enumerate(specs):
        if not isinstance(raw_spec, dict):
            message = f"artifact_specs[{index}] must be an object"
            errors.append(message)
            repair_hints.append(hint("ARTIFACT_SPECS_SHAPE", message, f"goal.artifact_specs[{index}]"))
            continue
        name = str(raw_spec.get("name") or raw_spec.get("artifact_id") or f"artifact_{index + 1}")
        artifact_id = str(raw_spec.get("artifact_id") or f"A.{slugify(name, f'artifact_{index + 1}').upper()}")
        if artifact_id in seen_ids:
            message = f"duplicate artifact_id: {artifact_id}"
            errors.append(message)
            repair_hints.append(hint("DUPLICATE_ARTIFACT_ID", message, f"goal.artifact_specs[{index}].artifact_id"))
        seen_ids.add(artifact_id)
        requested_path = raw_spec.get("requested_path")
        if requested_path is None:
            artifact_path = f"artifacts/{slugify(name, f'artifact_{index + 1}')}.txt"
        elif isinstance(requested_path, str) and requested_path.strip():
            artifact_path = requested_path
        else:
            message = f"artifact {artifact_id} requested_path must be a non-empty string when supplied"
            errors.append(message)
            repair_hints.append(hint("EXPECTED_ARTIFACTS_CONTRACT", message, f"goal.artifact_specs[{index}].requested_path"))
            artifact_path = f"artifacts/{slugify(name, f'artifact_{index + 1}')}.txt"
        artifact_path, path_errors = safe_artifact_path(artifact_path, f"artifact {artifact_id}")
        errors.extend(path_errors)
        for path_error in path_errors:
            code = "PROTECTED_PATH" if "protected status artifact" in path_error else "EXPECTED_ARTIFACTS_CONTRACT"
            repair_hints.append(hint(code, path_error, f"goal.artifact_specs[{index}].requested_path"))
        if artifact_path in seen_paths:
            message = f"duplicate artifact path: {artifact_path}"
            errors.append(message)
            repair_hints.append(hint("DUPLICATE_ARTIFACT_PATH", message, f"goal.artifact_specs[{index}].requested_path"))
        seen_paths.add(artifact_path)
        content = str(raw_spec.get("content", "")).strip()
        if not content:
            content = f"Compiled artifact for {name} in the bounded planning task."
        if v2.contains_forbidden_content_language(content):
            message = f"artifact {artifact_id} content contains final-status authority language"
            errors.append(message)
            repair_hints.append(hint("AUTHORITY_LANGUAGE", message, f"goal.artifact_specs[{index}].content"))
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > 2000:
            message = f"artifact {artifact_id} content exceeds 2000 bytes"
            errors.append(message)
            repair_hints.append(hint("CONTENT_TOO_LARGE", message, f"goal.artifact_specs[{index}].content"))
        artifacts.append({
            "artifact_id": artifact_id,
            "expected_path": artifact_path,
            "required": True,
            "allowed_actions": [v2.SAFE_ACTION_TYPE],
            "min_size_bytes": max(1, min(content_bytes, 20)),
            "max_size_bytes": max(1000, content_bytes),
        })
        actions.append({
            "action_id": f"A.WRITE_{slugify(artifact_id, f'artifact_{index + 1}').upper()}",
            "action_type": v2.SAFE_ACTION_TYPE,
            "artifact_id": artifact_id,
            "artifact_path": artifact_path,
            "content": content,
        })

    expected = {
        "schema_version": "guarded_execution_v2_expected_artifacts_v1",
        "artifacts": artifacts,
    }
    plan = {
        "schema_version": "guarded_execution_v2_plan_v1",
        "plan_id": str(goal.get("goal_id") or "planning_efficiency_v1_compiled_plan"),
        "planning_metadata": {
            "compiler": "guarded_plan_compiler_v1",
            "verifier_evidence_required": True,
            "required_verifier_checks": verifier_requirements(),
            "claim_boundary": "Compiled plan is a pre-execution planning artifact only; policy and certifier retain final status authority.",
        },
        "actions": actions,
    }
    lint_report = linter.lint_plan(plan, expected) if not errors else None
    if lint_report and lint_report.get("status") != "PLAN_LINT_PASS":
        repair_hints.extend(lint_report.get("repair_hints", []))
        errors.extend(item["message"] for item in lint_report.get("repair_hints", []))
    repair_hints = dedupe_repair_hints(repair_hints)
    status = "PLAN_COMPILE_PASS" if not errors else "PLAN_COMPILE_FAIL"
    compile_report = {
        "schema_version": "guarded_plan_compile_report_v1",
        "status": status,
        "authority": v2.REQUIRED_AUTHORITY,
        "goal_id": str(goal.get("goal_id") or "planning_efficiency_v1_compiled_plan"),
        "outputs": {
            "plan": "planning_efficiency_v1_plan.json",
            "expected_artifacts": "planning_efficiency_v1_expected_artifacts.json",
            "lint_report": "planning_efficiency_v1_lint_report.json",
        },
        "compiler_checks": [
            {"check_id": "rough_goal_valid", "status": "PASS" if rough_goal and not v2.contains_forbidden_content_language(rough_goal) else "FAIL"},
            {"check_id": "artifact_specs_budget", "status": "PASS" if v2.MIN_ACTIONS <= len(specs) <= v2.MAX_ACTIONS else "FAIL"},
            {"check_id": "compiled_plan_lints", "status": "PASS" if lint_report and lint_report.get("status") == "PLAN_LINT_PASS" else "FAIL"},
        ],
        "compile_errors": errors,
        "repair_hints": repair_hints,
        "planning_efficiency": {
            "compiled_action_count": len(actions),
            "declared_artifact_count": len(artifacts),
            "lint_status": lint_report.get("status") if lint_report else "NOT_RUN",
            "repair_hint_count": len(repair_hints),
            "ready_for_guarded_execution": status == "PLAN_COMPILE_PASS",
        },
        "runtime_execution": {
            "goal_execution_attempted": False,
            "plan_execution_attempted": False,
            "status_authority": "certifier_only",
            "requires_policy_certifier_for_status": True,
            "can_certify_done": False,
        },
        "claim_boundary": "Plan compilation improves planning proficiency and efficiency by producing guarded-execution-compatible plans before runtime. It does not execute goals, decide policy, certify DONE, or prove arbitrary runtime safety.",
    }
    return (plan if status == "PLAN_COMPILE_PASS" else None), (expected if status == "PLAN_COMPILE_PASS" else None), compile_report


def validate_compile_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "guarded_plan_compile_report_v1":
        errors.append("schema_version must be guarded_plan_compile_report_v1")
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
    if report.get("status") == "PLAN_COMPILE_FAIL" and not report.get("compile_errors"):
        errors.append("failing compile reports must include compile_errors")
    repair_hints = report.get("repair_hints", [])
    if report.get("status") == "PLAN_COMPILE_FAIL" and not repair_hints:
        errors.append("failing compile reports must include repair_hints")
    if repair_hints is not None:
        if not isinstance(repair_hints, list):
            errors.append("repair_hints must be a list")
        else:
            for index, item in enumerate(repair_hints):
                if not isinstance(item, dict):
                    errors.append(f"repair_hints[{index}] must be an object")
                    continue
                for key in ["code", "message", "target"]:
                    if not isinstance(item.get(key), str):
                        errors.append(f"repair_hints[{index}].{key} must be a string")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile a rough goal into a guarded execution plan and lint it.")
    parser.add_argument("--goal", default=str(DEFAULT_GOAL))
    parser.add_argument("--plan-output", default=str(DEFAULT_PLAN_OUTPUT))
    parser.add_argument("--expected-output", default=str(DEFAULT_EXPECTED_OUTPUT))
    parser.add_argument("--compile-report-output", default=str(DEFAULT_COMPILE_REPORT_OUTPUT))
    parser.add_argument("--lint-report-output", default=str(DEFAULT_LINT_REPORT_OUTPUT))
    args = parser.parse_args(argv)
    try:
        plan, expected, compile_report = compile_goal(load_required_json(Path(args.goal), "goal"))
        errors = validate_compile_report(compile_report)
        write_json(Path(args.compile_report_output), compile_report)
        if plan is not None and expected is not None:
            lint_report = linter.lint_plan(plan, expected)
            lint_errors = linter.validate_lint_report(lint_report)
            errors.extend(lint_errors)
            write_json(Path(args.plan_output), plan)
            write_json(Path(args.expected_output), expected)
            write_json(Path(args.lint_report_output), lint_report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if compile_report["status"] != "PLAN_COMPILE_PASS":
        for error in compile_report.get("compile_errors", []):
            print(f"HINT: {error}", file=sys.stderr)
        return 1
    print(f"OK: {compile_report['status']} ({compile_report['planning_efficiency']['compiled_action_count']} actions) -> {args.plan_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
