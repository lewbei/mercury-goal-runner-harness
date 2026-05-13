#!/usr/bin/env python3
"""Validate Stage 1 multi-frame settlement fixtures and score reports."""

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
DEFAULT_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage1_multiframe"
SCHEMA_PATH = DEFAULT_DIR / "stage1_multiframe_eval.schema.json"
VALIDATE_SCHEMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
PROTECTED_STEMS = {"final_status", "certification", "policy_decision"}
PROTECTED_STATUS_VALUES = {"CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"}
MODES = {"normal_prompt", "multiframe_harness"}
EXPECTED_50_CATEGORY_DISTRIBUTION = {
    "harness_governance": 8,
    "coding_tool_use": 7,
    "research_paper_novelty": 7,
    "repo_product_readiness": 6,
    "model_routing": 6,
    "self_improvement_evolution": 5,
    "memory_reputation_trust": 5,
    "safety_security": 3,
    "ambiguous_user_intent": 3,
}
INVISIBLE_CODEPOINTS = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_stage1", VALIDATE_SCHEMA_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(ch for ch in normalized if ch not in INVISIBLE_CODEPOINTS and unicodedata.category(ch) != "Cf")


def normalize_name(value: str) -> str:
    return " ".join(clean_text(value).lower().split()).replace(" ", "")


