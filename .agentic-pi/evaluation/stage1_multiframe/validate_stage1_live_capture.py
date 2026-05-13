#!/usr/bin/env python3
"""Validate Stage 1 live A/B capture provenance offline.

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
DEFAULT_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage1_multiframe"
PROMPT_SET_PATH = DEFAULT_DIR / "prompt_set.json"
SCHEMA_PATH = DEFAULT_DIR / "stage1_live_capture.schema.json"
VALIDATE_SCHEMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
MODES = {"normal_prompt", "multiframe_harness"}
PROTECTED_STEMS = {"final_status", "certification", "policy_decision"}
PROTECTED_STATUS_VALUES = {"CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"}
INVISIBLE_CODEPOINTS = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_stage1_live_capture", VALIDATE_SCHEMA_PATH)
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
            errors.append(f"{loc}.can_certify_done: live capture cannot certify DONE")
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
            errors.append(f"{loc}: live capture must not contain final status value {status!r}")
    name = normalize_name(Path(cleaned).name)
    looks_like_artifact_ref = "/" in cleaned or "\\" in cleaned or Path(cleaned).suffix in {".json", ".md"}
    protected_artifact_mentioned = any(
        re.search(rf"\b{re.escape(stem)}(?:[_\-.][\w.-]+)?\.(?:json|md)\b", cleaned, flags=re.IGNORECASE)
        for stem in PROTECTED_STEMS
    )
    if protected_artifact_mentioned or (
        looks_like_artifact_ref and any(name == stem or name.startswith((f"{stem}_", f"{stem}-", f"{stem}.")) for stem in PROTECTED_STEMS)
    ):
        errors.append(f"{loc}: live capture must not reference protected status artifact {value!r}")


def validate_capture(prompt_set: dict[str, Any], capture: dict[str, Any], *, allow_subset_for_tests: bool = False) -> list[str]:
    errors: list[str] = []
    schema_validator = load_schema_validator()
    errors.extend(f"schema: {item}" for item in schema_validator.validate(capture, load_json(SCHEMA_PATH)))
    scan_value(capture, errors, "capture")
    if errors:
        return errors

    prompt_by_id = {prompt["prompt_id"]: prompt for prompt in prompt_set["prompts"]}
    scope = capture["capture_scope"]
    if scope == "subset_fixture_only" and not allow_subset_for_tests:
        errors.append("subset_fixture_only captures require --allow-subset-for-tests")
    if scope == "full_50_prompt_capture" and allow_subset_for_tests:
        errors.append("--allow-subset-for-tests must not be used with full_50_prompt_capture")

    captures_by_prompt: dict[str, dict[str, dict[str, Any]]] = {}
    for index, record in enumerate(capture["captures"]):
        loc = f"captures[{index}]"
        prompt_id = record["prompt_id"]
        mode = record["mode"]
        if prompt_id not in prompt_by_id:
            errors.append(f"{loc}: unknown prompt_id {prompt_id!r}")
            continue
        prompt = prompt_by_id[prompt_id]
        if record["prompt_text"] != prompt["prompt"]:
            errors.append(f"{loc}: prompt_text does not match prompt_set for {prompt_id}")
        expected_prompt_hash = sha256_text(record["prompt_text"])
        if record["prompt_hash"] != expected_prompt_hash:
            errors.append(f"{loc}: prompt_hash mismatch")
        expected_output_hash = sha256_text(record["output_text"])
        if record["output_hash"] != expected_output_hash:
            errors.append(f"{loc}: output_hash mismatch")
        if record["system_prompt_hash"] == sha256_text(""):
            errors.append(f"{loc}: system_prompt_hash must not be the empty-string hash")
        if mode in captures_by_prompt.setdefault(prompt_id, {}):
            errors.append(f"{loc}: duplicate mode {mode!r} for prompt_id {prompt_id!r}")
        captures_by_prompt[prompt_id][mode] = record

    expected_prompt_ids = set(prompt_by_id) if scope == "full_50_prompt_capture" else set(captures_by_prompt)
    if scope == "full_50_prompt_capture" and len(expected_prompt_ids) != 50:
        errors.append("full live capture requires the 50-prompt Stage 1 prompt set")
    missing_prompt_ids = sorted(expected_prompt_ids - set(captures_by_prompt))
    if missing_prompt_ids:
        errors.append(f"missing prompt captures: {missing_prompt_ids}")
    for prompt_id in sorted(expected_prompt_ids & set(captures_by_prompt)):
        modes = set(captures_by_prompt[prompt_id])
        if modes != MODES:
            errors.append(f"prompt {prompt_id}: expected exactly modes {sorted(MODES)}, got {sorted(modes)}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 1 live A/B capture provenance offline")
    parser.add_argument("--prompt-set", default=str(PROMPT_SET_PATH))
    parser.add_argument("--capture", required=True)
    parser.add_argument("--allow-subset-for-tests", action="store_true")
    args = parser.parse_args(argv)

    errors = validate_capture(
        load_json(Path(args.prompt_set)),
        load_json(Path(args.capture)),
        allow_subset_for_tests=args.allow_subset_for_tests,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: stage1 live capture valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
