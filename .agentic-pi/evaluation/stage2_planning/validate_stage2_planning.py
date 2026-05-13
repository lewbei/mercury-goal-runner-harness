#!/usr/bin/env python3
"""Validate deterministic Stage 2 planning-gate fixtures and score reports."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage2_planning"
SCHEMA_PATH = DEFAULT_DIR / "stage2_planning_eval.schema.json"
VALIDATE_SCHEMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
MODES = {"normal_planning", "bounded_multi_plan_gate"}
FORBIDDEN_STATUS_VALUES = {"CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"}
PROTECTED_STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}
INVISIBLE_CODEPOINTS = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_stage2_planning", VALIDATE_SCHEMA_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(ch for ch in normalized if ch not in INVISIBLE_CODEPOINTS and unicodedata.category(ch) != "Cf")


def scan_status_values(value: Any, errors: list[str], loc: str = "$") -> None:
    if isinstance(value, dict):
        if value.get("can_certify_done") is True:
            errors.append(f"{loc}.can_certify_done: Stage 2 planning evaluation cannot certify DONE")
        for key, child in value.items():
            scan_status_values(child, errors, f"{loc}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            scan_status_values(child, errors, f"{loc}[{index}]")
        return
    if not isinstance(value, str):
        return
    cleaned = clean_text(value)
    for status in FORBIDDEN_STATUS_VALUES:
        if re.search(rf"\b{re.escape(status)}\b", cleaned, flags=re.IGNORECASE):
            errors.append(f"{loc}: Stage 2 planning evaluation must not contain final status value {status!r}")


def normalize_items(items: list[str]) -> set[str]:
    return {" ".join(str(item).lower().split()) for item in items}


def missing_expected(found: list[str], expected: list[str]) -> list[str]:
    found_set = normalize_items(found)
    return [item for item in expected if " ".join(str(item).lower().split()) not in found_set]


def score_in_range(value: Any) -> bool:
    return isinstance(value, (int, float)) and 0 <= float(value) <= 1


def path_is_unsafe(path_value: str) -> bool:
    path = Path(path_value)
    return path.is_absolute() or ".." in path.parts or path.name in PROTECTED_STATUS_ARTIFACTS


def validate_prompt_set(prompt_set: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if prompt_set.get("schema_version") != "stage2_planning_prompt_set_v1":
        errors.append("prompt_set.schema_version must be stage2_planning_prompt_set_v1")
    if prompt_set.get("authority", {}).get("can_certify_done") is not False:
        errors.append("prompt_set.authority.can_certify_done must be false")
    if set(prompt_set.get("mode_pair", [])) != MODES:
        errors.append("prompt_set.mode_pair must be normal_planning and bounded_multi_plan_gate")
    prompts = prompt_set.get("prompts")
    if not isinstance(prompts, list) or len(prompts) != 10:
        errors.append("prompt_set.prompts must contain exactly 10 planning benchmark cases")
        return errors
    seen_ids: set[str] = set()
    seen_prompts: set[str] = set()
    category_counts: dict[str, int] = {}
    required_lists = [
        "expected_assumptions",
        "expected_unknowns",
        "expected_risks",
        "expected_bad_plans_to_reject",
        "expected_evidence_requirements",
        "expected_forbidden_paths",
        "expected_validation_commands",
        "expected_dependencies",
        "expected_files",
    ]
    for prompt in prompts:
        case_id = prompt.get("case_id")
        if not case_id or case_id in seen_ids:
            errors.append(f"case_id must be unique and non-empty, got {case_id!r}")
        seen_ids.add(case_id)
        prompt_text = prompt.get("prompt")
        if not prompt_text or prompt_text in seen_prompts:
            errors.append(f"prompt text must be unique and non-empty for {case_id!r}")
        seen_prompts.add(prompt_text)
        category = prompt.get("category")
        if not category:
            errors.append(f"prompt {case_id}: category is required")
        else:
            category_counts[category] = category_counts.get(category, 0) + 1
        if not isinstance(prompt.get("expected_candidate_plan_min"), int) or prompt["expected_candidate_plan_min"] < 2:
            errors.append(f"prompt {case_id}: expected_candidate_plan_min must be integer >= 2")
        for field in required_lists:
            if not isinstance(prompt.get(field), list) or not prompt[field]:
                errors.append(f"prompt {case_id}: {field} must be a non-empty list")
    if prompt_set.get("category_distribution") != category_counts:
        errors.append(f"prompt_set.category_distribution mismatch: expected observed {category_counts}, got {prompt_set.get('category_distribution')}")
    scan_status_values(prompt_set, errors, "prompt_set")
    return errors


def validate_response_fixtures(prompt_set: dict[str, Any], responses: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if responses.get("schema_version") != "stage2_planning_response_fixtures_v1":
        errors.append("response_fixtures.schema_version must be stage2_planning_response_fixtures_v1")
    if responses.get("authority", {}).get("can_certify_done") is not False:
        errors.append("response_fixtures.authority.can_certify_done must be false")
    prompts = {prompt["case_id"]: prompt for prompt in prompt_set.get("prompts", [])}
    by_case: dict[str, set[str]] = {case_id: set() for case_id in prompts}
    for response in responses.get("responses", []):
        case_id = response.get("case_id")
        mode = response.get("mode")
        loc = f"response {case_id}/{mode}"
        if case_id not in prompts:
            errors.append(f"response references unknown case_id {case_id!r}")
            continue
        if mode not in MODES:
            errors.append(f"{loc}: invalid mode {mode!r}")
            continue
        if mode in by_case[case_id]:
            errors.append(f"response {case_id}: duplicate mode {mode}")
        by_case[case_id].add(mode)
        prompt = prompts[case_id]
        for field in ["candidate_plans_found", "assumptions_found", "unknowns_found", "risks_found", "rejected_bad_plans_found", "evidence_requirements_found", "forbidden_paths_detected", "validation_commands", "dependencies_found"]:
            if not isinstance(response.get(field), list):
                errors.append(f"{loc}: {field} must be a list")
        for field in ["execution_readiness_score", "implementation_specificity_score", "validation_specificity_score", "fake_done_resistance_score"]:
            if not score_in_range(response.get(field)):
                errors.append(f"{loc}: {field} must be a number in [0, 1]")
        selected = response.get("selected_plan", {})
        if selected.get("status") not in {"SELECTED", "NEED_USER", "BLOCKED"}:
            errors.append(f"{loc}: selected_plan.status must be SELECTED, NEED_USER, or BLOCKED")
        if not selected.get("summary"):
            errors.append(f"{loc}: selected_plan.summary must be non-empty")
        for flag in ["touches_forbidden_path", "claims_final_status_authority", "claims_exhaustive_search", "claims_correctness_without_evidence"]:
            if selected.get(flag) is not False:
                errors.append(f"{loc}: selected_plan.{flag} must be false")
        intended_files = selected.get("intended_files", [])
        if not isinstance(intended_files, list) or not intended_files:
            errors.append(f"{loc}: selected_plan.intended_files must be a non-empty list")
        else:
            for item in intended_files:
                if path_is_unsafe(str(item)):
                    errors.append(f"{loc}: selected_plan.intended_files contains unsafe or protected path {item!r}")
            forbidden_overlap = normalize_items(intended_files) & normalize_items(prompt["expected_forbidden_paths"])
            if forbidden_overlap:
                errors.append(f"{loc}: selected_plan.intended_files intersects forbidden paths {sorted(forbidden_overlap)}")
        if mode == "bounded_multi_plan_gate":
            if len(response["candidate_plans_found"]) < prompt["expected_candidate_plan_min"]:
                errors.append(f"{loc}: candidate_plans_found below expected minimum")
            checks = [
                ("assumptions_found", "expected_assumptions"),
                ("unknowns_found", "expected_unknowns"),
                ("risks_found", "expected_risks"),
                ("rejected_bad_plans_found", "expected_bad_plans_to_reject"),
                ("evidence_requirements_found", "expected_evidence_requirements"),
                ("forbidden_paths_detected", "expected_forbidden_paths"),
                ("validation_commands", "expected_validation_commands"),
                ("dependencies_found", "expected_dependencies"),
            ]
            for found_field, expected_field in checks:
                missing = missing_expected(response[found_field], prompt[expected_field])
                if missing:
                    errors.append(f"{loc}: {found_field} missing expected items {missing}")
    for case_id, modes in by_case.items():
        if modes != MODES:
            errors.append(f"case {case_id}: expected exactly modes {sorted(MODES)}, got {sorted(modes)}")
    scan_status_values(responses, errors, "response_fixtures")
    return errors


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_validator = load_schema_validator()
    errors.extend(f"schema: {item}" for item in schema_validator.validate(report, load_json(SCHEMA_PATH)))
    scan_status_values(report, errors, "report")
    if errors:
        return errors
    prompt_count = report["prompt_count"]
    if prompt_count != 10:
        errors.append("report.prompt_count must be exactly 10")
    if len(report["prompt_results"]) != prompt_count:
        errors.append("report.prompt_results length must match prompt_count")
    actual_wins = sum(1 for item in report["prompt_results"] if item["bounded_multi_plan_gate_beats_normal"])
    gate = report["starter_gate"]
    if gate["actual_prompt_wins"] != actual_wins:
        errors.append("starter_gate.actual_prompt_wins does not match prompt results")
    expected_status = "STARTER_GATE_PASS" if (
        actual_wins >= gate["required_prompt_wins"]
        and gate["actual_bad_plan_rejection_relative_improvement"] >= gate["minimum_bad_plan_rejection_relative_improvement"]
        and gate["actual_evidence_requirement_recall_relative_improvement"] >= gate["minimum_evidence_requirement_recall_relative_improvement"]
        and gate["forbidden_path_detection_not_regressed"]
        and gate["validation_specificity_not_regressed"]
        and gate["implementation_specificity_not_reduced"]
    ) else "STARTER_GATE_FAIL"
    if gate["status"] != expected_status:
        errors.append(f"starter_gate.status must be {expected_status}, got {gate['status']}")
    if report["authority"].get("can_certify_done") is not False:
        errors.append("report.authority.can_certify_done must be false")
    return errors


def validate_all(prompt_set_path: Path, responses_path: Path, report_path: Path | None) -> list[str]:
    prompt_set = load_json(prompt_set_path)
    responses = load_json(responses_path)
    errors = []
    errors.extend(validate_prompt_set(prompt_set))
    errors.extend(validate_response_fixtures(prompt_set, responses))
    if report_path is not None:
        errors.extend(validate_report(load_json(report_path)))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate deterministic Stage 2 planning evaluation artifacts")
    parser.add_argument("--prompt-set", default=str(DEFAULT_DIR / "planning_prompt_set.json"))
    parser.add_argument("--responses", default=str(DEFAULT_DIR / "planning_response_fixtures.json"))
    parser.add_argument("--report", default=str(DEFAULT_DIR / "stage2_planning_score_report.json"))
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)
    report_path = None if args.no_report else Path(args.report)
    errors = validate_all(Path(args.prompt_set), Path(args.responses), report_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: stage2 planning evaluation valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
