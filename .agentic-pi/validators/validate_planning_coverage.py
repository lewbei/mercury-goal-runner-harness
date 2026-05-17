#!/usr/bin/env python3
"""Validate planning_coverage.json.

This is a planning-quality gate, not certification. It rejects artifacts that
claim exhaustive planning or final-status authority, and checks that planning
coverage records alternatives, assumptions, risks, verifier handoff, ask-user
triggers, and false-DONE traps.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / ".agentic-pi" / "schemas" / "planning_coverage.schema.json"
VALIDATE_SCHEMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
FORBIDDEN_STATUS_VALUES = {"DONE_PASS", "DONE_FAIL", "NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_planning_coverage", VALIDATE_SCHEMA_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def path_to_run_dir(path: Path) -> Path:
    if path.is_dir():
        return path
    return path.parent


def recursively_find_forbidden_status_values(value: Any, loc: str = "$", errors: list[str] | None = None) -> list[str]:
    if errors is None:
        errors = []
    if isinstance(value, dict):
        for key, child in value.items():
            recursively_find_forbidden_status_values(child, f"{loc}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            recursively_find_forbidden_status_values(child, f"{loc}[{index}]", errors)
    elif isinstance(value, str) and value in FORBIDDEN_STATUS_VALUES:
        errors.append(f"{loc}: planning coverage must not contain final status value {value!r}")
    return errors


def expected_artifact_paths(run_dir: Path) -> set[str]:
    path = run_dir / "expected_artifacts.json"
    if not path.is_file():
        return set()
    expected = load_json(path)
    paths = set()
    for item in expected.get("artifacts", []):
        if isinstance(item, dict) and isinstance(item.get("expected_path"), str):
            paths.add(item["expected_path"])
    return paths


def goal_final_outputs(run_dir: Path) -> set[str]:
    path = run_dir / "goal_contract.json"
    if not path.is_file():
        return set()
    goal = load_json(path)
    return {str(item) for item in goal.get("final_outputs", []) if str(item).strip()}


def validate_planning_coverage(data: dict, *, run_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    validator = load_schema_validator()
    schema_errors = validator.validate(data, load_json(SCHEMA_PATH))
    errors.extend(f"schema: {item}" for item in schema_errors)
    if schema_errors:
        return errors

    authority = data["authority"]
    if authority.get("can_certify_done") is not False:
        errors.append("authority.can_certify_done must be false")
    if authority.get("claim_exhaustive_planning") is not False:
        errors.append("authority.claim_exhaustive_planning must be false")
    if authority.get("claim_correctness") is not False:
        errors.append("authority.claim_correctness must be false")
    if authority.get("final_status_authority") != "certifier_only":
        errors.append("final_status_authority must be certifier_only")

    proof_boundary = data["proof_boundary"]
    if proof_boundary.get("proof_scope") != "planning_coverage_only":
        errors.append("proof_boundary.proof_scope must be planning_coverage_only")
    if proof_boundary.get("proves_all_possible_plans") is not False:
        errors.append("proof_boundary.proves_all_possible_plans must be false")
    if proof_boundary.get("proves_artifact_correctness") is not False:
        errors.append("proof_boundary.proves_artifact_correctness must be false")
    for required_gate in ["requires_worker_execution", "requires_verifier_artifacts", "requires_policy_engine", "requires_certifier"]:
        if proof_boundary.get(required_gate) is not True:
            errors.append(f"proof_boundary.{required_gate} must be true")

    alternatives = data["alternatives_considered"]
    selected = [item for item in alternatives if item.get("status") == "selected"]
    non_selected = [item for item in alternatives if item.get("status") in {"rejected", "deferred", "blocked", "need_user"}]
    if len(selected) != 1:
        errors.append(f"expected exactly one selected alternative, found {len(selected)}")
    if not non_selected:
        errors.append("expected at least one rejected/deferred/blocked/need_user alternative")
    if data["search_budget"].get("rejected_or_deferred_count", 0) != len(non_selected):
        errors.append("search_budget.rejected_or_deferred_count must match non-selected alternatives")
    if data["search_budget"].get("search_completeness_claim") != "bounded_not_exhaustive":
        errors.append("search_budget must claim bounded_not_exhaustive, not exhaustive planning")

    option_ids = [item.get("option_id") for item in alternatives]
    if len(option_ids) != len(set(option_ids)):
        errors.append("alternatives_considered option_id values must be unique")

    coverage_checks = data["coverage_checks"]
    check_by_id = {item.get("check_id"): item for item in coverage_checks}
    required_checks = {
        "C.AUTHORITY_BOUNDARY",
        "C.CORRECTNESS_BOUNDARY",
        "C.ALTERNATIVES_RECORDED",
        "C.REJECTED_OR_DEFERRED_RECORDED",
        "C.CONSTRAINTS_CAPTURED",
        "C.RISKS_CAPTURED",
        "C.VERIFIER_HANDOFF_RECORDED",
        "C.FALSE_DONE_TRAPS_RECORDED",
        "C.ASK_USER_TRIGGERS_RECORDED",
    }
    missing_checks = sorted(required_checks - set(check_by_id))
    if missing_checks:
        errors.append(f"missing coverage checks: {missing_checks}")
    failing_checks = sorted(
        item.get("check_id") for item in coverage_checks if item.get("status") == "FAIL"
    )
    if failing_checks:
        errors.append(f"coverage checks failed: {failing_checks}")

    if not data["goal_coverage"].get("constraints"):
        errors.append("goal_coverage.constraints must not be empty")
    if not data["risk_register"]:
        errors.append("risk_register must not be empty")
    if not data["false_done_traps"]:
        errors.append("false_done_traps must not be empty")
    if not data["ask_user_triggers"]:
        errors.append("ask_user_triggers must not be empty")

    verifier_requirements = data["verification_strategy"].get("verifier_requirements", [])
    if not verifier_requirements:
        errors.append("verification_strategy.verifier_requirements must not be empty")
    policy_boundary = data["verification_strategy"].get("policy_boundary", "")
    if "certify_run.py" not in policy_boundary and "policy_engine.py" not in policy_boundary:
        errors.append("verification_strategy.policy_boundary must name policy_engine.py or certify_run.py")

    errors.extend(recursively_find_forbidden_status_values(data))

    if run_dir is not None:
        source_map = {item["path"]: item for item in data["source_artifacts"]}
        for rel_path, item in source_map.items():
            exists = (run_dir / rel_path).is_file()
            if item.get("exists") != exists:
                errors.append(f"source_artifacts exists mismatch for {rel_path}")
            if item.get("required") is True and not exists:
                errors.append(f"required source artifact missing: {rel_path}")

        final_outputs = goal_final_outputs(run_dir)
        if final_outputs:
            covered_outputs = set(data["goal_coverage"].get("final_outputs", []))
            missing = sorted(final_outputs - covered_outputs)
            if missing:
                errors.append(f"goal final_outputs missing from coverage: {missing}")

        expected_paths = expected_artifact_paths(run_dir)
        if expected_paths:
            verifier_paths = set(data["verification_strategy"].get("expected_artifacts", []))
            missing = sorted(expected_paths - verifier_paths)
            if missing:
                errors.append(f"expected_artifacts paths missing from verification strategy: {missing}")

        selected_path = run_dir / "selected_strategy.json"
        decision_path = run_dir / "strategy_decision.json"
        if selected_path.is_file() and decision_path.is_file():
            selected_doc = load_json(selected_path)
            decision_doc = load_json(decision_path)
            expected_selected = decision_doc.get("selected_strategy") or selected_doc.get("strategy_id")
            selected_ids = [item.get("option_id") for item in selected]
            if expected_selected and selected_ids != [expected_selected]:
                errors.append("selected alternative does not match strategy decision")

    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate planning_coverage.json")
    parser.add_argument("path", help="planning_coverage.json path or run directory")
    args = parser.parse_args(argv)
    path = Path(args.path)
    coverage_path = path / "planning_coverage.json" if path.is_dir() else path
    if not coverage_path.is_file():
        print(f"PLANNING_COVERAGE_INVALID: file missing: {coverage_path}")
        return 1
    try:
        data = load_json(coverage_path)
        errors = validate_planning_coverage(data, run_dir=path_to_run_dir(coverage_path))
    except Exception as exc:
        print(f"PLANNING_COVERAGE_INVALID: {exc}")
        return 1
    if errors:
        print("PLANNING_COVERAGE_INVALID")
        for item in errors:
            print(f"- {item}")
        return 1
    print("PLANNING_COVERAGE_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
