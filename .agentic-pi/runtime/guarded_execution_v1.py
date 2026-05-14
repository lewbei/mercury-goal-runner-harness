#!/usr/bin/env python3
"""Guarded Execution v1.

This deterministic runtime slice validates the Stage 3 preflight report and then
permits exactly one safe non-authority artifact write. It rejects missing or
failing preflight evidence, protected status paths, multiple actions, raw command
actions, and unsafe runtime intents. It does not execute arbitrary goals, decide
policy, or certify DONE.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = ROOT / ".agentic-pi" / "runtime" / "stage3_runtime_preflight.py"
DEFAULT_PREFLIGHT_REPORT = ROOT / ".agentic-runs" / "stage3_runtime_preflight" / "stage3_runtime_preflight_report_v1.json"
DEFAULT_ACTION_SPEC = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v1_safe_action.json"
DEFAULT_RUN_ID = "guarded_execution_v1_smoke"
PROTECTED_OUTPUT_NAMES = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}
FINAL_STATUS_VALUES = {"CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"}
REQUIRED_AUTHORITY = {"authority_level": "evaluation_only", "final_status_authority": "certifier_only", "can_certify_done": False}
SAFE_ACTION_TYPE = "write_text_artifact"
SAFE_INTENTS = {"write_one_safe_artifact", "guarded_execution_v1_smoke"}
UNSAFE_INTENT_TOKENS = {
    "execute arbitrary",
    "execute goal",
    "run goal",
    "run_goal",
    "shell",
    "command",
    "protected status",
    "bypass policy",
    "bypass certifier",
    "certify done",
    "mark done",
}
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    if path.name in PROTECTED_OUTPUT_NAMES:
        raise ValueError(f"refusing to write protected status artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_preflight_module():
    spec = importlib.util.spec_from_file_location("stage3_runtime_preflight_for_guarded_execution", PREFLIGHT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def rel_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def contains_final_status_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_final_status_value(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_final_status_value(child) for child in value)
    if isinstance(value, str):
        return any(re.search(rf"\b{re.escape(status)}\b", value, flags=re.IGNORECASE) for status in FINAL_STATUS_VALUES)
    return False


def safe_run_id(run_id: str) -> bool:
    return bool(isinstance(run_id, str) and RUN_ID_RE.match(run_id) and not run_id.startswith("."))


def run_dir_for_id(run_id: str) -> Path:
    if not safe_run_id(run_id):
        raise ValueError(f"unsafe run id: {run_id!r}")
    return ROOT / ".agentic-runs" / run_id


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, expected: Any, actual: Any) -> None:
    checks.append({
        "check_id": check_id,
        "status": "PASS" if passed else "FAIL",
        "expected": expected,
        "actual": actual,
    })


def intent_is_safe(intent: str) -> bool:
    normalized = str(intent).strip().lower().replace("-", "_")
    if normalized in SAFE_INTENTS:
        return True
    return bool(normalized) and not any(token in normalized for token in UNSAFE_INTENT_TOKENS)


def preflight_permissions(preflight: dict[str, Any]) -> dict[str, Any]:
    value = preflight.get("runtime_preflight", {})
    return value if isinstance(value, dict) else {}


def preflight_is_usable(preflight: dict[str, Any]) -> tuple[bool, list[str]]:
    preflight_module = load_preflight_module()
    errors = preflight_module.validate_preflight_report(preflight)
    permissions = preflight_permissions(preflight)
    if preflight.get("schema_version") != "stage3_runtime_preflight_report_v1":
        errors.append("preflight schema_version mismatch")
    if preflight.get("status") != "STAGE3_RUNTIME_PREFLIGHT_PASS":
        errors.append("preflight status is not STAGE3_RUNTIME_PREFLIGHT_PASS")
    if preflight.get("authority") != REQUIRED_AUTHORITY:
        errors.append("preflight authority boundary mismatch")
    if permissions.get("may_consume_planning_evidence") is not True:
        errors.append("preflight does not allow planning evidence consumption")
    if permissions.get("may_execute_goals") is not False:
        errors.append("preflight must not allow goal execution")
    if permissions.get("may_certify_done") is not False:
        errors.append("preflight must not allow DONE certification")
    if permissions.get("requires_policy_certifier_for_status") is not True:
        errors.append("preflight must require policy/certifier for status")
    if contains_final_status_value(preflight):
        errors.append("preflight report contains final status enum value")
    return errors == [], errors


def validate_action_spec(action: Any) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(action, dict):
        return False, ["action spec must be a JSON object"]
    if "actions" in action:
        errors.append("multiple actions are not allowed")
    if "command" in action or "cmd" in action or "shell" in action:
        errors.append("raw command actions are not allowed")
    if action.get("schema_version") != "guarded_execution_action_v1":
        errors.append("action spec schema_version must be guarded_execution_action_v1")
    if action.get("action_type") != SAFE_ACTION_TYPE:
        errors.append(f"action_type must be {SAFE_ACTION_TYPE}")
    artifact_path = action.get("artifact_path")
    if not isinstance(artifact_path, str) or not artifact_path.strip():
        errors.append("artifact_path must be a non-empty string")
    else:
        candidate = Path(artifact_path)
        normalized = artifact_path.replace("\\", "/")
        if candidate.is_absolute():
            errors.append("artifact_path must be run-relative")
        if ".." in candidate.parts:
            errors.append("artifact_path must not contain path traversal")
        if Path(normalized).name in PROTECTED_OUTPUT_NAMES:
            errors.append("artifact_path must not target protected status artifacts")
        if not normalized.startswith("artifacts/"):
            errors.append("artifact_path must stay under artifacts/")
    content = action.get("content")
    if not isinstance(content, str) or not content.strip():
        errors.append("content must be a non-empty string")
    elif len(content.encode("utf-8")) > 2000:
        errors.append("content must be at most 2000 bytes")
    elif contains_final_status_value(content):
        errors.append("content must not contain final status enum values")
    return errors == [], errors


def resolve_artifact_path(run_dir: Path, artifact_path: str) -> Path:
    root = run_dir.resolve()
    resolved = (root / artifact_path).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"artifact path escapes run folder: {artifact_path}")
    if Path(artifact_path.replace("\\", "/")).name in PROTECTED_OUTPUT_NAMES:
        raise ValueError(f"artifact path targets protected status artifact: {artifact_path}")
    if not resolved.relative_to(root).as_posix().startswith("artifacts/"):
        raise ValueError(f"artifact path must stay under artifacts/: {artifact_path}")
    return resolved


def action_summary(action: Any) -> dict[str, Any]:
    if not isinstance(action, dict):
        return {"action_valid_shape": False}
    content = action.get("content")
    return {
        "action_id": action.get("action_id", ""),
        "action_type": action.get("action_type", ""),
        "artifact_path": action.get("artifact_path", ""),
        "content_sha256": sha256_text(content) if isinstance(content, str) else "",
        "content_bytes": len(content.encode("utf-8")) if isinstance(content, str) else 0,
    }


def build_execution_report(preflight: dict[str, Any], preflight_path: Path, action: Any, run_id: str, runtime_intent: str) -> dict[str, Any]:
    preflight_ok, preflight_errors = preflight_is_usable(preflight)
    action_ok, action_errors = validate_action_spec(action)
    checks: list[dict[str, Any]] = []
    permissions = preflight_permissions(preflight)

    add_check(checks, "preflight_usable", preflight_ok, "preflight report passes and preserves runtime permissions", preflight_errors)
    add_check(
        checks,
        "preflight_allows_only_planning_evidence_consumption",
        permissions.get("may_consume_planning_evidence") is True and permissions.get("may_execute_goals") is False,
        "may_consume_planning_evidence true and may_execute_goals false",
        {
            "may_consume_planning_evidence": permissions.get("may_consume_planning_evidence"),
            "may_execute_goals": permissions.get("may_execute_goals"),
        },
    )
    add_check(
        checks,
        "preflight_keeps_certifier_status_authority",
        permissions.get("may_certify_done") is False and permissions.get("requires_policy_certifier_for_status") is True,
        "may_certify_done false and requires_policy_certifier_for_status true",
        {
            "may_certify_done": permissions.get("may_certify_done"),
            "requires_policy_certifier_for_status": permissions.get("requires_policy_certifier_for_status"),
        },
    )
    add_check(checks, "single_safe_action_spec", action_ok, "exactly one write_text_artifact action under artifacts/", action_errors)
    add_check(checks, "runtime_intent_is_safe", intent_is_safe(runtime_intent), "runtime intent is safe and non-arbitrary", runtime_intent)

    status = "GUARDED_EXECUTION_V1_PASS" if all(check["status"] == "PASS" for check in checks) else "GUARDED_EXECUTION_V1_FAIL"
    artifact_written = False
    artifact_rel_path = ""
    artifact_sha256 = ""
    if status == "GUARDED_EXECUTION_V1_PASS":
        run_dir = run_dir_for_id(run_id)
        artifact_rel_path = action["artifact_path"]
        artifact_path = resolve_artifact_path(run_dir, artifact_rel_path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(action["content"], encoding="utf-8")
        artifact_written = True
        artifact_sha256 = sha256_text(action["content"])

    runtime_execution = {
        "run_id": run_id,
        "preflight_checked": True,
        "action_count_requested": 1 if isinstance(action, dict) and "actions" not in action else len(action.get("actions", [])) if isinstance(action, dict) and isinstance(action.get("actions"), list) else 0,
        "action_count_executed": 1 if artifact_written else 0,
        "safe_artifact_written": artifact_written,
        "artifact_path": artifact_rel_path,
        "artifact_sha256": artifact_sha256,
        "goal_execution_attempted": False,
        "arbitrary_command_attempted": isinstance(action, dict) and any(key in action for key in ["command", "cmd", "shell"]),
        "protected_status_write_attempted": isinstance(action, dict) and Path(str(action.get("artifact_path", "")).replace("\\", "/")).name in PROTECTED_OUTPUT_NAMES,
        "status_authority": "certifier_only",
        "requires_policy_certifier_for_status": True,
        "can_certify_done": False,
    }
    if status != "GUARDED_EXECUTION_V1_PASS":
        runtime_execution["safe_artifact_written"] = False
        runtime_execution["artifact_path"] = ""
        runtime_execution["artifact_sha256"] = ""

    return {
        "schema_version": "guarded_execution_v1_report_v1",
        "status": status,
        "authority": REQUIRED_AUTHORITY,
        "runtime_intent": runtime_intent,
        "source_reports": {"stage3_runtime_preflight_report": rel_path(preflight_path)},
        "action_summary": action_summary(action),
        "criteria": checks,
        "runtime_execution": runtime_execution,
        "summary": {
            "preflight_status": preflight.get("status"),
            "criteria_passed": sum(1 for check in checks if check["status"] == "PASS"),
            "criteria_total": len(checks),
        },
        "claim_boundary": "Guarded Execution v1 proves one safe non-authority artifact write can occur after a passing Stage 3 preflight. It does not execute arbitrary goals, decide policy, certify DONE, or prove arbitrary runtime safety.",
    }


def validate_execution_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "guarded_execution_v1_report_v1":
        errors.append("schema_version must be guarded_execution_v1_report_v1")
    if report.get("authority") != REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    if contains_final_status_value(report):
        errors.append("guarded execution report must not contain final status enum values")
    runtime_execution = report.get("runtime_execution", {})
    if runtime_execution.get("goal_execution_attempted") is not False:
        errors.append("runtime_execution.goal_execution_attempted must be false")
    if runtime_execution.get("can_certify_done") is not False:
        errors.append("runtime_execution.can_certify_done must be false")
    if runtime_execution.get("status_authority") != "certifier_only":
        errors.append("runtime_execution.status_authority must be certifier_only")
    if runtime_execution.get("requires_policy_certifier_for_status") is not True:
        errors.append("runtime_execution.requires_policy_certifier_for_status must be true")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
    else:
        expected_status = "GUARDED_EXECUTION_V1_PASS" if all(check.get("status") == "PASS" for check in criteria) else "GUARDED_EXECUTION_V1_FAIL"
        if report.get("status") != expected_status:
            errors.append(f"status must be {expected_status}")
    if report.get("status") == "GUARDED_EXECUTION_V1_PASS":
        if runtime_execution.get("action_count_executed") != 1:
            errors.append("passing guarded execution must execute exactly one action")
        if runtime_execution.get("safe_artifact_written") is not True:
            errors.append("passing guarded execution must write a safe artifact")
    else:
        if runtime_execution.get("action_count_executed") != 0:
            errors.append("failing guarded execution must execute zero actions")
        if runtime_execution.get("safe_artifact_written") is not False:
            errors.append("failing guarded execution must not write an artifact")
    return errors


def load_required_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} missing: {path}")
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Guarded Execution v1")
    parser.add_argument("--preflight-report", default=str(DEFAULT_PREFLIGHT_REPORT))
    parser.add_argument("--action-spec", default=str(DEFAULT_ACTION_SPEC))
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--runtime-intent", default="write_one_safe_artifact")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    try:
        run_dir = run_dir_for_id(args.run_id)
        output_path = Path(args.output) if args.output else run_dir / "guarded_execution_v1_report.json"
        report = build_execution_report(
            load_required_json(Path(args.preflight_report), "preflight report"),
            Path(args.preflight_report),
            load_required_json(Path(args.action_spec), "action spec"),
            args.run_id,
            args.runtime_intent,
        )
        errors = validate_execution_report(report)
        write_json(output_path, report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report["status"] != "GUARDED_EXECUTION_V1_PASS":
        for check in report["criteria"]:
            if check["status"] != "PASS":
                print(f"FAIL: {check['check_id']}: expected {check['expected']}, actual {check['actual']}", file=sys.stderr)
        return 1
    print(f"OK: {report['status']} ({len(report['criteria'])} checks) -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
