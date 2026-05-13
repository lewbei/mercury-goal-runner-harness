#!/usr/bin/env python3
"""Validate the Stage 1 live A/B capture request pack offline."""

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
DEFAULT_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage1_multiframe"
PROMPT_SET_PATH = DEFAULT_DIR / "prompt_set.json"
SCHEMA_PATH = DEFAULT_DIR / "stage1_capture_request_pack.schema.json"
VALIDATE_SCHEMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
MODES = {"normal_prompt", "multiframe_harness"}
PROTECTED_STATUS_VALUES = {"CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"}
PROTECTED_STEMS = {"final_status", "certification", "policy_decision"}
INVISIBLE_CODEPOINTS = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"}
FORBIDDEN_TASK_KEYS = {"output_text", "output_hash", "captured_at", "provider", "model", "model_version"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_stage1_capture_request_pack", VALIDATE_SCHEMA_PATH)
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
    name = normalize_name(Path(cleaned).name)
    looks_like_artifact_ref = "/" in cleaned or "\\" in cleaned or Path(cleaned).suffix in {".json", ".md"}
    protected_artifact_mentioned = any(
        re.search(rf"\b{re.escape(stem)}(?:[_\-.][\w.-]+)?\.(?:json|md)\b", cleaned, flags=re.IGNORECASE)
        for stem in PROTECTED_STEMS
    )
    if protected_artifact_mentioned or (
        looks_like_artifact_ref and any(name == stem or name.startswith((f"{stem}_", f"{stem}-", f"{stem}.")) for stem in PROTECTED_STEMS)
    ):
        errors.append(f"{loc}: request pack must not reference protected status artifact {value!r}")


def validate_request_pack(prompt_set: dict[str, Any], request_pack: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_validator = load_schema_validator()
    errors.extend(f"schema: {item}" for item in schema_validator.validate(request_pack, load_json(SCHEMA_PATH)))
    scan_value(request_pack, errors, "request_pack")
    if errors:
        return errors

    prompts = {prompt["prompt_id"]: prompt for prompt in prompt_set["prompts"]}
    if len(prompts) != 50:
        errors.append("request pack validation requires the 50-prompt Stage 1 prompt set")
    tasks = request_pack["tasks"]
    if len(tasks) != 100:
        errors.append(f"request pack must contain exactly 100 tasks, got {len(tasks)}")
    if request_pack["capture_policy"].get("required_task_count") != 100:
        errors.append("capture_policy.required_task_count must be 100")
    if set(request_pack["capture_policy"].get("modes", [])) != MODES:
        errors.append("capture_policy.modes must be normal_prompt and multiframe_harness")

    task_ids: set[str] = set()
    modes_by_prompt: dict[str, set[str]] = {prompt_id: set() for prompt_id in prompts}
    for index, task in enumerate(tasks):
        loc = f"tasks[{index}]"
        forbidden_keys_present = sorted(FORBIDDEN_TASK_KEYS & set(task))
        if forbidden_keys_present:
            errors.append(f"{loc}: request task must not include output/live result keys {forbidden_keys_present}")
        task_id = task["task_id"]
        if task_id in task_ids:
            errors.append(f"duplicate task_id: {task_id}")
        task_ids.add(task_id)
        prompt_id = task["prompt_id"]
        mode = task["mode"]
        if prompt_id not in prompts:
            errors.append(f"{loc}: unknown prompt_id {prompt_id!r}")
            continue
        if mode in modes_by_prompt[prompt_id]:
            errors.append(f"{loc}: duplicate mode {mode!r} for prompt_id {prompt_id!r}")
        modes_by_prompt[prompt_id].add(mode)
        prompt = prompts[prompt_id]
        if task["prompt_text"] != prompt["prompt"]:
            errors.append(f"{loc}: prompt_text does not match prompt_set for {prompt_id}")
        if task["prompt_hash"] != sha256_text(task["prompt_text"]):
            errors.append(f"{loc}: prompt_hash mismatch")
        if prompt["prompt"] not in task["capture_instruction"]:
            errors.append(f"{loc}: capture_instruction must include the exact benchmark prompt")

    for prompt_id, modes in modes_by_prompt.items():
        if modes != MODES:
            errors.append(f"prompt {prompt_id}: expected exactly modes {sorted(MODES)}, got {sorted(modes)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 1 live A/B capture request pack")
    parser.add_argument("--prompt-set", default=str(PROMPT_SET_PATH))
    parser.add_argument("--request-pack", required=True)
    args = parser.parse_args(argv)

    errors = validate_request_pack(load_json(Path(args.prompt_set)), load_json(Path(args.request_pack)))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: stage1 live capture request pack valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
