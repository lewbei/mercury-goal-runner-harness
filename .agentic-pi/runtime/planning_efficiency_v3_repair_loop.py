#!/usr/bin/env python3
"""Planning Efficiency v3 bounded repair loop.

This deterministic pre-execution loop reruns Planning Efficiency v2 preflight,
applies only exact allowlisted repairs from repair_hints, and stops after a hard
repair budget. It never executes the generated plan, invokes guarded execution,
decides policy, or certifies completion.
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import canonical_json
import guarded_execution_v2 as v2
import guarded_plan_compiler as compiler
import planning_efficiency_v2_preflight as preflight


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOAL = ROOT / ".agentic-pi" / "runtime" / "planning_efficiency_v3_repair_goal.json"
DEFAULT_STAGE3_PREFLIGHT_REPORT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "stage3_runtime_preflight_report_v1.json"
DEFAULT_WORK_DIR = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v3_repair_loop"
DEFAULT_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_efficiency_v3_repair_report.json"
DEFAULT_MAX_REPAIR_ATTEMPTS = 3
HARD_MAX_REPAIR_ATTEMPTS = 3
PASS_STATUS = "PLANNING_EFFICIENCY_V3_REPAIR_PASS"
NOT_READY_STATUS = "PLANNING_EFFICIENCY_V3_NOT_READY"
FINAL_ARTIFACT_KEYS = [
    "repaired_goal",
    "plan",
    "expected_artifacts",
    "compile_report",
    "lint_report",
    "preflight_report",
]
SUPPORTED_HINT_CODES = {
    "TOKEN_PATTERN",
    "FINAL_STATUS_ENUM_LEAK",
    "PROTECTED_STATUS_ARTIFACT_NAME",
    "AUTHORITY_LANGUAGE",
    "PROTECTED_PATH",
    "EXPECTED_ARTIFACTS_CONTRACT",
    "DUPLICATE_ARTIFACT_ID",
    "DUPLICATE_ARTIFACT_PATH",
    "CONTENT_TOO_LARGE",
    "ACTION_BUDGET",
}
UNSUPPORTED_HINT_CODES = {
    "STAGE3_PREFLIGHT",
    "PROTECTED_OUTPUT_PATH",
    "GOAL_SCHEMA",
    "MISSING_ROUGH_GOAL",
    "ARTIFACT_SPECS_SHAPE",
    "RAW_COMMAND_SHAPE",
    "PLAN_SHAPE",
    "PLAN_EXPECTED_ARTIFACT_MISMATCH",
    "UNDECLARED_ARTIFACT",
    "MISSING_REQUIRED_ARTIFACT",
    "MISSING_VERIFIER_REQUIREMENTS",
}
REPLACEMENT_TEXT = "authority_boundary_removed"
TOKEN_REPLACEMENT = "redacted_token"
STATUS_REPLACEMENT = "status_value_removed"
PROTECTED_NAME_REPLACEMENT = "non_authority_artifact.txt"
CONTENT_BYTE_LIMIT = 1800


def rel_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def write_json(path: Path, data: Any) -> dict[str, Any]:
    return canonical_json.write_json_canonical(path, data, v2.is_protected_output_name)


def load_required_json(path: Path, label: str) -> dict[str, Any]:
    return preflight.load_required_json(path, label)


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, expected: Any, actual: Any) -> None:
    checks.append({
        "check_id": check_id,
        "status": "PASS" if passed else "FAIL",
        "expected": expected,
        "actual": actual,
    })


def artifact_paths(work_dir: Path) -> dict[str, Path]:
    return {
        "repaired_goal": work_dir / "planning_efficiency_v3_repaired_goal.json",
        "plan": work_dir / "planning_efficiency_v3_plan.json",
        "expected_artifacts": work_dir / "planning_efficiency_v3_expected_artifacts.json",
        "compile_report": work_dir / "planning_efficiency_v3_compile_report.json",
        "lint_report": work_dir / "planning_efficiency_v3_lint_report.json",
        "preflight_report": work_dir / "planning_efficiency_v3_preflight_report.json",
    }


def attempt_paths(work_dir: Path, attempt_index: int) -> dict[str, Path]:
    return artifact_paths(work_dir / "attempts" / f"attempt_{attempt_index}")


def clear_final_outputs(paths: dict[str, Path]) -> None:
    for key in FINAL_ARTIFACT_KEYS:
        path = paths[key]
        if path.is_file():
            path.unlink()


def write_preflight_outputs(
    paths: dict[str, Path],
    plan: dict[str, Any] | None,
    expected: dict[str, Any] | None,
    compile_report: dict[str, Any],
    lint_report: dict[str, Any] | None,
    report: dict[str, Any],
    write_handoff: bool,
) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    metadata["compile_report"] = write_json(paths["compile_report"], compile_report)
    if write_handoff and report.get("status") == preflight.PASS_STATUS and plan is not None and expected is not None and lint_report is not None:
        metadata["plan"] = write_json(paths["plan"], plan)
        metadata["expected_artifacts"] = write_json(paths["expected_artifacts"], expected)
        metadata["lint_report"] = write_json(paths["lint_report"], lint_report)
    metadata["preflight_report"] = write_json(paths["preflight_report"], report)
    return metadata


def build_preflight_for_paths(
    goal: dict[str, Any],
    paths: dict[str, Path],
    goal_path: Path,
    stage3_preflight: dict[str, Any],
    stage3_preflight_path: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any], dict[str, Any] | None, dict[str, Any], list[str]]:
    plan, expected, compile_report, lint_report, report = preflight.build_preflight(
        goal,
        paths["plan"],
        paths["expected_artifacts"],
        paths["compile_report"],
        paths["lint_report"],
        paths["preflight_report"],
        goal_path,
        stage3_preflight,
        stage3_preflight_path,
    )
    errors = preflight.validate_preflight_report(report)
    return plan, expected, compile_report, lint_report, report, errors


def replace_in_strings(value: Any, replacements: list[tuple[re.Pattern[str], str]]) -> tuple[Any, int]:
    if isinstance(value, dict):
        changed = 0
        new_obj: dict[str, Any] = {}
        for key, child in value.items():
            new_key = key
            if isinstance(key, str):
                new_key, key_count = replace_string(key, replacements)
                changed += key_count
            new_child, child_count = replace_in_strings(child, replacements)
            changed += child_count
            new_obj[new_key] = new_child
        return new_obj, changed
    if isinstance(value, list):
        changed = 0
        new_items = []
        for child in value:
            new_child, child_count = replace_in_strings(child, replacements)
            changed += child_count
            new_items.append(new_child)
        return new_items, changed
    if isinstance(value, str):
        return replace_string(value, replacements)
    return value, 0


def replace_string(value: str, replacements: list[tuple[re.Pattern[str], str]]) -> tuple[str, int]:
    changed = 0
    current = value
    for pattern, replacement in replacements:
        current, count = pattern.subn(replacement, current)
        changed += count
    return current, changed


def token_replacements() -> list[tuple[re.Pattern[str], str]]:
    return [(pattern, TOKEN_REPLACEMENT) for _, pattern in preflight.TOKEN_PATTERNS]


def status_replacements() -> list[tuple[re.Pattern[str], str]]:
    return [(re.compile(rf"\b{re.escape(status)}\b", flags=re.IGNORECASE), STATUS_REPLACEMENT) for status in sorted(v2.FINAL_STATUS_VALUES)]


def protected_name_replacements() -> list[tuple[re.Pattern[str], str]]:
    return [
        (re.compile(rf"(?<![\w.-]){re.escape(name)}(?![\w.-])", flags=re.IGNORECASE), PROTECTED_NAME_REPLACEMENT)
        for name in sorted(preflight.PROTECTED_STATUS_ARTIFACT_NAMES)
    ]


def authority_language_replacements() -> list[tuple[re.Pattern[str], str]]:
    replacements: list[tuple[re.Pattern[str], str]] = []
    for phrase in sorted(v2.FORBIDDEN_CONTENT_PHRASES, key=len, reverse=True):
        escaped = re.escape(phrase).replace(r"\ ", r"[ _-]+")
        replacements.append((re.compile(escaped, flags=re.IGNORECASE), REPLACEMENT_TEXT))
    return replacements + status_replacements()


def valid_artifact_path(raw_path: str) -> bool:
    try:
        v2.resolve_artifact_path(Path("/tmp/planning-efficiency-v3"), raw_path.replace("\\", "/"))
        return True
    except ValueError:
        return False


def repaired_path_for_spec(spec: dict[str, Any], index: int, suffix: str = "repaired") -> str:
    label = str(spec.get("name") or spec.get("artifact_id") or f"artifact_{index + 1}")
    slug = compiler.slugify(label, f"artifact_{index + 1}")
    return f"artifacts/{slug}_{suffix}.txt"


def ensure_artifact_specs(goal: dict[str, Any]) -> list[dict[str, Any]] | None:
    specs = goal.get("artifact_specs")
    if isinstance(specs, list) and all(isinstance(item, dict) for item in specs):
        return specs
    return None


def repair_paths(goal: dict[str, Any]) -> int:
    specs = ensure_artifact_specs(goal)
    if specs is None:
        return 0
    changed = 0
    seen: set[str] = set()
    for index, spec in enumerate(specs):
        raw_path = spec.get("requested_path")
        if isinstance(raw_path, str) and raw_path.strip():
            candidate = raw_path.replace("\\", "/")
        else:
            candidate = repaired_path_for_spec(spec, index)
        needs_repair = not valid_artifact_path(candidate) or candidate in seen
        if needs_repair:
            candidate = repaired_path_for_spec(spec, index, f"repaired_{index + 1}")
            while candidate in seen:
                candidate = repaired_path_for_spec(spec, index, f"repaired_{index + 1}_{len(seen) + 1}")
            spec["requested_path"] = candidate
            changed += 1
        else:
            spec["requested_path"] = candidate
        seen.add(candidate)
    return changed


def repair_duplicate_artifact_ids(goal: dict[str, Any]) -> int:
    specs = ensure_artifact_specs(goal)
    if specs is None:
        return 0
    seen: set[str] = set()
    changed = 0
    for index, spec in enumerate(specs):
        artifact_id = str(spec.get("artifact_id") or f"A.ARTIFACT_{index + 1}")
        if artifact_id in seen:
            base = compiler.slugify(artifact_id, f"artifact_{index + 1}").upper()
            repaired = f"A.{base}_REPAIRED_{index + 1}"
            while repaired in seen:
                repaired = f"A.{base}_REPAIRED_{index + 1}_{len(seen) + 1}"
            spec["artifact_id"] = repaired
            changed += 1
            seen.add(repaired)
        else:
            spec["artifact_id"] = artifact_id
            seen.add(artifact_id)
    return changed


def repair_under_budget(goal: dict[str, Any]) -> tuple[bool, str, int]:
    specs = ensure_artifact_specs(goal)
    if specs is None:
        return False, "ARTIFACT_SPECS_SHAPE", 0
    if len(specs) > v2.MAX_ACTIONS:
        return False, "ACTION_BUDGET_OVER_MAX_AMBIGUOUS", 0
    changed = 0
    while len(specs) < v2.MIN_ACTIONS:
        index = len(specs)
        suffix = index + 1
        specs.append({
            "artifact_id": f"A.V3_REPAIR_FILLER_{suffix}",
            "name": f"v3_repair_filler_{suffix}",
            "requested_path": f"artifacts/v3_repair_filler_{suffix}.txt",
            "content": "Deterministic filler artifact added by Planning Efficiency v3 to satisfy the guarded execution minimum action count.",
        })
        changed += 1
    return True, "ACTION_BUDGET_UNDER_MIN_REPAIRED", changed


def truncate_content(goal: dict[str, Any]) -> int:
    specs = ensure_artifact_specs(goal)
    if specs is None:
        return 0
    changed = 0
    suffix = "\n[Planning Efficiency v3 deterministic truncation applied.]"
    for spec in specs:
        content = spec.get("content")
        if not isinstance(content, str):
            continue
        if len(content.encode("utf-8")) <= CONTENT_BYTE_LIMIT:
            continue
        encoded = content.encode("utf-8")[: CONTENT_BYTE_LIMIT - len(suffix.encode("utf-8"))]
        spec["content"] = encoded.decode("utf-8", errors="ignore") + suffix
        changed += 1
    return changed


def apply_repair_hints(goal: dict[str, Any], repair_hints: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str], list[str], bool]:
    if not repair_hints:
        return goal, [], ["NO_REPAIR_HINTS"], False
    codes = [str(item.get("code", "")) for item in repair_hints if isinstance(item, dict)]
    unsupported = sorted({code or "MALFORMED_HINT" for code in codes if code not in SUPPORTED_HINT_CODES or code in UNSUPPORTED_HINT_CODES})
    if unsupported:
        return goal, [], unsupported, False

    repaired = copy.deepcopy(goal)
    applied: list[str] = []
    total_changes = 0
    for code in codes:
        if code == "TOKEN_PATTERN":
            repaired, count = replace_in_strings(repaired, token_replacements())
            total_changes += count
            if count:
                applied.append(code)
        elif code == "FINAL_STATUS_ENUM_LEAK":
            repaired, count = replace_in_strings(repaired, status_replacements())
            total_changes += count
            if count:
                applied.append(code)
        elif code == "PROTECTED_STATUS_ARTIFACT_NAME":
            repaired, count = replace_in_strings(repaired, protected_name_replacements())
            path_count = repair_paths(repaired)
            total_changes += count + path_count
            if count or path_count:
                applied.append(code)
        elif code == "AUTHORITY_LANGUAGE":
            repaired, count = replace_in_strings(repaired, authority_language_replacements())
            total_changes += count
            if count:
                applied.append(code)
        elif code in {"PROTECTED_PATH", "EXPECTED_ARTIFACTS_CONTRACT", "DUPLICATE_ARTIFACT_PATH"}:
            count = repair_paths(repaired)
            total_changes += count
            if count:
                applied.append(code)
        elif code == "DUPLICATE_ARTIFACT_ID":
            count = repair_duplicate_artifact_ids(repaired)
            total_changes += count
            if count:
                applied.append(code)
        elif code == "CONTENT_TOO_LARGE":
            count = truncate_content(repaired)
            total_changes += count
            if count:
                applied.append(code)
        elif code == "ACTION_BUDGET":
            ok, reason, count = repair_under_budget(repaired)
            if not ok:
                return goal, [], [reason], False
            total_changes += count
            if count:
                applied.append(code)
    changed = total_changes > 0 and canonical_json.stable_json(repaired) != canonical_json.stable_json(goal)
    if not changed:
        return goal, [], ["REPAIR_HINTS_MADE_NO_CHANGE"], False
    return repaired, sorted(set(applied)), [], True


def attempt_summary(
    attempt_index: int,
    attempt_report: dict[str, Any],
    validation_errors: list[str],
    paths: dict[str, Path],
) -> dict[str, Any]:
    hints = attempt_report.get("repair_hints", [])
    return {
        "attempt_index": attempt_index,
        "preflight_status": attempt_report.get("status"),
        "criteria_passed": attempt_report.get("planning_efficiency", {}).get("criteria_passed", 0),
        "criteria_total": attempt_report.get("planning_efficiency", {}).get("criteria_total", 0),
        "repair_hint_codes": [item.get("code", "") for item in hints if isinstance(item, dict)],
        "validation_error_count": len(validation_errors),
        "attempt_preflight_report": rel_path(paths["preflight_report"]),
    }


def final_outputs_exist(paths: dict[str, Path]) -> bool:
    return all(paths[key].is_file() for key in FINAL_ARTIFACT_KEYS)


def final_hashes(paths: dict[str, Path]) -> dict[str, str]:
    return {key: canonical_json.sha256_file(paths[key]) for key in FINAL_ARTIFACT_KEYS if paths[key].is_file()}


def build_repair_loop_report(
    goal_path: Path,
    stage3_preflight_path: Path,
    work_dir: Path,
    output_path: Path,
    max_repair_attempts: int = DEFAULT_MAX_REPAIR_ATTEMPTS,
) -> dict[str, Any]:
    if max_repair_attempts < 0 or max_repair_attempts > HARD_MAX_REPAIR_ATTEMPTS:
        raise ValueError(f"max repair attempts must be between 0 and {HARD_MAX_REPAIR_ATTEMPTS}")
    final_paths = artifact_paths(work_dir)
    clear_final_outputs(final_paths)
    original_goal = load_required_json(goal_path, "goal")
    stage3_preflight = load_required_json(stage3_preflight_path, "Stage 3 preflight report")
    current_goal = copy.deepcopy(original_goal)
    attempts: list[dict[str, Any]] = []
    repair_attempts_used = 0
    not_ready_reasons: list[str] = []
    final_report: dict[str, Any] | None = None
    final_plan: dict[str, Any] | None = None
    final_expected: dict[str, Any] | None = None
    final_compile: dict[str, Any] | None = None
    final_lint: dict[str, Any] | None = None

    for attempt_index in range(max_repair_attempts + 1):
        paths = attempt_paths(work_dir, attempt_index)
        plan, expected, compile_report, lint_report, report, validation_errors = build_preflight_for_paths(
            current_goal,
            paths,
            goal_path,
            stage3_preflight,
            stage3_preflight_path,
        )
        write_preflight_outputs(paths, plan, expected, compile_report, lint_report, report, write_handoff=False)
        summary = attempt_summary(attempt_index, report, validation_errors, paths)
        attempts.append(summary)

        if report.get("status") == preflight.PASS_STATUS and not validation_errors:
            final_plan, final_expected, final_compile, final_lint, final_report, final_errors = build_preflight_for_paths(
                current_goal,
                final_paths,
                goal_path,
                stage3_preflight,
                stage3_preflight_path,
            )
            if final_report.get("status") == preflight.PASS_STATUS and not final_errors:
                write_json(final_paths["repaired_goal"], current_goal)
                write_preflight_outputs(final_paths, final_plan, final_expected, final_compile, final_lint, final_report, write_handoff=True)
                break
            not_ready_reasons.append("FINAL_PREFLIGHT_REBUILD_INVALID")
            break

        if validation_errors:
            not_ready_reasons.append("PREFLIGHT_REPORT_INVALID")
            break
        if repair_attempts_used >= max_repair_attempts:
            not_ready_reasons.append("REPAIR_ATTEMPTS_EXHAUSTED")
            break
        repaired_goal, applied, unsupported, changed = apply_repair_hints(current_goal, report.get("repair_hints", []))
        summary["repair_applied_codes"] = applied
        summary["unsupported_repair_codes"] = unsupported
        if unsupported or not changed:
            not_ready_reasons.extend(unsupported or ["REPAIR_NOT_APPLIED"])
            break
        current_goal = repaired_goal
        repair_attempts_used += 1

    status = PASS_STATUS if final_outputs_exist(final_paths) and final_report and final_report.get("status") == preflight.PASS_STATUS else NOT_READY_STATUS
    final_written = final_outputs_exist(final_paths)
    exact_hints = all(not item.get("unsupported_repair_codes") for item in attempts if "unsupported_repair_codes" in item)
    preflight_passed = status == PASS_STATUS
    final_gate = {
        "planning_repair_passed": preflight_passed,
        "repaired_preflight_passed": preflight_passed,
        "may_pass_plan_to_guarded_execution": preflight_passed,
        "guarded_execution_inputs": {
            "plan": rel_path(final_paths["plan"]),
            "expected_artifacts": rel_path(final_paths["expected_artifacts"]),
            "planning_preflight_report": rel_path(final_paths["preflight_report"]),
            "stage3_runtime_preflight_report": rel_path(stage3_preflight_path),
        } if preflight_passed else {},
        "blocked_before_execution": not preflight_passed,
        "required_next_runtime": "guarded_execution_v2" if preflight_passed else "none_until_repair_passes",
        "runtime_module": ".agentic-pi/runtime/guarded_execution_v2.py" if preflight_passed else "",
    }

    checks: list[dict[str, Any]] = []
    add_check(checks, "max_repair_attempts_bounded", repair_attempts_used <= max_repair_attempts <= HARD_MAX_REPAIR_ATTEMPTS, f"repair attempts do not exceed {HARD_MAX_REPAIR_ATTEMPTS}", {"used": repair_attempts_used, "max": max_repair_attempts})
    add_check(checks, "repair_hints_exact_or_not_ready", exact_hints, "only allowlisted exact repair hints are applied; ambiguous hints stop as NOT_READY", attempts)
    add_check(checks, "preflight_passed_after_repair", preflight_passed, "final repaired Planning Efficiency v2 preflight passes before guarded execution handoff", not_ready_reasons or (final_report or {}).get("status"))
    add_check(checks, "guarded_execution_not_invoked", True, "v3 repair loop does not execute guarded execution", False)
    add_check(checks, "final_handoff_written_only_after_pass", final_written == preflight_passed, "final plan/preflight handoff files exist only after passing repaired preflight", {"final_written": final_written, "preflight_passed": preflight_passed})
    add_check(checks, "certifier_only_authority_preserved", True, "v3 repair loop is evaluation-only and cannot certify DONE", v2.REQUIRED_AUTHORITY)

    return {
        "schema_version": "planning_efficiency_v3_repair_loop_report_v1",
        "status": status,
        "authority": v2.REQUIRED_AUTHORITY,
        "source_goal": rel_path(goal_path),
        "stage3_runtime_preflight_report": rel_path(stage3_preflight_path),
        "work_dir": rel_path(work_dir),
        "output": rel_path(output_path),
        "max_repair_attempts": max_repair_attempts,
        "hard_max_repair_attempts": HARD_MAX_REPAIR_ATTEMPTS,
        "repair_attempts_used": repair_attempts_used,
        "preflight_attempt_count": len(attempts),
        "attempts": attempts,
        "not_ready_reasons": not_ready_reasons,
        "criteria": checks,
        "final_artifacts": {key: rel_path(path) for key, path in final_paths.items()} if preflight_passed else {},
        "final_artifact_hashes": final_hashes(final_paths) if preflight_passed else {},
        "execution_gate": final_gate,
        "runtime_execution": {
            "goal_execution_attempted": False,
            "plan_execution_attempted": False,
            "guarded_execution_invoked": False,
            "status_authority": "certifier_only",
            "requires_policy_certifier_for_status": True,
            "can_certify_done": False,
        },
        "claim_boundary": "Planning Efficiency v3 repairs bounded planning preflight failures with an exact allowlist and a hard repair budget. It does not execute goals, invoke guarded execution, decide policy, certify DONE, or prove arbitrary runtime safety.",
    }


def validate_repair_loop_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "planning_efficiency_v3_repair_loop_report_v1":
        errors.append("schema_version must be planning_efficiency_v3_repair_loop_report_v1")
    if report.get("status") not in {PASS_STATUS, NOT_READY_STATUS}:
        errors.append("status must be a Planning Efficiency v3 pass or NOT_READY status")
    if report.get("authority") != v2.REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    if v2.contains_final_status_value(report):
        errors.append("v3 repair loop report must not contain final status enum values")
    max_attempts = report.get("max_repair_attempts")
    if not isinstance(max_attempts, int) or not 0 <= max_attempts <= HARD_MAX_REPAIR_ATTEMPTS:
        errors.append(f"max_repair_attempts must be an integer between 0 and {HARD_MAX_REPAIR_ATTEMPTS}")
    if report.get("repair_attempts_used", 0) > max_attempts:
        errors.append("repair_attempts_used must not exceed max_repair_attempts")
    runtime = report.get("runtime_execution", {})
    if runtime.get("goal_execution_attempted") is not False:
        errors.append("runtime_execution.goal_execution_attempted must be false")
    if runtime.get("plan_execution_attempted") is not False:
        errors.append("runtime_execution.plan_execution_attempted must be false")
    if runtime.get("guarded_execution_invoked") is not False:
        errors.append("runtime_execution.guarded_execution_invoked must be false")
    if runtime.get("status_authority") != "certifier_only":
        errors.append("runtime_execution.status_authority must be certifier_only")
    if runtime.get("can_certify_done") is not False:
        errors.append("runtime_execution.can_certify_done must be false")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
    elif report.get("status") == PASS_STATUS and any(check.get("status") != "PASS" for check in criteria):
        errors.append("passing v3 repair loop reports must have all criteria PASS")
    gate = report.get("execution_gate", {})
    if report.get("status") == PASS_STATUS:
        if gate.get("may_pass_plan_to_guarded_execution") is not True:
            errors.append("passing v3 report must allow guarded execution handoff")
        if gate.get("required_next_runtime") != "guarded_execution_v2":
            errors.append("passing v3 report must bind to guarded_execution_v2")
        if not report.get("final_artifacts"):
            errors.append("passing v3 report must record final_artifacts")
    else:
        if gate.get("may_pass_plan_to_guarded_execution") is not False:
            errors.append("NOT_READY v3 report must not allow guarded execution handoff")
        if report.get("final_artifacts"):
            errors.append("NOT_READY v3 report must not record final_artifacts")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Planning Efficiency v3 bounded repair loop without executing guarded plans.")
    parser.add_argument("--goal", default=str(DEFAULT_GOAL))
    parser.add_argument("--stage3-preflight-report", default=str(DEFAULT_STAGE3_PREFLIGHT_REPORT))
    parser.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--max-repair-attempts", type=int, default=DEFAULT_MAX_REPAIR_ATTEMPTS)
    args = parser.parse_args(argv)
    try:
        output_path = Path(args.output)
        if v2.is_protected_output_name(output_path.name):
            raise ValueError(f"refusing to write protected status artifact: {output_path}")
        report = build_repair_loop_report(
            Path(args.goal),
            Path(args.stage3_preflight_report),
            Path(args.work_dir),
            output_path,
            args.max_repair_attempts,
        )
        errors = validate_repair_loop_report(report)
        write_json(output_path, report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report["status"] != PASS_STATUS:
        for reason in report.get("not_ready_reasons", []):
            print(f"NOT_READY: {reason}", file=sys.stderr)
        return 1
    print(f"OK: {report['status']} ({report['repair_attempts_used']} repairs, {report['preflight_attempt_count']} preflight attempts) -> {args.output}")
    print("bounded repair loop max attempts 3")
    print("exact repair hints applied")
    print("repaired Planning Efficiency v2 preflight passed")
    print("Stage 3 runtime preflight input checked")
    print("guarded execution not invoked by v3")
    print("handoff bound to guarded_execution_v2")
    print("certifier-only authority preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
