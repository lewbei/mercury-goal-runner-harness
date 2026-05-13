#!/usr/bin/env python3
"""Validate Stage 2 live planning feature reports offline."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage2_planning"
SCHEMA_PATH = DEFAULT_DIR / "stage2_live_planning_feature_report.schema.json"
VALIDATE_SCHEMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
PROTECTED_OUTPUT_NAMES = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}
PROTECTED_STATUS_VALUES = {"CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_stage2_live_planning_features", VALIDATE_SCHEMA_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def scan_value(value: Any, errors: list[str], loc: str = "$") -> None:
    if isinstance(value, dict):
        if value.get("can_certify_done") is True:
            errors.append(f"{loc}.can_certify_done: feature report cannot certify DONE")
        for key, child in value.items():
            scan_value(child, errors, f"{loc}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_value(child, errors, f"{loc}[{index}]")
    elif isinstance(value, str):
        for status in PROTECTED_STATUS_VALUES:
            if re.search(rf"\b{re.escape(status)}\b", value, flags=re.IGNORECASE):
                errors.append(f"{loc}: feature report must not contain final status value {status!r}")


def validate_report(prompt_set: dict[str, Any], capture: dict[str, Any], report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_validator = load_schema_validator()
    errors.extend(f"schema: {item}" for item in schema_validator.validate(report, load_json(SCHEMA_PATH)))
    scan_value(report, errors, "report")
    if errors:
        return errors

    prompt_ids = {prompt["case_id"] for prompt in prompt_set["prompts"]}
    capture_by_key = {(record["case_id"], record["mode"], record["output_hash"]): record for record in capture["captures"]}
    if report["record_count"] != len(report["records"]):
        errors.append("record_count must match records length")
    if report["record_count"] != len(capture["captures"]):
        errors.append("record_count must match capture records length")
    source = report["source_capture"]
    for field in ["capture_id", "prompt_set_id", "request_pack_id", "capture_scope"]:
        if source.get(field) != capture.get(field):
            errors.append(f"source_capture.{field} must match capture")
    if report["authority"].get("can_certify_done") is not False:
        errors.append("report.authority.can_certify_done must be false")

    for index, record in enumerate(report["records"]):
        loc = f"records[{index}]"
        if record["case_id"] not in prompt_ids:
            errors.append(f"{loc}: unknown case_id {record['case_id']!r}")
        key = (record["case_id"], record["mode"], record["output_hash"])
        if key not in capture_by_key:
            errors.append(f"{loc}: no matching capture record by case_id/mode/output_hash")
        for metric_name, metric_value in record["metrics"].items():
            if not isinstance(metric_value, (int, float)) or not 0 <= float(metric_value) <= 1:
                errors.append(f"{loc}: metric {metric_name} must be in [0, 1]")
        for feature in record["extracted_features"].values():
            if not isinstance(feature, list):
                errors.append(f"{loc}: extracted feature must be a list")
    for mode, metrics in report["aggregate_metrics"].get("mode_averages", {}).items():
        for metric_name, metric_value in metrics.items():
            if not isinstance(metric_value, (int, float)) or not 0 <= float(metric_value) <= 1:
                errors.append(f"aggregate {mode}.{metric_name} must be in [0, 1]")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 2 live planning feature report")
    parser.add_argument("--prompt-set", default=str(DEFAULT_DIR / "planning_prompt_set.json"))
    parser.add_argument("--capture", default=str(DEFAULT_DIR / "live_capture_mercury_subset_5.json"))
    parser.add_argument("--report", required=True)
    parser.add_argument("--allow-subset-for-tests", action="store_true")
    args = parser.parse_args(argv)
    capture = load_json(Path(args.capture))
    if capture.get("capture_scope") == "subset_fixture_only" and not args.allow_subset_for_tests:
        print("ERROR: subset_fixture_only feature reports require --allow-subset-for-tests", file=sys.stderr)
        return 1
    errors = validate_report(load_json(Path(args.prompt_set)), capture, load_json(Path(args.report)))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: stage2 live planning feature report valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
