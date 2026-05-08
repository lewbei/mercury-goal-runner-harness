#!/usr/bin/env python3
"""Aggregate RPG harness test records.

This reports statistics over collected RPG test records. It does not certify
DONE and does not replace certify_run.py or policy_engine.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / ".agentic-runs" / "rpg_test_aggregation_outputs" / "rpg_test_aggregation_result.json"
RPG_SCHEMA = ROOT / ".agentic-pi" / "schemas" / "rpg_test_record.schema.json"
VALIDATE_SCHEMA = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"

VERSION = "v3.4"
FALSE_CERTIFIED_DONE = "FALSE_CERTIFIED_DONE"
FALSE_NOT_DONE = "FALSE_NOT_DONE"
MONITOR_FAIL = "MONITOR_FAIL"


def _load_schema_validator():
    spec = importlib.util.spec_from_file_location("validate_schema_for_rpg_aggregator", VALIDATE_SCHEMA)
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_schema_for_rpg_aggregator"] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def discover_record_paths(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        candidate = path if path.is_absolute() else ROOT / path
        if candidate.is_file():
            found.append(candidate)
        elif candidate.is_dir():
            found.extend(sorted(candidate.rglob("rpg_test_record.json")))
            if candidate.name == "templates":
                found.extend(sorted(candidate.rglob("rpg_test_record.template.json")))
        else:
            raise FileNotFoundError(f"record path does not exist: {path}")
    return sorted(set(found))


def _rate_bps(count: int, total: int) -> int:
    if total == 0:
        return 0
    return round((count / total) * 10000)


def _wilson_interval_bps(count: int, total: int, z: float = 1.96) -> dict:
    if total == 0:
        return {"count": count, "total": total, "rate_bps": 0, "lower_bps": 0, "upper_bps": 0}

    p_hat = count / total
    denom = 1 + (z * z / total)
    center = (p_hat + (z * z) / (2 * total)) / denom
    half_width = (
        z
        * math.sqrt((p_hat * (1 - p_hat) / total) + ((z * z) / (4 * total * total)))
        / denom
    )
    lower = max(0.0, center - half_width)
    upper = min(1.0, center + half_width)
    return {
        "count": count,
        "total": total,
        "rate_bps": _rate_bps(count, total),
        "lower_bps": round(lower * 10000),
        "upper_bps": round(upper * 10000),
    }


def _record_status(record: dict) -> str:
    return record["failure_classification"]["result"]


def _is_monitor_miss(record: dict) -> bool:
    expected_failure = record["purpose"]["expected_failure_mode"]
    caught = record["failure_classification"]["was_caught"]
    return expected_failure != "other" and not caught


def aggregate_records(paths: list[Path], min_records: int = 1) -> dict:
    validator = _load_schema_validator()
    schema = validator.load_json(RPG_SCHEMA)
    record_paths = discover_record_paths(paths)
    loaded_records = []
    invalid_records = []

    for path in record_paths:
        try:
            record = load_json(path)
        except Exception as exc:  # pragma: no cover - defensive reporting
            invalid_records.append({"path": display_path(path), "errors": [str(exc)]})
            continue
        errors = validator.validate(record, schema)
        if errors:
            invalid_records.append({"path": display_path(path), "errors": errors})
            continue
        loaded_records.append({"path": display_path(path), "record": record})

    included = [
        row for row in loaded_records
        if row["record"]["statistical_metadata"]["include_in_statistics"]
    ]
    excluded = [
        row for row in loaded_records
        if not row["record"]["statistical_metadata"]["include_in_statistics"]
    ]
    statuses = [_record_status(row["record"]) for row in included]
    false_certified_count = sum(1 for status in statuses if status == FALSE_CERTIFIED_DONE)
    false_block_count = sum(1 for status in statuses if status == FALSE_NOT_DONE)
    monitor_miss_count = sum(1 for row in included if _is_monitor_miss(row["record"]))
    regression_fixture_count = sum(
        1 for row in included
        if row["record"]["regression_decision"]["should_become_regression_fixture"]
    )
    patch_needed_count = sum(1 for row in included if row["record"]["regression_decision"]["patch_needed"])
    included_count = len(included)
    counts_by_result = {}
    counts_by_failure_mode = {}
    counts_by_catch_layer = {}
    for row in included:
        record = row["record"]
        result = record["failure_classification"]["result"]
        failure_mode = record["purpose"]["expected_failure_mode"]
        catch_layer = record["purpose"]["expected_catch_layer"]
        counts_by_result[result] = counts_by_result.get(result, 0) + 1
        counts_by_failure_mode[failure_mode] = counts_by_failure_mode.get(failure_mode, 0) + 1
        counts_by_catch_layer[catch_layer] = counts_by_catch_layer.get(catch_layer, 0) + 1

    stopping_rule_met = (
        len(invalid_records) == 0
        and included_count >= min_records
        and false_certified_count == 0
        and monitor_miss_count == 0
    )

    return {
        "aggregation_id": "rpg_test_record_statistics",
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(record_paths),
        "schema_valid_count": len(loaded_records),
        "schema_invalid_count": len(invalid_records),
        "included_count": included_count,
        "excluded_count": len(excluded),
        "min_records": min_records,
        "counts_by_result": counts_by_result,
        "counts_by_failure_mode": counts_by_failure_mode,
        "counts_by_catch_layer": counts_by_catch_layer,
        "false_certified_done_count": false_certified_count,
        "false_certified_done_rate_bps": _rate_bps(false_certified_count, included_count),
        "monitor_miss_count": monitor_miss_count,
        "monitor_miss_rate_bps": _rate_bps(monitor_miss_count, included_count),
        "false_block_count": false_block_count,
        "false_block_rate_bps": _rate_bps(false_block_count, included_count),
        "regression_fixture_count": regression_fixture_count,
        "patch_needed_count": patch_needed_count,
        "confidence_intervals_bps": {
            "false_certified_done": _wilson_interval_bps(false_certified_count, included_count),
            "monitor_miss": _wilson_interval_bps(monitor_miss_count, included_count),
            "false_block": _wilson_interval_bps(false_block_count, included_count),
        },
        "invalid_records": invalid_records,
        "included_record_ids": [row["record"]["test_identity"]["test_id"] for row in included],
        "stopping_rule_met": stopping_rule_met,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "claim_boundary": (
            "RPG aggregation is statistical evidence only over collected schema-valid records; "
            "it does not prove arbitrary prompt coverage, arbitrary unbounded bash safety, "
            "or full Pi autonomy."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate RPG harness test records without certifying DONE.")
    parser.add_argument("paths", nargs="*", default=[".agentic-pi/templates"])
    parser.add_argument("--min-records", type=int, default=1)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    try:
        result = aggregate_records([Path(p) for p in args.paths], min_records=args.min_records)
    except Exception as exc:
        print(f"RPG_TEST_AGGREGATION_FAILED: {exc}")
        return 1
    write_json(Path(args.output), result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["stopping_rule_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
