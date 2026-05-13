#!/usr/bin/env python3
"""Validate the Stage 2 live planning capture request pack offline."""

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
SCHEMA_PATH = DEFAULT_DIR / "stage2_planning_capture_request_pack.schema.json"
VALIDATE_SCHEMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
MODES = {"normal_planning", "bounded_multi_plan_gate"}
PROTECTED_STATUS_VALUES = {"CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"}
INVISIBLE_CODEPOINTS = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"}
FORBIDDEN_TASK_KEYS = {"output_text", "output_hash", "captured_at", "provider", "model", "model_version"}
REQUIRED_BOUNDED_PHRASES = [
    "Known facts from the goal only",
    "prompt-supported or speculative",
    "Unknowns / blockers",
    "At least three candidate plans",
    "Attacks against each candidate plan",
    "Rejected bad plans",
    "Evidence required before execution",
    "Exact validation commands",
    "File/path boundary check",
    "NEED_USER / BLOCKED",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_stage2_planning_request_pack", VALIDATE_SCHEMA_PATH)
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
            errors.append(f"{loc}.can_certify_done: request pack cannot certify DONE")
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
            errors.append(f"{loc}: request pack must not contain final status value {status!r}")


def validate_request_pack(prompt_set: dict[str, Any], request_pack: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_validator = load_schema_validator()
    errors.extend(f"schema: {item}" for item in schema_validator.validate(request_pack, load_json(SCHEMA_PATH)))
    scan_value(request_pack, errors, "request_pack")
    if errors:
        return errors

    prompts = {prompt["case_id"]: prompt for prompt in prompt_set["prompts"]}
    if len(prompts) != 10:
        errors.append("request pack validation requires the 10-case Stage 2 planning prompt set")
    tasks = request_pack["tasks"]
    if len(tasks) != 20:
        errors.append(f"request pack must contain exactly 20 tasks, got {len(tasks)}")
    if request_pack["capture_policy"].get("required_task_count") != 20:
        errors.append("capture_policy.required_task_count must be 20")
    if set(request_pack["capture_policy"].get("modes", [])) != MODES:
        errors.append("capture_policy.modes must be normal_planning and bounded_multi_plan_gate")

    task_ids: set[str] = set()
    modes_by_case: dict[str, set[str]] = {case_id: set() for case_id in prompts}
    for index, task in enumerate(tasks):
        loc = f"tasks[{index}]"
        forbidden_keys_present = sorted(FORBIDDEN_TASK_KEYS & set(task))
        if forbidden_keys_present:
            errors.append(f"{loc}: request task must not include output/live result keys {forbidden_keys_present}")
        task_id = task["task_id"]
        if task_id in task_ids:
            errors.append(f"duplicate task_id: {task_id}")
        task_ids.add(task_id)
        case_id = task["case_id"]
        mode = task["mode"]
        if case_id not in prompts:
            errors.append(f"{loc}: unknown case_id {case_id!r}")
            continue
        if mode in modes_by_case[case_id]:
            errors.append(f"{loc}: duplicate mode {mode!r} for case_id {case_id!r}")
        modes_by_case[case_id].add(mode)
        prompt = prompts[case_id]
        if task["prompt_text"] != prompt["prompt"]:
            errors.append(f"{loc}: prompt_text does not match prompt_set for {case_id}")
        if task["prompt_hash"] != sha256_text(task["prompt_text"]):
            errors.append(f"{loc}: prompt_hash mismatch")
        if prompt["prompt"] not in task["capture_instruction"]:
            errors.append(f"{loc}: capture_instruction must include the exact planning prompt")
        if mode == "bounded_multi_plan_gate":
            missing = [phrase for phrase in REQUIRED_BOUNDED_PHRASES if phrase not in task["capture_instruction"]]
            if missing:
                errors.append(f"{loc}: bounded_multi_plan_gate instruction missing planning phrases {missing}")
    for case_id, modes in modes_by_case.items():
        if modes != MODES:
            errors.append(f"case {case_id}: expected exactly modes {sorted(MODES)}, got {sorted(modes)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 2 live planning capture request pack")
    parser.add_argument("--prompt-set", default=str(PROMPT_SET_PATH))
    parser.add_argument("--request-pack", required=True)
    args = parser.parse_args(argv)
    errors = validate_request_pack(load_json(Path(args.prompt_set)), load_json(Path(args.request_pack)))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: stage2 planning request pack valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