def scan_value(value: Any, errors: list[str], loc: str = "$") -> None:
    if isinstance(value, dict):
        if value.get("can_certify_done") is True:
            errors.append(f"{loc}.can_certify_done: Stage 1 evaluation cannot certify DONE")
        for key, child in value.items():
            scan_value(child, errors, f"{loc}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            scan_value(child, errors, f"{loc}[{index}]")
        return
    if not isinstance(value, str):
        return
    cleaned = clean_text(value)
    for status in PROTECTED_STATUS_VALUES:
        if re.search(rf"\b{re.escape(status)}\b", cleaned):
            errors.append(f"{loc}: Stage 1 evaluation must not contain final status value {status!r}")
    name = normalize_name(Path(cleaned).name)
    looks_like_artifact_ref = "/" in cleaned or "\\" in cleaned or Path(cleaned).suffix in {".json", ".md"}
    if looks_like_artifact_ref and any(name == stem or name.startswith((f"{stem}_", f"{stem}-", f"{stem}.")) for stem in PROTECTED_STEMS):
        errors.append(f"{loc}: Stage 1 evaluation must not reference protected status artifact {value!r}")


def validate_prompt_set(prompt_set: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if prompt_set.get("authority", {}).get("can_certify_done") is not False:
        errors.append("prompt_set.authority.can_certify_done must be false")
    prompts = prompt_set.get("prompts")
    if not isinstance(prompts, list) or len(prompts) not in {5, 50}:
        errors.append("prompt_set.prompts must contain exactly 5 starter prompts or 50 settlement prompts")
        return errors
    seen = set()
    required_lists = ["expected_frames", "expected_assumptions", "expected_failure_modes", "bad_frames_to_reject"]
    category_counts: dict[str, int] = {}
    for prompt in prompts:
        prompt_id = prompt.get("prompt_id")
        if not prompt_id or prompt_id in seen:
            errors.append(f"prompt_id must be unique and non-empty, got {prompt_id!r}")
        seen.add(prompt_id)
        category = prompt.get("category")
        if len(prompts) == 50:
            if category not in EXPECTED_50_CATEGORY_DISTRIBUTION:
                errors.append(f"prompt {prompt_id}: unknown or missing category {category!r}")
            else:
                category_counts[category] = category_counts.get(category, 0) + 1
        for field in required_lists:
            if not isinstance(prompt.get(field), list) or not prompt[field]:
                errors.append(f"prompt {prompt_id}: {field} must be a non-empty list")
    if len(prompts) == 50 and category_counts != EXPECTED_50_CATEGORY_DISTRIBUTION:
        errors.append(f"50-prompt category distribution mismatch: expected {EXPECTED_50_CATEGORY_DISTRIBUTION}, got {category_counts}")
    declared_distribution = prompt_set.get("category_distribution")
    if len(prompts) == 50 and declared_distribution != EXPECTED_50_CATEGORY_DISTRIBUTION:
        errors.append("prompt_set.category_distribution must match the documented 50-prompt distribution")
    scan_value(prompt_set, errors, "prompt_set")
    return errors


def validate_response_fixtures(prompt_set: dict[str, Any], responses: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if responses.get("authority", {}).get("can_certify_done") is not False:
        errors.append("response_fixtures.authority.can_certify_done must be false")
    prompt_ids = {prompt["prompt_id"] for prompt in prompt_set.get("prompts", [])}
    by_prompt: dict[str, set[str]] = {prompt_id: set() for prompt_id in prompt_ids}
    for response in responses.get("responses", []):
        prompt_id = response.get("prompt_id")
        mode = response.get("mode")
        if prompt_id not in prompt_ids:
            errors.append(f"response references unknown prompt_id {prompt_id!r}")
            continue
        if mode not in MODES:
            errors.append(f"response {prompt_id}: invalid mode {mode!r}")
            continue
        if mode in by_prompt[prompt_id]:
            errors.append(f"response {prompt_id}: duplicate mode {mode}")
        by_prompt[prompt_id].add(mode)
        for field in ["frames_found", "assumptions_found", "failure_modes_found", "bad_frames_rejected"]:
            if not isinstance(response.get(field), list):
                errors.append(f"response {prompt_id}/{mode}: {field} must be a list")
        quality = response.get("final_answer_quality")
        if not isinstance(quality, (int, float)) or not 0 <= quality <= 1:
            errors.append(f"response {prompt_id}/{mode}: final_answer_quality must be number in [0, 1]")
    for prompt_id, modes in by_prompt.items():
        if modes != MODES:
            errors.append(f"prompt {prompt_id}: expected exactly modes {sorted(MODES)}, got {sorted(modes)}")
    scan_value(responses, errors, "response_fixtures")
    return errors


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_validator = load_schema_validator()
    errors.extend(f"schema: {item}" for item in schema_validator.validate(report, load_json(SCHEMA_PATH)))
    scan_value(report, errors, "report")
    if errors:
        return errors
    prompt_results = report["prompt_results"]
    prompt_count = report["prompt_count"]
    if prompt_count not in {5, 50}:
        errors.append("report.prompt_count must be exactly 5 or 50")
    if len(prompt_results) != prompt_count:
        errors.append(f"report.prompt_results length {len(prompt_results)} does not match prompt_count {prompt_count}")
    actual_wins = sum(1 for item in prompt_results if item["multiframe_beats_normal"])

    starter_gate = report["starter_gate"]
    if starter_gate["actual_prompt_wins"] != actual_wins:
        errors.append(f"starter_gate.actual_prompt_wins {starter_gate['actual_prompt_wins']} does not match prompt results {actual_wins}")
    if prompt_count == 5:
        expected_starter_status = "STARTER_GATE_PASS" if (
            actual_wins >= starter_gate["required_prompt_wins"]
            and starter_gate["assumption_recall_improved"]
            and starter_gate["failure_mode_recall_improved"]
            and starter_gate["quality_not_reduced"]
        ) else "STARTER_GATE_FAIL"
    else:
        expected_starter_status = "NOT_APPLICABLE"
    if starter_gate["status"] != expected_starter_status:
        errors.append(f"starter_gate.status must be {expected_starter_status}, got {starter_gate['status']}")

    settlement_gate = report["settlement_50_gate"]
    if settlement_gate["actual_prompt_wins"] != actual_wins:
        errors.append(f"settlement_50_gate.actual_prompt_wins {settlement_gate['actual_prompt_wins']} does not match prompt results {actual_wins}")
    if prompt_count == 50:
        expected_settlement_status = "SETTLEMENT_50_PASS" if (
            actual_wins >= settlement_gate["required_prompt_wins"]
            and settlement_gate["actual_assumption_recall_relative_improvement"] >= settlement_gate["minimum_assumption_recall_relative_improvement"]
            and settlement_gate["actual_failure_mode_recall_relative_improvement"] >= settlement_gate["minimum_failure_mode_recall_relative_improvement"]
            and settlement_gate["quality_not_reduced"]
        ) else "SETTLEMENT_50_FAIL"
    else:
        expected_settlement_status = "NOT_APPLICABLE"
    if settlement_gate["status"] != expected_settlement_status:
        errors.append(f"settlement_50_gate.status must be {expected_settlement_status}, got {settlement_gate['status']}")

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
    parser = argparse.ArgumentParser(description="Validate deterministic Stage 1 multi-frame evaluation artifacts")
    parser.add_argument("--prompt-set", default=str(DEFAULT_DIR / "prompt_set.json"))
    parser.add_argument("--responses", default=str(DEFAULT_DIR / "response_fixtures.json"))
    parser.add_argument("--report", default=str(DEFAULT_DIR / "stage1_score_report.json"))
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)
    report_path = None if args.no_report else Path(args.report)
    errors = validate_all(Path(args.prompt_set), Path(args.responses), report_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: stage1 multiframe evaluation valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
