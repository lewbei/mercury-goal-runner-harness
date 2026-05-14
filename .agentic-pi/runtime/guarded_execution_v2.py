#!/usr/bin/env python3
"""Guarded Execution v2 bounded plan execution.

This deterministic runtime slice validates Stage 3 preflight, reads a bounded
plan and an expected-artifacts contract, then writes only declared non-authority
text artifacts. It records a ledger with action order, hashes, and denied action
reasons. It does not run arbitrary commands, execute arbitrary goals, decide
policy, or certify completion.
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
DEFAULT_PLAN = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v2_plan.json"
DEFAULT_EXPECTED_ARTIFACTS = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v2_expected_artifacts.json"
DEFAULT_RUN_ID = "guarded_execution_v2_smoke"
DEFAULT_LEDGER_NAME = "guarded_execution_v2_ledger.json"
PROTECTED_OUTPUT_NAMES = {
    "final_status.json",
    "final_status.md",
    "certification.json",
    "policy_decision.json",
    "evidence_freeze.json",
    "evidence_index.json",
    "evidence_hash_manifest.json",
    "replay_report.json",
    "run_manifest.json",
    "goal_contract.json",
    "selected_plan.json",
    "merged_plan.json",
    "plan_graph.json",
    "verifier_contract.json",
    "validator_certification.json",
}
FINAL_STATUS_VALUES = {"CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"}
FORBIDDEN_CONTENT_PHRASES = {
    "final_status",
    "policy_decision",
    "certification.json",
    "final status authority",
    "final_status_authority",
    "status_authority",
    "can_certify_done",
    "certify done",
    "certified done",
    "mark done",
}
COMMAND_KEYS = {"command", "cmd", "shell", "exec", "python", "bash", "powershell"}
REQUIRED_AUTHORITY = {"authority_level": "evaluation_only", "final_status_authority": "certifier_only", "can_certify_done": False}
SAFE_ACTION_TYPE = "write_text_artifact"
SAFE_INTENTS = {"bounded_plan_artifact_writes", "guarded_execution_v2_smoke"}
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
MIN_ACTIONS = 3
MAX_ACTIONS = 5
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    if path.name in PROTECTED_OUTPUT_NAMES:
        raise ValueError(f"refusing to write protected status artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_required_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} missing: {path}")
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return data


def load_preflight_module():
    spec = importlib.util.spec_from_file_location("stage3_runtime_preflight_for_guarded_execution_v2", PREFLIGHT_PATH)
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


def contains_forbidden_content_language(value: str) -> bool:
    normalized = value.lower().replace("-", "_")
    return contains_final_status_value(value) or any(phrase in normalized for phrase in FORBIDDEN_CONTENT_PHRASES)


def contains_command_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in COMMAND_KEYS or contains_command_key(child) for key, child in value.items())
    if isinstance(value, list):
        return any(contains_command_key(child) for child in value)
    return False


def safe_run_id(run_id: str) -> bool:
    return bool(isinstance(run_id, str) and RUN_ID_RE.match(run_id) and not run_id.startswith("."))


def run_dir_for_id(run_id: str) -> Path:
    if not safe_run_id(run_id):
        raise ValueError(f"unsafe run id: {run_id!r}")
    return ROOT / ".agentic-runs" / run_id


def normalize_run_relative(raw_path: str) -> str:
    return raw_path.replace("\\", "/")


def basename_is_protected(raw_path: str) -> bool:
    return Path(normalize_run_relative(raw_path)).name in PROTECTED_OUTPUT_NAMES


def resolve_artifact_path(run_dir: Path, artifact_path: str) -> Path:
    root = run_dir.resolve()
    normalized = normalize_run_relative(artifact_path)
    candidate = Path(normalized)
    if candidate.is_absolute():
        raise ValueError(f"artifact path must be run-relative: {artifact_path}")
    if ".." in candidate.parts:
        raise ValueError(f"artifact path must not contain path traversal: {artifact_path}")
    if basename_is_protected(normalized):
        raise ValueError(f"artifact path targets protected status artifact: {artifact_path}")
    if not normalized.startswith("artifacts/"):
        raise ValueError(f"artifact path must stay under artifacts/: {artifact_path}")
    resolved = (root / normalized).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"artifact path escapes run folder: {artifact_path}")
    return resolved


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, expected: Any, actual: Any) -> None:
    checks.append({
        "check_id": check_id,
        "status": "PASS" if passed else "FAIL",
        "expected": expected,
        "actual": actual,
    })


def deny(denied: list[dict[str, Any]], action_id: str, artifact_path: str, reason: str) -> None:
    denied.append({
        "action_id": action_id,
        "artifact_path": artifact_path,
        "reason": reason,
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


def expected_artifact_items(contract: dict[str, Any]) -> list[Any]:
    items = contract.get("artifacts", contract.get("expected_artifacts", []))
    return items if isinstance(items, list) else []


def validate_expected_artifacts(contract: Any) -> tuple[bool, list[str], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    declared: dict[str, dict[str, Any]] = {}
    if not isinstance(contract, dict):
        return False, ["expected artifacts contract must be a JSON object"], declared
    if contract.get("schema_version") != "guarded_execution_v2_expected_artifacts_v1":
        errors.append("expected artifacts schema_version must be guarded_execution_v2_expected_artifacts_v1")
    items = expected_artifact_items(contract)
    if not items:
        errors.append("expected artifacts contract must declare at least one artifact")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"expected artifact #{index} must be an object")
            continue
        artifact_id = item.get("artifact_id")
        expected_path = item.get("expected_path")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            errors.append(f"expected artifact #{index} missing artifact_id")
            artifact_id = f"<missing-{index}>"
        if artifact_id in seen_ids:
            errors.append(f"duplicate expected artifact id: {artifact_id}")
        seen_ids.add(artifact_id)
        if not isinstance(expected_path, str) or not expected_path.strip():
            errors.append(f"expected artifact {artifact_id} missing expected_path")
            expected_path = ""
        normalized = normalize_run_relative(expected_path)
        if normalized in seen_paths:
            errors.append(f"duplicate expected artifact path: {normalized}")
        seen_paths.add(normalized)
        try:
            resolve_artifact_path(Path("/tmp/guarded-execution-v2-run"), normalized)
        except ValueError as exc:
            errors.append(f"expected artifact {artifact_id}: {exc}")
        if basename_is_protected(normalized):
            errors.append(f"expected artifact {artifact_id} targets protected status artifact")
        if item.get("required") is not True:
            errors.append(f"expected artifact {artifact_id} must be required")
        allowed_actions = item.get("allowed_actions", [SAFE_ACTION_TYPE])
        if not isinstance(allowed_actions, list) or SAFE_ACTION_TYPE not in allowed_actions:
            errors.append(f"expected artifact {artifact_id} must allow {SAFE_ACTION_TYPE}")
        max_bytes = item.get("max_size_bytes", 2000)
        min_bytes = item.get("min_size_bytes", 1)
        if not isinstance(min_bytes, int) or min_bytes < 1:
            errors.append(f"expected artifact {artifact_id} min_size_bytes must be a positive integer")
        if not isinstance(max_bytes, int) or max_bytes < min_bytes:
            errors.append(f"expected artifact {artifact_id} max_size_bytes must be >= min_size_bytes")
        declared[artifact_id] = {**item, "expected_path": normalized}
    return errors == [], errors, declared


def plan_actions(plan: dict[str, Any]) -> list[Any]:
    actions = plan.get("actions", []) if isinstance(plan, dict) else []
    return actions if isinstance(actions, list) else []


def validate_plan(plan: Any) -> tuple[bool, list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    normalized_actions: list[dict[str, Any]] = []
    if not isinstance(plan, dict):
        return False, ["bounded plan must be a JSON object"], normalized_actions
    if plan.get("schema_version") != "guarded_execution_v2_plan_v1":
        errors.append("plan schema_version must be guarded_execution_v2_plan_v1")
    if contains_command_key(plan):
        errors.append("plan contains raw command/cmd/shell key")
    actions = plan_actions(plan)
    if not actions:
        errors.append("plan must contain at least one action")
    elif len(actions) < MIN_ACTIONS:
        errors.append(f"plan action count is below budget floor {MIN_ACTIONS}: {len(actions)}")
    if len(actions) > MAX_ACTIONS:
        errors.append(f"plan action count exceeds budget {MAX_ACTIONS}: {len(actions)}")
    seen_action_ids: set[str] = set()
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            errors.append(f"action #{index} must be an object")
            continue
        action_id = action.get("action_id", f"<missing-{index}>")
        artifact_id = action.get("artifact_id", "")
        artifact_path = normalize_run_relative(str(action.get("artifact_path", "")))
        content = action.get("content", "")
        if not isinstance(action.get("action_id"), str) or not action.get("action_id", "").strip():
            errors.append(f"action #{index} missing action_id")
        if action_id in seen_action_ids:
            errors.append(f"duplicate action_id: {action_id}")
        seen_action_ids.add(str(action_id))
        if action.get("action_type") != SAFE_ACTION_TYPE:
            errors.append(f"action {action_id} action_type must be {SAFE_ACTION_TYPE}")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            errors.append(f"action {action_id} missing artifact_id")
        if not isinstance(action.get("artifact_path"), str) or not action.get("artifact_path", "").strip():
            errors.append(f"action {action_id} missing artifact_path")
        else:
            try:
                resolve_artifact_path(Path("/tmp/guarded-execution-v2-run"), artifact_path)
            except ValueError as exc:
                errors.append(f"action {action_id}: {exc}")
        if not isinstance(content, str) or not content.strip():
            errors.append(f"action {action_id} content must be a non-empty string")
        elif len(content.encode("utf-8")) > 2000:
            errors.append(f"action {action_id} content must be at most 2000 bytes")
        elif contains_forbidden_content_language(content):
            errors.append(f"action {action_id} content contains final-status authority language")
        normalized_actions.append({
            "index": index,
            "action_id": str(action_id),
            "action_type": action.get("action_type"),
            "artifact_id": artifact_id,
            "artifact_path": artifact_path,
            "content": content,
        })
    return errors == [], errors, normalized_actions


def validate_plan_against_contract(actions: list[dict[str, Any]], declared: dict[str, dict[str, Any]]) -> tuple[bool, list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    denied: list[dict[str, Any]] = []
    produced_ids = {action.get("artifact_id") for action in actions}
    for artifact_id, item in sorted(declared.items()):
        if item.get("required") is True and artifact_id not in produced_ids:
            errors.append(f"required expected artifact is not produced: {artifact_id}")
            deny(denied, "<missing-action>", item.get("expected_path", ""), f"required expected artifact is not produced: {artifact_id}")
    seen_paths: set[str] = set()
    seen_artifact_ids: set[str] = set()
    for action in actions:
        action_id = action["action_id"]
        artifact_id = action["artifact_id"]
        artifact_path = action["artifact_path"]
        contract_item = declared.get(artifact_id)
        if contract_item is None:
            reason = f"artifact_id is not declared in expected_artifacts: {artifact_id}"
            errors.append(f"action {action_id}: {reason}")
            deny(denied, action_id, artifact_path, reason)
            continue
        if artifact_id in seen_artifact_ids:
            reason = f"artifact_id is produced more than once: {artifact_id}"
            errors.append(f"action {action_id}: {reason}")
            deny(denied, action_id, artifact_path, reason)
        seen_artifact_ids.add(artifact_id)
        expected_path = contract_item.get("expected_path")
        if artifact_path != expected_path:
            reason = f"artifact_path does not match expected_artifacts path for {artifact_id}: expected {expected_path}, got {artifact_path}"
            errors.append(f"action {action_id}: {reason}")
            deny(denied, action_id, artifact_path, reason)
        if artifact_path in seen_paths:
            reason = f"artifact_path is written more than once: {artifact_path}"
            errors.append(f"action {action_id}: {reason}")
            deny(denied, action_id, artifact_path, reason)
        seen_paths.add(artifact_path)
        if action.get("action_type") not in contract_item.get("allowed_actions", [SAFE_ACTION_TYPE]):
            reason = f"action_type is not allowed by expected_artifacts for {artifact_id}"
            errors.append(f"action {action_id}: {reason}")
            deny(denied, action_id, artifact_path, reason)
        content_bytes = len(str(action.get("content", "")).encode("utf-8"))
        if content_bytes < contract_item.get("min_size_bytes", 1):
            reason = f"content is smaller than expected artifact minimum for {artifact_id}"
            errors.append(f"action {action_id}: {reason}")
            deny(denied, action_id, artifact_path, reason)
        if content_bytes > contract_item.get("max_size_bytes", 2000):
            reason = f"content is larger than expected artifact maximum for {artifact_id}"
            errors.append(f"action {action_id}: {reason}")
            deny(denied, action_id, artifact_path, reason)
    return errors == [], errors, denied


def unsafe_flags(plan: dict[str, Any], actions: list[dict[str, Any]], contract: dict[str, Any]) -> dict[str, bool]:
    contract_paths = [str(item.get("expected_path", "")) for item in expected_artifact_items(contract) if isinstance(item, dict)]
    action_paths = [str(action.get("artifact_path", "")) for action in actions]
    contents = [str(action.get("content", "")) for action in actions]
    return {
        "arbitrary_command_attempted": contains_command_key(plan),
        "protected_status_write_attempted": any(basename_is_protected(path) for path in [*contract_paths, *action_paths]),
        "final_status_language_denied": any(contains_forbidden_content_language(content) for content in contents),
        "over_budget_attempted": len(actions) > MAX_ACTIONS,
        "under_budget_attempted": len(actions) < MIN_ACTIONS,
    }


def action_order_entry(action: dict[str, Any], status: str, reason: str = "") -> dict[str, Any]:
    content = action.get("content") if isinstance(action.get("content"), str) else ""
    return {
        "index": action.get("index", -1),
        "action_id": action.get("action_id", ""),
        "artifact_id": action.get("artifact_id", ""),
        "artifact_path": action.get("artifact_path", ""),
        "content_sha256": sha256_text(content) if content else "",
        "content_bytes": len(content.encode("utf-8")) if content else 0,
        "status": status,
        "reason": reason,
    }


def build_execution_report(
    preflight: dict[str, Any],
    preflight_path: Path,
    plan: dict[str, Any],
    plan_path: Path,
    expected_artifacts: dict[str, Any],
    expected_artifacts_path: Path,
    run_id: str,
    runtime_intent: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_dir = run_dir_for_id(run_id)
    preflight_ok, preflight_errors = preflight_is_usable(preflight)
    contract_ok, contract_errors, declared = validate_expected_artifacts(expected_artifacts)
    plan_ok, plan_errors, actions = validate_plan(plan)
    match_ok, match_errors, denied_from_match = validate_plan_against_contract(actions, declared) if contract_ok and actions else (False, ["plan cannot be matched to expected artifacts"], [])
    flags = unsafe_flags(plan if isinstance(plan, dict) else {}, actions, expected_artifacts if isinstance(expected_artifacts, dict) else {})
    intent_ok = intent_is_safe(runtime_intent)
    checks: list[dict[str, Any]] = []
    permissions = preflight_permissions(preflight)

    add_check(checks, "preflight_usable", preflight_ok, "Stage 3 preflight passes and preserves permissions", preflight_errors)
    add_check(
        checks,
        "preflight_allows_planning_but_not_goal_execution",
        permissions.get("may_consume_planning_evidence") is True and permissions.get("may_execute_goals") is False,
        "may_consume_planning_evidence true and may_execute_goals false",
        {
            "may_consume_planning_evidence": permissions.get("may_consume_planning_evidence"),
            "may_execute_goals": permissions.get("may_execute_goals"),
        },
    )
    add_check(
        checks,
        "expected_artifacts_contract_valid",
        contract_ok,
        "expected_artifacts declares required safe artifact paths under artifacts/",
        contract_errors,
    )
    add_check(
        checks,
        "bounded_plan_valid",
        plan_ok,
        f"plan contains {MIN_ACTIONS}..{MAX_ACTIONS} write_text_artifact actions and no raw command keys",
        plan_errors,
    )
    add_check(
        checks,
        "plan_matches_expected_artifacts",
        match_ok,
        "every required expected artifact is produced exactly once at the declared path",
        match_errors,
    )
    flags["undeclared_path_attempted"] = any(
        "not declared" in error or "does not match expected_artifacts" in error for error in match_errors
    )
    add_check(
        checks,
        "unsafe_action_shapes_absent",
        not any(flags.values()) and intent_ok,
        "no protected status path, raw command key, action-budget violation, undeclared path, final-status language, or unsafe intent",
        {**flags, "runtime_intent_is_safe": intent_ok},
    )

    should_execute = all(check["status"] == "PASS" for check in checks)
    denied_actions = list(denied_from_match)
    action_order: list[dict[str, Any]] = []
    artifact_hashes: dict[str, str] = {}
    if should_execute:
        for action in actions:
            artifact_path = resolve_artifact_path(run_dir, action["artifact_path"])
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(action["content"], encoding="utf-8")
            digest = sha256_text(action["content"])
            artifact_hashes[action["artifact_path"]] = digest
            action_order.append(action_order_entry(action, "EXECUTED"))
    else:
        global_errors = [error for check in checks if check["status"] != "PASS" for error in (check["actual"] if isinstance(check["actual"], list) else [str(check["actual"])])]
        for action in actions:
            reason = "; ".join(global_errors) if global_errors else "guarded execution failed closed"
            action_order.append(action_order_entry(action, "DENIED", reason))
            if not any(item.get("action_id") == action["action_id"] and item.get("artifact_path") == action["artifact_path"] for item in denied_actions):
                deny(denied_actions, action["action_id"], action["artifact_path"], reason)

    status = "GUARDED_EXECUTION_V2_PASS" if should_execute else "GUARDED_EXECUTION_V2_FAIL"
    ledger = {
        "schema_version": "guarded_execution_v2_ledger_v1",
        "run_id": run_id,
        "status": status,
        "preflight_checked": True,
        "min_actions": MIN_ACTIONS,
        "max_actions": MAX_ACTIONS,
        "action_count_planned": len(actions),
        "action_count_executed": len([item for item in action_order if item["status"] == "EXECUTED"]),
        "action_count_denied": len([item for item in action_order if item["status"] == "DENIED"]),
        "action_order": action_order,
        "denied_actions": denied_actions,
        "artifact_hashes": artifact_hashes,
        "goal_execution_attempted": False,
        "arbitrary_command_attempted": flags["arbitrary_command_attempted"],
        "protected_status_write_attempted": flags["protected_status_write_attempted"],
        "final_status_language_denied": flags["final_status_language_denied"],
        "over_budget_attempted": flags["over_budget_attempted"],
        "under_budget_attempted": flags["under_budget_attempted"],
        "undeclared_path_attempted": flags["undeclared_path_attempted"],
        "status_authority": "certifier_only",
        "requires_policy_certifier_for_status": True,
        "can_certify_done": False,
    }
    report = {
        "schema_version": "guarded_execution_v2_report_v1",
        "status": status,
        "authority": REQUIRED_AUTHORITY,
        "runtime_intent": runtime_intent,
        "source_reports": {
            "stage3_runtime_preflight_report": rel_path(preflight_path),
            "bounded_plan": rel_path(plan_path),
            "expected_artifacts": rel_path(expected_artifacts_path),
        },
        "criteria": checks,
        "runtime_execution": {
            "run_id": run_id,
            "preflight_checked": True,
            "min_actions": MIN_ACTIONS,
            "max_actions": MAX_ACTIONS,
            "action_count_planned": len(actions),
            "action_count_executed": ledger["action_count_executed"],
            "action_count_denied": ledger["action_count_denied"],
            "safe_artifacts_written": ledger["action_count_executed"],
            "ledger_artifact": f"artifacts/{DEFAULT_LEDGER_NAME}",
            "artifact_hashes": artifact_hashes,
            "produced_artifact_paths": sorted(artifact_hashes),
            "goal_execution_attempted": False,
            "arbitrary_command_attempted": flags["arbitrary_command_attempted"],
            "protected_status_write_attempted": flags["protected_status_write_attempted"],
            "final_status_language_denied": flags["final_status_language_denied"],
            "over_budget_attempted": flags["over_budget_attempted"],
            "under_budget_attempted": flags["under_budget_attempted"],
            "undeclared_path_attempted": flags["undeclared_path_attempted"],
            "status_authority": "certifier_only",
            "requires_policy_certifier_for_status": True,
            "can_certify_done": False,
        },
        "summary": {
            "preflight_status": preflight.get("status"),
            "criteria_passed": sum(1 for check in checks if check["status"] == "PASS"),
            "criteria_total": len(checks),
            "declared_artifact_count": len(declared),
            "planned_action_count": len(actions),
        },
        "claim_boundary": "Guarded Execution v2 proves a bounded declared plan can write only declared non-authority artifacts after a passing Stage 3 preflight. It does not execute arbitrary goals, decide policy, certify DONE, or prove arbitrary runtime safety.",
    }
    return report, ledger


def validate_execution_report(report: dict[str, Any], ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "guarded_execution_v2_report_v1":
        errors.append("schema_version must be guarded_execution_v2_report_v1")
    if ledger.get("schema_version") != "guarded_execution_v2_ledger_v1":
        errors.append("ledger schema_version must be guarded_execution_v2_ledger_v1")
    if report.get("authority") != REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    if contains_final_status_value(report) or contains_final_status_value(ledger):
        errors.append("guarded execution v2 artifacts must not contain final status enum values")
    runtime_execution = report.get("runtime_execution", {})
    for obj_name, obj in [("runtime_execution", runtime_execution), ("ledger", ledger)]:
        if obj.get("goal_execution_attempted") is not False:
            errors.append(f"{obj_name}.goal_execution_attempted must be false")
        if obj.get("can_certify_done") is not False:
            errors.append(f"{obj_name}.can_certify_done must be false")
        if obj.get("status_authority") != "certifier_only":
            errors.append(f"{obj_name}.status_authority must be certifier_only")
        if obj.get("requires_policy_certifier_for_status") is not True:
            errors.append(f"{obj_name}.requires_policy_certifier_for_status must be true")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
    else:
        expected_status = "GUARDED_EXECUTION_V2_PASS" if all(check.get("status") == "PASS" for check in criteria) else "GUARDED_EXECUTION_V2_FAIL"
        if report.get("status") != expected_status:
            errors.append(f"status must be {expected_status}")
        if ledger.get("status") != expected_status:
            errors.append(f"ledger status must be {expected_status}")
    if report.get("status") == "GUARDED_EXECUTION_V2_PASS":
        if runtime_execution.get("action_count_executed", 0) < 1:
            errors.append("passing guarded execution v2 must execute at least one action")
        if runtime_execution.get("action_count_executed") != ledger.get("action_count_executed"):
            errors.append("report and ledger executed action counts must match")
        if ledger.get("action_count_denied") != 0:
            errors.append("passing guarded execution v2 must have zero denied actions")
        if not ledger.get("artifact_hashes"):
            errors.append("passing guarded execution v2 must record artifact hashes")
    else:
        if runtime_execution.get("action_count_executed") != 0:
            errors.append("failing guarded execution v2 must execute zero actions")
        if ledger.get("action_count_executed") != 0:
            errors.append("failing guarded execution v2 ledger must execute zero actions")
    if ledger.get("action_count_planned", 0) > MAX_ACTIONS:
        if ledger.get("action_count_executed") != 0:
            errors.append("over-budget guarded execution v2 must execute zero actions")
    if 0 < ledger.get("action_count_planned", 0) < MIN_ACTIONS:
        if ledger.get("action_count_executed") != 0:
            errors.append("under-budget guarded execution v2 must execute zero actions")
    return errors


def guarded_output_path(raw_path: str | None, default_path: Path) -> Path:
    path = Path(raw_path) if raw_path else default_path
    if path.name in PROTECTED_OUTPUT_NAMES:
        raise ValueError(f"refusing to write protected status artifact: {path}")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Guarded Execution v2 bounded plan execution")
    parser.add_argument("--preflight-report", default=str(DEFAULT_PREFLIGHT_REPORT))
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--expected-artifacts", default=str(DEFAULT_EXPECTED_ARTIFACTS))
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--runtime-intent", default="bounded_plan_artifact_writes")
    parser.add_argument("--output")
    parser.add_argument("--ledger-output")
    args = parser.parse_args(argv)

    try:
        run_dir = run_dir_for_id(args.run_id)
        report_path = guarded_output_path(args.output, run_dir / "guarded_execution_v2_report.json")
        ledger_path = guarded_output_path(args.ledger_output, run_dir / "artifacts" / DEFAULT_LEDGER_NAME)
        report, ledger = build_execution_report(
            load_required_json(Path(args.preflight_report), "preflight report"),
            Path(args.preflight_report),
            load_required_json(Path(args.plan), "bounded plan"),
            Path(args.plan),
            load_required_json(Path(args.expected_artifacts), "expected artifacts"),
            Path(args.expected_artifacts),
            args.run_id,
            args.runtime_intent,
        )
        errors = validate_execution_report(report, ledger)
        write_json(ledger_path, ledger)
        write_json(report_path, report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report["status"] != "GUARDED_EXECUTION_V2_PASS":
        for check in report["criteria"]:
            if check["status"] != "PASS":
                print(f"FAIL: {check['check_id']}: expected {check['expected']}, actual {check['actual']}", file=sys.stderr)
        return 1
    print(f"OK: {report['status']} ({len(report['criteria'])} checks) -> {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
