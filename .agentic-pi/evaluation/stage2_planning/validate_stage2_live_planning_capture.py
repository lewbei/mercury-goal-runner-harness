#!/usr/bin/env python3
"""Validate Stage 2 live planning capture provenance offline.

This validator does not call live models and does not score raw model text. It
only checks capture completeness, hashes, prompt matching, and authority bounds.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage2_planning"
PROMPT_SET_PATH = DEFAULT_DIR / "planning_prompt_set.json"
SCHEMA_PATH = DEFAULT_DIR / "stage2_live_planning_capture.schema.json"
VALIDATE_SCHEMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
MODES = {"normal_planning", "bounded_multi_plan_gate"}
PROTECTED_STATUS_VALUES = {"CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"}
INVISIBLE_CODEPOINTS = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_stage2_live_planning_capture", VALIDATE_SCHEMA_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(ch for ch in normalized if ch not in INVISIBLE_CODEPOINTS and unicodedata.category(ch) != "Cf")


def scan_value(value: Any, errors: list[str], loc: str = "$") -> None:
    if isinstance(value, dict):
        if value.get("can_certify_done") is True:
            errors.append(f"{loc}.can_certify_done: live planning capture cannot certify DONE")
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
        if re.search(rf"\b{re.escape(status)}\b", cleaned, flags=re.IGNORECASE):
            errors.append(f"{loc}: live planning capture must not contain final status value {status!r}")
    if re.search(r"\b(i|we)\s+(certify|certified)\b", cleaned, flags=re.IGNORECASE):
        errors.append(f"{loc}: live planning capture must not claim certification authority")


def validate_capture(prompt_set: dict[str, Any], capture: dict[str, Any], *, allow_subset_for_tests: bool = False) -> list[str]:
    errors: list[str] = []
    schema_validator = load_schema_validator()
    errors.extend(f"schema: {item}" for item in schema_validator.validate(capture, load_json(SCHEMA_PATH)))
    scan_value(capture, errors, "capture")
    if errors:
        return errors

    prompt_by_id = {prompt["case_id"]: prompt for prompt in prompt_set["prompts"]}
    scope = capture["capture_scope"]
    if scope == "subset_fixture_only" and not allow_subset_for_tests:
        errors.append("subset_fixture_only captures require --allow-subset-for-tests")
    if scope == "full_10_case_capture" and allow_subset_for_tests:
        errors.append("--allow-subset-for-tests must not be used with full_10_case_capture")

    captures_by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for index, record in enumerate(capture["captures"]):
        loc = f"captures[{index}]"
        case_id = record["case_id"]
        mode = record["mode"]
        if case_id not in prompt_by_id:
            errors.append(f"{loc}: unknown case_id {case_id!r}")
            continue
        prompt = prompt_by_id[case_id]
        if record["prompt_text"] != prompt["prompt"]:
            errors.append(f"{loc}: prompt_text does not match prompt_set for {case_id}")
        if record["prompt_hash"] != sha256_text(record["prompt_text"]):
            errors.append(f"{loc}: prompt_hash mismatch")
        if record["output_hash"] != sha256_text(record["output_text"]):
            errors.append(f"{loc}: output_hash mismatch")
        if record["system_prompt_hash"] == sha256_text(""):
            errors.append(f"{loc}: system_prompt_hash must not be the empty-string hash")
        if mode in captures_by_case.setdefault(case_id, {}):
            errors.append(f"{loc}: duplicate mode {mode!r} for case_id {case_id!r}")
        captures_by_case[case_id][mode] = record

    expected_case_ids = set(prompt_by_id) if scope == "full_10_case_capture" else set(captures_by_case)
    if scope == "full_10_case_capture" and len(expected_case_ids) != 10:
        errors.append("full live planning capture requires the 10-case Stage 2 prompt set")
    missing_case_ids = sorted(expected_case_ids - set(captures_by_case))
    if missing_case_ids:
        errors.append(f"missing case captures: {missing_case_ids}")
    for case_id in sorted(expected_case_ids & set(captures_by_case)):
        modes = set(captures_by_case[case_id])
        if modes != MODES:
            errors.append(f"case {case_id}: expected exactly modes {sorted(MODES)}, got {sorted(modes)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 2 live planning capture provenance offline")
    parser.add_argument("--prompt-set", default=str(PROMPT_SET_PATH))
    parser.add_argument("--capture", required=True)
    parser.add_argument("--allow-subset-for-tests", action="store_true")
    args = parser.parse_args(argv)
    errors = validate_capture(load_json(Path(args.prompt_set)), load_json(Path(args.capture)), allow_subset_for_tests=args.allow_subset_for_tests)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: stage2 live planning capture valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
