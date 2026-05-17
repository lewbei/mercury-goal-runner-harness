#!/usr/bin/env python3
"""Validate adaptive_research_inputs.json.

This is a deterministic planning-input gate. It validates saved adaptive or
nondeterministic research provenance without performing network fetches and
rejects any attempt to turn research into final-status authority.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / ".agentic-pi" / "schemas" / "adaptive_research_inputs.schema.json"
VALIDATE_SCHEMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}
FORBIDDEN_STATUS_VALUES = {"DONE_PASS", "DONE_FAIL", "NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_adaptive_research_inputs", VALIDATE_SCHEMA_PATH)
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
            # The policy is allowed to name forbidden artifact file paths, but
            # not final status lattice values.
            recursively_find_forbidden_status_values(child, f"{loc}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            recursively_find_forbidden_status_values(child, f"{loc}[{index}]", errors)
    elif isinstance(value, str) and value in FORBIDDEN_STATUS_VALUES:
        errors.append(f"{loc}: adaptive research inputs must not contain final status value {value!r}")
    return errors


def validate_run_relative_ref(ref: str, errors: list[str], loc: str) -> None:
    if ref.startswith("/") or ":" in ref.replace("verifier_artifacts/*.json", ""):
        errors.append(f"{loc}: evidence ref must be run-relative/provenance-only, got {ref!r}")
    if ".." in Path(ref).parts:
        errors.append(f"{loc}: evidence ref must not escape run folder, got {ref!r}")
    if Path(ref).name in STATUS_ARTIFACTS:
        errors.append(f"{loc}: evidence ref must not point at authority artifact {ref!r}")


def validate_adaptive_research_inputs(data: dict, *, run_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    validator = load_schema_validator()
    schema_errors = validator.validate(data, load_json(SCHEMA_PATH))
    errors.extend(f"schema: {item}" for item in schema_errors)
    if schema_errors:
        return errors

    authority = data["authority"]
    if authority.get("can_certify_done") is not False:
        errors.append("authority.can_certify_done must be false")
    if authority.get("can_write_status_artifacts") is not False:
        errors.append("authority.can_write_status_artifacts must be false")
    if authority.get("claim_correctness") is not False:
        errors.append("authority.claim_correctness must be false")
    if authority.get("claim_exhaustive_research") is not False:
        errors.append("authority.claim_exhaustive_research must be false")
    if authority.get("final_status_authority") != "certifier_only":
        errors.append("authority.final_status_authority must be certifier_only")

    boundary = data["determinism_boundary"]
    for required_true in [
        "adaptive_generation_may_be_nondeterministic",
        "deterministic_validation_required",
        "validators_must_not_fetch_network",
        "certifier_ignores_as_authority",
        "replay_uses_recorded_sources_only",
    ]:
        if boundary.get(required_true) is not True:
            errors.append(f"determinism_boundary.{required_true} must be true")

    collection = data["collection_config"]
    if collection.get("non_exhaustive_research_claim") != "bounded_not_exhaustive":
        errors.append("collection_config.non_exhaustive_research_claim must be bounded_not_exhaustive")
    if len(data["research_questions"]) > int(collection.get("max_research_questions", 0)):
        errors.append("research_questions length exceeds collection_config.max_research_questions")
    if len(data["findings"]) > int(collection.get("max_findings", 0)):
        errors.append("findings length exceeds collection_config.max_findings")
    if len(data["planning_inputs"]) > int(collection.get("max_planning_inputs", 0)):
        errors.append("planning_inputs length exceeds collection_config.max_planning_inputs")

    implementation = data["implementation_boundary"]
    if implementation.get("source_code_origin") != "harness_native_no_vendor_copy":
        errors.append("implementation_boundary.source_code_origin must be harness_native_no_vendor_copy")
    if implementation.get("external_sources_are_design_inputs_only") is not True:
        errors.append("external sources must remain design inputs only")
    if implementation.get("external_code_copied") is not False:
        errors.append("implementation_boundary.external_code_copied must be false")
    if implementation.get("external_dependencies_added") is not False:
        errors.append("implementation_boundary.external_dependencies_added must be false")

    write_policy = data["status_artifact_write_policy"]
    if write_policy.get("attempted_status_write") is not False:
        errors.append("status_artifact_write_policy.attempted_status_write must be false")
    forbidden_paths = set(write_policy.get("forbidden_paths", []))
    missing_forbidden = sorted(STATUS_ARTIFACTS - forbidden_paths)
    if missing_forbidden:
        errors.append(f"status_artifact_write_policy.forbidden_paths missing authority files: {missing_forbidden}")

    question_ids = [item.get("question_id") for item in data["research_questions"]]
    if len(question_ids) != len(set(question_ids)):
        errors.append("research_questions question_id values must be unique")

    finding_ids = [item.get("finding_id") for item in data["findings"]]
    if len(finding_ids) != len(set(finding_ids)):
        errors.append("findings finding_id values must be unique")
    finding_id_set = set(finding_ids)
    for finding in data["findings"]:
        finding_id = finding.get("finding_id")
        if finding.get("authority_impact") != "none":
            errors.append(f"finding {finding_id} authority_impact must be none")
        if finding.get("can_certify_done") is not False:
            errors.append(f"finding {finding_id} can_certify_done must be false")
        if finding.get("external_source_design_only") is not True:
            errors.append(f"finding {finding_id} external_source_design_only must be true")
        if finding.get("code_copied") is not False:
            errors.append(f"finding {finding_id} code_copied must be false")
        provenance = finding.get("provenance", {})
        if not str(provenance.get("content_hash", "")).startswith("sha256:"):
            errors.append(f"finding {finding_id} provenance.content_hash must be sha256")
        for ref in finding.get("evidence_refs", []):
            validate_run_relative_ref(str(ref), errors, f"finding {finding_id} evidence_refs")

    input_ids = [item.get("input_id") for item in data["planning_inputs"]]
    if len(input_ids) != len(set(input_ids)):
        errors.append("planning_inputs input_id values must be unique")
    for item in data["planning_inputs"]:
        input_id = item.get("input_id")
        if item.get("authority_level") != "planning_only":
            errors.append(f"planning input {input_id} authority_level must be planning_only")
        if item.get("can_certify_done") is not False:
            errors.append(f"planning input {input_id} can_certify_done must be false")
        if not str(item.get("required_verifier_followup", "")).strip():
            errors.append(f"planning input {input_id} must record required verifier follow-up")
        for ref in item.get("finding_refs", []):
            if ref not in finding_id_set:
                errors.append(f"planning input {input_id} references missing finding: {ref}")

    integration = data["integration_contract"]
    boundary_text = str(integration.get("authority_boundary", "")).lower()
    if "cannot certify" not in boundary_text:
        errors.append("integration_contract.authority_boundary must state adaptive research cannot certify")
    for forbidden_consumer in integration.get("must_not_be_consumed_by", []):
        lowered = str(forbidden_consumer).lower()
        if "certify_run.py" in lowered or "policy_engine.py" in lowered:
            continue
        errors.append("integration_contract.must_not_be_consumed_by must name policy/certifier authority boundaries")

    errors.extend(recursively_find_forbidden_status_values(data))

    if run_dir is not None:
        if data.get("run_id") != run_dir.name:
            errors.append("run_id must match run directory name")
        source_map = {item["path"]: item for item in data["source_artifacts"]}
        for rel_path, item in source_map.items():
            exists = (run_dir / rel_path).is_file()
            if item.get("exists") != exists:
                errors.append(f"source_artifacts exists mismatch for {rel_path}")
            if item.get("required") is True and not exists:
                errors.append(f"required source artifact missing: {rel_path}")
        if not (run_dir / "goal_contract.json").is_file():
            errors.append("required source artifact missing: goal_contract.json")
        if not (run_dir / "strategy_candidates.json").is_file():
            errors.append("required source artifact missing: strategy_candidates.json")

    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate adaptive_research_inputs.json")
    parser.add_argument("path", help="adaptive_research_inputs.json path or run directory")
    args = parser.parse_args(argv)
    path = Path(args.path)
    artifact_path = path / "adaptive_research_inputs.json" if path.is_dir() else path
    if not artifact_path.is_file():
        print(f"ADAPTIVE_RESEARCH_INPUTS_INVALID: file missing: {artifact_path}")
        return 1
    try:
        data = load_json(artifact_path)
        errors = validate_adaptive_research_inputs(data, run_dir=path_to_run_dir(artifact_path))
    except Exception as exc:
        print(f"ADAPTIVE_RESEARCH_INPUTS_INVALID: {exc}")
        return 1
    if errors:
        print("ADAPTIVE_RESEARCH_INPUTS_INVALID")
        for item in errors:
            print(f"- {item}")
        return 1
    print("ADAPTIVE_RESEARCH_INPUTS_VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
