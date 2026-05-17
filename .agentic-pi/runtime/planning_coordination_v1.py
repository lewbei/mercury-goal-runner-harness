#!/usr/bin/env python3
"""Planning Coordination v1 completeness gate.

This deterministic gate coordinates existing planning routes and selects one
preflight-passing guarded-execution handoff. It does not execute guarded plans,
run arbitrary commands, decide policy, or certify completion.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import canonical_json
import guarded_execution_v2 as v2
import planning_efficiency_v2_preflight as preflight
import planning_efficiency_v3_repair_loop as repair_loop


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOAL = ROOT / ".agentic-pi" / "runtime" / "planning_coordination_v1_goal.json"
DEFAULT_STAGE3_PREFLIGHT_REPORT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "stage3_runtime_preflight_report_v1.json"
DEFAULT_WORK_DIR = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_coordination_v1"
DEFAULT_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_coordination_v1_report.json"
PASS_STATUS = "PLANNING_COORDINATION_V1_APPROVED"
NOT_READY_STATUS = "PLANNING_COORDINATION_V1_NOT_READY"
CANDIDATE_PASS_STATUS = "PREFLIGHT_PASS"
CANDIDATE_FAIL_STATUS = "PREFLIGHT_FAIL"
CANDIDATE_NOT_READY_STATUS = "GENERATOR_NOT_READY"
COMPLETENESS_APPROVED = "APPROVED_FOR_EXECUTION"
COMPLETENESS_BLOCKED_NO_VALID_CANDIDATE = "BLOCKED_NO_VALID_CANDIDATE"
COMPLETENESS_BLOCKED_AMBIGUOUS = "BLOCKED_AMBIGUOUS_SELECTION"
SUPPORTED_ROUTES = {"auto", "direct-v2", "repair-v3"}
GENERATOR_PRIORITY = {
    "direct_v2_preflight": 0,
    "planning_efficiency_v3_repair_loop": 10,
}


def rel_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def resolve_reported_path(raw_path: str) -> Path:
    candidate = Path(str(raw_path))
    if candidate.is_absolute():
        return candidate.resolve()
    return (ROOT / candidate).resolve()


def path_inside_root(path: Path) -> bool:
    resolved = path.resolve()
    root = ROOT.resolve()
    return resolved == root or root in resolved.parents


def path_allowed_for_runtime_output(path: Path) -> bool:
    """Allow temp paths and .agentic-runs paths, but not source-tree writes."""
    if not path_inside_root(path):
        return True
    try:
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return False
    return relative.startswith(".agentic-runs/")


def ensure_output_paths_allowed(*paths: Path) -> None:
    for path in paths:
        if v2.is_protected_output_name(path.name):
            raise ValueError(f"refusing to write protected status artifact: {path}")
        if not path_allowed_for_runtime_output(path):
            raise ValueError(f"runtime coordination output must be outside source files or under .agentic-runs/: {path}")


def write_json(path: Path, data: Any) -> dict[str, Any]:
    ensure_output_paths_allowed(path)
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


def failed_check_ids(report: dict[str, Any]) -> list[str]:
    return [
        str(item.get("check_id", "<unknown>"))
        for item in report.get("criteria", [])
        if isinstance(item, dict) and item.get("status") != "PASS"
    ]


def repair_hint_codes(report: dict[str, Any]) -> list[str]:
    return [
        str(item.get("code", ""))
        for item in report.get("repair_hints", [])
        if isinstance(item, dict) and item.get("code")
    ]


def direct_candidate_paths(work_dir: Path) -> dict[str, Path]:
    base = work_dir / "candidates" / "direct_v2_preflight"
    return {
        "plan": base / "direct_v2_plan.json",
        "expected_artifacts": base / "direct_v2_expected_artifacts.json",
        "compile_report": base / "direct_v2_compile_report.json",
        "lint_report": base / "direct_v2_lint_report.json",
        "preflight_report": base / "direct_v2_preflight_report.json",
    }


def repair_candidate_paths(work_dir: Path) -> dict[str, Path]:
    base = work_dir / "candidates" / "planning_efficiency_v3_repair_loop"
    return {
        "work_dir": base,
        "repair_report": base / "planning_efficiency_v3_repair_report.json",
        "repaired_goal": base / "planning_efficiency_v3_repaired_goal.json",
        "plan": base / "planning_efficiency_v3_plan.json",
        "expected_artifacts": base / "planning_efficiency_v3_expected_artifacts.json",
        "compile_report": base / "planning_efficiency_v3_compile_report.json",
        "lint_report": base / "planning_efficiency_v3_lint_report.json",
        "preflight_report": base / "planning_efficiency_v3_preflight_report.json",
    }


def planning_artifact_paths(work_dir: Path) -> dict[str, Path]:
    return {
        "candidate_plans": work_dir / "candidate_plans.json",
        "planning_assumption_matrix": work_dir / "planning_assumption_matrix.json",
        "planning_risk_attack_report": work_dir / "planning_risk_attack_report.json",
        "planning_evidence_contract": work_dir / "planning_evidence_contract.json",
        "planning_selection_decision": work_dir / "planning_selection_decision.json",
        "planning_completeness_report": work_dir / "planning_completeness_report.json",
        "coordinator_selection_ledger": work_dir / "coordinator_selection_ledger.json",
    }


def candidate_artifact_hashes(paths: dict[str, Path], keys: list[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key in keys:
        path = paths[key]
        if path.is_file():
            hashes[key] = canonical_json.sha256_file(path)
    return hashes


def score_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    passed = candidate.get("status") == CANDIDATE_PASS_STATUS
    priority = GENERATOR_PRIORITY.get(str(candidate.get("generator")), 100)
    repair_count = int(candidate.get("metrics", {}).get("repair_attempts_used", 0) or 0)
    criteria_passed = int(candidate.get("metrics", {}).get("criteria_passed", 0) or 0)
    action_count = int(candidate.get("metrics", {}).get("compiled_action_count", 0) or 0)
    if not passed:
        total = -100 - len(candidate.get("rejection_reasons", [])) - priority
    else:
        total = 1000 + (criteria_passed * 10) - (repair_count * 25) - action_count - priority
    return {
        "total": total,
        "preflight_pass_bonus": 1000 if passed else 0,
        "criteria_passed": criteria_passed,
        "repair_count_penalty": repair_count * 25,
        "estimated_step_penalty": action_count,
        "generator_priority_penalty": priority,
        "safety": 1.0 if passed else 0.0,
        "repair_count": repair_count,
        "estimated_steps": action_count,
    }


def guarded_inputs(paths: dict[str, Path], stage3_preflight_path: Path) -> dict[str, str]:
    return {
        "preflight_report": rel_path(stage3_preflight_path),
        "plan": rel_path(paths["plan"]),
        "expected_artifacts": rel_path(paths["expected_artifacts"]),
        "planning_preflight_report": rel_path(paths["preflight_report"]),
    }


def source_reports_runtime_is_nonexecuting(*reports: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for index, report in enumerate(reports):
        runtime = report.get("runtime_execution", {}) if isinstance(report, dict) else {}
        label = str(report.get("schema_version", f"report_{index}")) if isinstance(report, dict) else f"report_{index}"
        if runtime.get("goal_execution_attempted") is not False:
            errors.append(f"{label}: goal_execution_attempted must be false")
        if runtime.get("plan_execution_attempted") is not False:
            errors.append(f"{label}: plan_execution_attempted must be false")
        if runtime.get("guarded_execution_invoked", False) is not False:
            errors.append(f"{label}: guarded_execution_invoked must be false")
        if runtime.get("can_certify_done") is not False:
            errors.append(f"{label}: can_certify_done must be false")
    return not errors, errors


def handoff_is_usable(paths: dict[str, Path]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for key in ["plan", "expected_artifacts", "preflight_report"]:
        if not paths[key].is_file():
            errors.append(f"missing handoff artifact: {paths[key]}")
    if errors:
        return False, errors
    try:
        plan = load_required_json(paths["plan"], "candidate plan")
        expected = load_required_json(paths["expected_artifacts"], "candidate expected artifacts")
        planning_preflight = load_required_json(paths["preflight_report"], "candidate planning preflight")
    except Exception as exc:
        return False, [str(exc)]

    contract_ok, contract_errors, declared = v2.validate_expected_artifacts(expected)
    plan_ok, plan_errors, actions = v2.validate_plan(plan)
    match_ok, match_errors, _ = v2.validate_plan_against_contract(actions, declared) if contract_ok and plan_ok else (False, ["plan cannot be matched to expected artifacts"], [])
    preflight_ok, preflight_errors = v2.planning_preflight_is_usable(
        planning_preflight,
        plan,
        expected,
        paths["plan"].resolve(),
        paths["expected_artifacts"].resolve(),
    )
    errors.extend(contract_errors)
    errors.extend(plan_errors)
    errors.extend(match_errors)
    errors.extend(preflight_errors)
    return contract_ok and plan_ok and match_ok and preflight_ok and not errors, errors


def build_direct_candidate(goal: dict[str, Any], goal_path: Path, stage3_preflight: dict[str, Any], stage3_preflight_path: Path, work_dir: Path) -> dict[str, Any]:
    paths = direct_candidate_paths(work_dir)
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
    validation_errors = preflight.validate_preflight_report(report)
    write_json(paths["compile_report"], compile_report)
    preflight_passed = report.get("status") == preflight.PASS_STATUS and not validation_errors
    if preflight_passed and plan is not None and expected is not None and lint_report is not None:
        write_json(paths["plan"], plan)
        write_json(paths["expected_artifacts"], expected)
        write_json(paths["lint_report"], lint_report)
    write_json(paths["preflight_report"], report)

    handoff_ok, handoff_errors = handoff_is_usable(paths) if preflight_passed else (False, [])
    runtime_ok, runtime_errors = source_reports_runtime_is_nonexecuting(compile_report, lint_report or {}, report)
    failed_checks = failed_check_ids(report)
    rejection_reasons = [*validation_errors, *failed_checks, *handoff_errors, *runtime_errors]
    status = CANDIDATE_PASS_STATUS if preflight_passed and handoff_ok and runtime_ok else CANDIDATE_FAIL_STATUS
    candidate = {
        "candidate_id": "direct_v2_preflight",
        "generator": "direct_v2_preflight",
        "status": status,
        "source_goal": rel_path(goal_path),
        "artifacts": {key: rel_path(path) for key, path in paths.items()},
        "written_artifact_hashes": candidate_artifact_hashes(paths, ["plan", "expected_artifacts", "compile_report", "lint_report", "preflight_report"]),
        "guarded_execution_inputs": guarded_inputs(paths, stage3_preflight_path) if status == CANDIDATE_PASS_STATUS else {},
        "metrics": {
            "compiled_action_count": compile_report.get("planning_efficiency", {}).get("compiled_action_count", 0),
            "declared_artifact_count": compile_report.get("planning_efficiency", {}).get("declared_artifact_count", 0),
            "criteria_passed": report.get("planning_efficiency", {}).get("criteria_passed", 0),
            "criteria_total": report.get("planning_efficiency", {}).get("criteria_total", 0),
            "repair_attempts_used": 0,
        },
        "repair_hint_codes": repair_hint_codes(report),
        "failed_check_ids": failed_checks,
        "rejection_reasons": rejection_reasons,
        "runtime_execution": {
            "goal_execution_attempted": False,
            "plan_execution_attempted": False,
            "guarded_execution_invoked": False,
            "can_certify_done": False,
        },
    }
    candidate["score"] = score_candidate(candidate)
    return candidate


def build_repair_candidate(goal_path: Path, stage3_preflight_path: Path, work_dir: Path, max_repair_attempts: int) -> dict[str, Any]:
    paths = repair_candidate_paths(work_dir)
    report = repair_loop.build_repair_loop_report(
        goal_path,
        stage3_preflight_path,
        paths["work_dir"],
        paths["repair_report"],
        max_repair_attempts,
    )
    validation_errors = repair_loop.validate_repair_loop_report(report)
    write_json(paths["repair_report"], report)
    repair_passed = report.get("status") == repair_loop.PASS_STATUS and not validation_errors
    handoff_ok, handoff_errors = handoff_is_usable(paths) if repair_passed else (False, [])
    source_reports: list[dict[str, Any]] = [report]
    if paths["compile_report"].is_file():
        source_reports.append(load_required_json(paths["compile_report"], "repair candidate compile report"))
    if paths["lint_report"].is_file():
        source_reports.append(load_required_json(paths["lint_report"], "repair candidate lint report"))
    if paths["preflight_report"].is_file():
        source_reports.append(load_required_json(paths["preflight_report"], "repair candidate preflight report"))
    runtime_ok, runtime_errors = source_reports_runtime_is_nonexecuting(*source_reports)
    rejection_reasons = [*validation_errors, *report.get("not_ready_reasons", []), *handoff_errors, *runtime_errors]
    status = CANDIDATE_PASS_STATUS if repair_passed and handoff_ok and runtime_ok else CANDIDATE_NOT_READY_STATUS
    candidate = {
        "candidate_id": "planning_efficiency_v3_repair_loop",
        "generator": "planning_efficiency_v3_repair_loop",
        "status": status,
        "source_goal": rel_path(goal_path),
        "artifacts": {key: rel_path(path) for key, path in paths.items()},
        "written_artifact_hashes": candidate_artifact_hashes(paths, ["repair_report", "repaired_goal", "plan", "expected_artifacts", "compile_report", "lint_report", "preflight_report"]),
        "guarded_execution_inputs": guarded_inputs(paths, stage3_preflight_path) if status == CANDIDATE_PASS_STATUS else {},
        "metrics": {
            "compiled_action_count": report.get("planning_efficiency", {}).get("compiled_action_count", 0),
            "declared_artifact_count": report.get("planning_efficiency", {}).get("declared_artifact_count", 0),
            "criteria_passed": sum(1 for item in report.get("criteria", []) if isinstance(item, dict) and item.get("status") == "PASS"),
            "criteria_total": len(report.get("criteria", [])),
            "repair_attempts_used": report.get("repair_attempts_used", 0),
            "preflight_attempt_count": report.get("preflight_attempt_count", 0),
        },
        "repair_hint_codes": [code for attempt in report.get("attempts", []) for code in attempt.get("repair_hint_codes", []) if code],
        "failed_check_ids": failed_check_ids(report),
        "rejection_reasons": rejection_reasons,
        "runtime_execution": {
            "goal_execution_attempted": False,
            "plan_execution_attempted": False,
            "guarded_execution_invoked": False,
            "can_certify_done": False,
        },
    }
    candidate["score"] = score_candidate(candidate)
    return candidate


def select_candidate(candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, bool, str, list[dict[str, Any]]]:
    passing = [candidate for candidate in candidates if candidate.get("status") == CANDIDATE_PASS_STATUS]
    if not passing:
        rejected = [{"candidate_id": c.get("candidate_id"), "reason": c.get("rejection_reasons", []) or c.get("status")} for c in candidates]
        return None, False, "No candidate passed mandatory planning preflight and handoff checks.", rejected
    ordered = sorted(passing, key=lambda c: (-int(c.get("score", {}).get("total", -999999)), str(c.get("candidate_id"))))
    selected = ordered[0]
    ambiguous = len(ordered) > 1 and ordered[0].get("score", {}).get("total") == ordered[1].get("score", {}).get("total")
    rejected = []
    for candidate in candidates:
        if candidate is selected:
            continue
        reason = candidate.get("rejection_reasons", []) if candidate.get("status") != CANDIDATE_PASS_STATUS else [
            f"lower deterministic score than selected candidate ({candidate.get('score', {}).get('total')} < {selected.get('score', {}).get('total')})"
        ]
        rejected.append({"candidate_id": candidate.get("candidate_id"), "reason": reason})
    if ambiguous:
        return None, True, "Ambiguous candidate selection: multiple candidates share the top deterministic score.", rejected
    return selected, False, "Selected highest scoring candidate that passed mandatory preflight and handoff checks.", rejected


def build_assumption_matrix(goal_path: Path, stage3_preflight_path: Path, selected: dict[str, Any] | None) -> dict[str, Any]:
    assumptions = [
        {
            "assumption_id": "A.COORDINATOR_NON_EXECUTION",
            "statement": "The coordinator may compile, preflight, repair bounded planning artifacts, and select a handoff, but it may not execute guarded plans.",
            "source": "governance_model",
            "resolved": True,
            "evidence": "runtime_execution.guarded_execution_invoked is false for coordinator and source reports",
            "blocks_execution_if_unresolved": True,
        },
        {
            "assumption_id": "A.STAGE3_PREFLIGHT_REQUIRED",
            "statement": "A passing Stage 3 runtime preflight report is required before planning handoff can be selected.",
            "source": rel_path(stage3_preflight_path),
            "resolved": True,
            "evidence": "candidate planning preflight checks stage3_runtime_preflight_usable",
            "blocks_execution_if_unresolved": True,
        },
        {
            "assumption_id": "A.CANDIDATE_SCHEMA_SHARED",
            "statement": "Every planner route must return the same candidate schema before selection.",
            "source": rel_path(goal_path),
            "resolved": True,
            "evidence": "candidate_plans.json records candidate_id, generator, status, artifacts, score, and guarded_execution_inputs",
            "blocks_execution_if_unresolved": True,
        },
        {
            "assumption_id": "A.CERTIFIER_ONLY_AUTHORITY",
            "statement": "Planning approval is not final completion authority; policy and certifier remain required for run status.",
            "source": "AGENTS.md authority invariant",
            "resolved": True,
            "evidence": "authority.final_status_authority is certifier_only and can_certify_done is false",
            "blocks_execution_if_unresolved": True,
        },
    ]
    return {
        "schema_version": "planning_coordination_v1_assumption_matrix_v1",
        "authority": v2.REQUIRED_AUTHORITY,
        "source_goal": rel_path(goal_path),
        "selected_candidate_id": selected.get("candidate_id") if selected else "",
        "assumptions": assumptions,
    }


def build_evidence_contract(goal_path: Path, stage3_preflight_path: Path, selected: dict[str, Any] | None) -> dict[str, Any]:
    required = [
        {
            "evidence_id": "E.STAGE3_RUNTIME_PREFLIGHT",
            "path": rel_path(stage3_preflight_path),
            "required_before_selection": True,
            "validator": "guarded_execution_v2.preflight_is_usable",
        },
        {
            "evidence_id": "E.CANDIDATE_PREFLIGHT_REPORTS",
            "path": "candidate_plans.json",
            "required_before_selection": True,
            "validator": "planning_efficiency_v2_preflight.validate_preflight_report / planning_efficiency_v3_repair_loop.validate_repair_loop_report",
        },
        {
            "evidence_id": "E.SELECTION_DECISION",
            "path": "planning_selection_decision.json",
            "required_before_execution": True,
            "validator": "planning_coordination_v1.validate_coordination_report",
        },
        {
            "evidence_id": "E.DOWNSTREAM_GUARDED_EXECUTION",
            "path": "guarded_execution_v2 report and ledger after separate runtime invocation",
            "required_before_certification": True,
            "validator": "guarded_execution_v2.validate_execution_report",
        },
    ]
    return {
        "schema_version": "planning_coordination_v1_evidence_contract_v1",
        "authority": v2.REQUIRED_AUTHORITY,
        "source_goal": rel_path(goal_path),
        "selected_candidate_id": selected.get("candidate_id") if selected else "",
        "required_evidence": required,
        "forbidden_evidence_claims": [
            "planner self-certification",
            "coordinator final status authority",
            "guarded execution before preflight pass",
        ],
    }


def build_risk_attack_report(candidates: list[dict[str, Any]], selected: dict[str, Any] | None, ambiguous: bool) -> dict[str, Any]:
    risks: list[dict[str, Any]] = []
    risks.append({
        "risk_id": "R.NO_VALID_CANDIDATE",
        "status": "PASS" if selected is not None else "FAIL",
        "attack": "All routes fail but coordinator falls through to execution.",
        "mitigation": "execution_gate.may_pass_plan_to_guarded_execution is false unless a candidate passes all checks.",
    })
    risks.append({
        "risk_id": "R.AMBIGUOUS_SELECTION",
        "status": "FAIL" if ambiguous else "PASS",
        "attack": "Multiple candidates tie and the coordinator chooses nondeterministically.",
        "mitigation": "Equal top score blocks selection; non-equal candidates use deterministic score and candidate_id ordering.",
    })
    risks.append({
        "risk_id": "R.GUARDED_EXECUTION_IN_COORDINATOR",
        "status": "PASS",
        "attack": "Coordinator invokes guarded execution internally and hides runtime effects.",
        "mitigation": "Coordinator only validates handoff files and records guarded_execution_invoked false.",
    })
    risks.append({
        "risk_id": "R.AUTHORITY_LEAK",
        "status": "PASS",
        "attack": "Coordinator claims final run status instead of policy/certifier.",
        "mitigation": "All reports use evaluation_only/certifier_only authority with can_certify_done false.",
    })
    for candidate in candidates:
        risks.append({
            "risk_id": f"R.CANDIDATE_{candidate.get('candidate_id')}",
            "status": "PASS" if candidate.get("status") == CANDIDATE_PASS_STATUS else "FAIL",
            "attack": "Candidate is selected without a passing planning preflight.",
            "mitigation": candidate.get("rejection_reasons", []) or "candidate has validated guarded execution inputs",
        })
    return {
        "schema_version": "planning_coordination_v1_risk_attack_report_v1",
        "authority": v2.REQUIRED_AUTHORITY,
        "selected_candidate_id": selected.get("candidate_id") if selected else "",
        "risks": risks,
    }


def build_selection_decision(candidates: list[dict[str, Any]], selected: dict[str, Any] | None, ambiguous: bool, reason: str, rejected: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "planning_coordination_v1_selection_decision_v1",
        "authority": v2.REQUIRED_AUTHORITY,
        "selection_status": "SELECTED" if selected else (COMPLETENESS_BLOCKED_AMBIGUOUS if ambiguous else COMPLETENESS_BLOCKED_NO_VALID_CANDIDATE),
        "selected_candidate_id": selected.get("candidate_id") if selected else "",
        "selected_generator": selected.get("generator") if selected else "",
        "selection_reason": reason,
        "score_breakdown": selected.get("score", {}) if selected else {},
        "rejected_candidates": rejected,
        "candidate_scores": [{"candidate_id": c.get("candidate_id"), "score": c.get("score", {})} for c in candidates],
        "ambiguity_detected": ambiguous,
        "can_certify_done": False,
    }


def build_completeness_report(selected: dict[str, Any] | None, ambiguous: bool) -> dict[str, Any]:
    status = COMPLETENESS_APPROVED if selected else (COMPLETENESS_BLOCKED_AMBIGUOUS if ambiguous else COMPLETENESS_BLOCKED_NO_VALID_CANDIDATE)
    return {
        "schema_version": "planning_coordination_v1_completeness_report_v1",
        "authority": v2.REQUIRED_AUTHORITY,
        "status": status,
        "selected_candidate_id": selected.get("candidate_id") if selected else "",
        "blocking_failures": [] if selected else [status],
        "quality_scores": selected.get("score", {}) if selected else {},
        "execution_gate": {
            "planning_complete": selected is not None,
            "may_pass_plan_to_guarded_execution": selected is not None,
            "required_next_runtime": "guarded_execution_v2" if selected else "none_until_planning_completeness_passes",
            "runtime_module": ".agentic-pi/runtime/guarded_execution_v2.py" if selected else "",
            "guarded_execution_inputs": selected.get("guarded_execution_inputs", {}) if selected else {},
        },
        "can_certify_done": False,
    }


def build_coordination_report(
    goal_path: Path,
    stage3_preflight_path: Path,
    work_dir: Path,
    output_path: Path,
    route: str = "auto",
    max_repair_attempts: int = repair_loop.DEFAULT_MAX_REPAIR_ATTEMPTS,
) -> dict[str, Any]:
    if route not in SUPPORTED_ROUTES:
        raise ValueError(f"route must be one of {sorted(SUPPORTED_ROUTES)}")
    ensure_output_paths_allowed(work_dir, output_path)
    goal = load_required_json(goal_path, "goal")
    stage3_preflight = load_required_json(stage3_preflight_path, "Stage 3 preflight report")
    stage3_ok, stage3_errors = v2.preflight_is_usable(stage3_preflight)

    candidates: list[dict[str, Any]] = []
    routes_to_run = ["direct-v2", "repair-v3"] if route == "auto" else [route]
    if "direct-v2" in routes_to_run:
        candidates.append(build_direct_candidate(goal, goal_path, stage3_preflight, stage3_preflight_path, work_dir))
    if "repair-v3" in routes_to_run:
        candidates.append(build_repair_candidate(goal_path, stage3_preflight_path, work_dir, max_repair_attempts))

    selected, ambiguous, selection_reason, rejected = select_candidate(candidates)
    if not stage3_ok:
        selected = None
        ambiguous = False
        selection_reason = "Stage 3 runtime preflight is not usable; coordination must stop before guarded execution handoff."
        rejected = [{"candidate_id": c.get("candidate_id"), "reason": c.get("rejection_reasons", []) or stage3_errors} for c in candidates]

    artifacts = planning_artifact_paths(work_dir)
    candidate_plans = {
        "schema_version": "planning_coordination_v1_candidates_v1",
        "authority": v2.REQUIRED_AUTHORITY,
        "route": route,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "can_certify_done": False,
    }
    assumption_matrix = build_assumption_matrix(goal_path, stage3_preflight_path, selected)
    evidence_contract = build_evidence_contract(goal_path, stage3_preflight_path, selected)
    risk_attack_report = build_risk_attack_report(candidates, selected, ambiguous)
    selection_decision = build_selection_decision(candidates, selected, ambiguous, selection_reason, rejected)
    completeness_report = build_completeness_report(selected, ambiguous)
    ledger = {
        "schema_version": "planning_coordination_v1_selection_ledger_v1",
        "authority": v2.REQUIRED_AUTHORITY,
        "source_goal": rel_path(goal_path),
        "stage3_runtime_preflight_report": rel_path(stage3_preflight_path),
        "route": route,
        "generators_requested": routes_to_run,
        "selected_candidate_id": selected.get("candidate_id") if selected else "",
        "rationale": selection_reason,
        "candidate_order": [candidate.get("candidate_id") for candidate in candidates],
        "candidate_scores": [{"candidate_id": c.get("candidate_id"), "score": c.get("score", {})} for c in candidates],
        "guarded_execution_inputs": selected.get("guarded_execution_inputs", {}) if selected else {},
        "runtime_execution": {
            "goal_execution_attempted": False,
            "plan_execution_attempted": False,
            "guarded_execution_invoked": False,
            "status_authority": "certifier_only",
            "requires_policy_certifier_for_status": True,
            "can_certify_done": False,
        },
    }

    write_metadata = {
        "candidate_plans": write_json(artifacts["candidate_plans"], candidate_plans),
        "planning_assumption_matrix": write_json(artifacts["planning_assumption_matrix"], assumption_matrix),
        "planning_risk_attack_report": write_json(artifacts["planning_risk_attack_report"], risk_attack_report),
        "planning_evidence_contract": write_json(artifacts["planning_evidence_contract"], evidence_contract),
        "planning_selection_decision": write_json(artifacts["planning_selection_decision"], selection_decision),
        "planning_completeness_report": write_json(artifacts["planning_completeness_report"], completeness_report),
        "coordinator_selection_ledger": write_json(artifacts["coordinator_selection_ledger"], ledger),
    }

    criteria: list[dict[str, Any]] = []
    add_check(criteria, "stage3_runtime_preflight_usable", stage3_ok, "Stage 3 runtime preflight passes before candidate selection", stage3_errors)
    add_check(criteria, "candidate_schema_shared", bool(candidates) and all(c.get("candidate_id") and c.get("generator") and c.get("score") for c in candidates), "every route emits the shared candidate schema", [c.get("candidate_id") for c in candidates])
    add_check(criteria, "at_least_one_candidate_preflight_passed", selected is not None, "one candidate passes mandatory preflight and handoff checks", [c.get("status") for c in candidates])
    add_check(criteria, "selection_not_ambiguous", not ambiguous, "top candidate score is unique", selection_decision.get("candidate_scores"))
    add_check(criteria, "planning_completeness_blocks_or_approves", completeness_report.get("status") in {COMPLETENESS_APPROVED, COMPLETENESS_BLOCKED_AMBIGUOUS, COMPLETENESS_BLOCKED_NO_VALID_CANDIDATE}, "completeness report has a known gate status", completeness_report.get("status"))
    add_check(criteria, "guarded_execution_not_invoked", True, "coordinator does not invoke guarded execution", False)
    add_check(criteria, "certifier_only_authority_preserved", True, "coordinator is evaluation-only and cannot certify", v2.REQUIRED_AUTHORITY)

    approved = selected is not None and stage3_ok and not ambiguous
    status = PASS_STATUS if approved and all(check["status"] == "PASS" for check in criteria) else NOT_READY_STATUS
    execution_gate = {
        "planning_completeness_status": completeness_report.get("status"),
        "may_pass_plan_to_guarded_execution": approved,
        "required_next_runtime": "guarded_execution_v2" if approved else "none_until_planning_completeness_passes",
        "runtime_module": ".agentic-pi/runtime/guarded_execution_v2.py" if approved else "",
        "guarded_execution_inputs": selected.get("guarded_execution_inputs", {}) if approved else {},
        "blocked_before_execution": not approved,
    }

    return {
        "schema_version": "planning_coordination_v1_report_v1",
        "status": status,
        "authority": v2.REQUIRED_AUTHORITY,
        "source_goal": rel_path(goal_path),
        "stage3_runtime_preflight_report": rel_path(stage3_preflight_path),
        "work_dir": rel_path(work_dir),
        "output": rel_path(output_path),
        "route": route,
        "candidate_count": len(candidates),
        "selected_candidate_id": selected.get("candidate_id") if selected else "",
        "selected_generator": selected.get("generator") if selected else "",
        "selection_reason": selection_reason,
        "criteria": criteria,
        "planning_artifacts": {key: rel_path(path) for key, path in artifacts.items()},
        "planning_artifact_hashes": {key: meta["sha256"] for key, meta in write_metadata.items()},
        "source_reports": {
            "candidate_plans": rel_path(artifacts["candidate_plans"]),
            "planning_selection_decision": rel_path(artifacts["planning_selection_decision"]),
            "planning_completeness_report": rel_path(artifacts["planning_completeness_report"]),
        },
        "execution_gate": execution_gate,
        "runtime_execution": {
            "goal_execution_attempted": False,
            "plan_execution_attempted": False,
            "guarded_execution_invoked": False,
            "status_authority": "certifier_only",
            "requires_policy_certifier_for_status": True,
            "can_certify_done": False,
        },
        "claim_boundary": "Planning Coordination v1 coordinates bounded planning candidates and writes a completeness/selection ledger only. It does not execute guarded plans, decide policy, certify DONE, or prove arbitrary planning safety.",
    }


def validate_coordination_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "planning_coordination_v1_report_v1":
        errors.append("schema_version must be planning_coordination_v1_report_v1")
    if report.get("status") not in {PASS_STATUS, NOT_READY_STATUS}:
        errors.append("status must be a Planning Coordination v1 approved or NOT_READY status")
    if report.get("authority") != v2.REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    if v2.contains_final_status_value(report):
        errors.append("planning coordination report must not contain final status enum values")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
    elif report.get("status") == PASS_STATUS and any(check.get("status") != "PASS" for check in criteria):
        errors.append("approved coordination reports must have all criteria PASS")
    runtime = report.get("runtime_execution", {})
    if runtime.get("goal_execution_attempted") is not False:
        errors.append("runtime_execution.goal_execution_attempted must be false")
    if runtime.get("plan_execution_attempted") is not False:
        errors.append("runtime_execution.plan_execution_attempted must be false")
    if runtime.get("guarded_execution_invoked") is not False:
        errors.append("runtime_execution.guarded_execution_invoked must be false")
    if runtime.get("status_authority") != "certifier_only":
        errors.append("runtime_execution.status_authority must be certifier_only")
    if runtime.get("requires_policy_certifier_for_status") is not True:
        errors.append("runtime_execution.requires_policy_certifier_for_status must be true")
    if runtime.get("can_certify_done") is not False:
        errors.append("runtime_execution.can_certify_done must be false")
    gate = report.get("execution_gate", {})
    if report.get("status") == PASS_STATUS:
        if gate.get("may_pass_plan_to_guarded_execution") is not True:
            errors.append("approved coordination report must allow guarded execution handoff")
        inputs = gate.get("guarded_execution_inputs", {})
        for key in ["preflight_report", "plan", "expected_artifacts", "planning_preflight_report"]:
            if not isinstance(inputs.get(key), str) or not inputs.get(key).strip():
                errors.append(f"approved coordination report missing guarded_execution_inputs.{key}")
            else:
                input_path = resolve_reported_path(inputs[key])
                if not input_path.is_file():
                    errors.append(f"approved coordination report input does not exist: {inputs[key]}")
    else:
        if gate.get("may_pass_plan_to_guarded_execution") is not False:
            errors.append("NOT_READY coordination report must not allow guarded execution handoff")
        if gate.get("guarded_execution_inputs"):
            errors.append("NOT_READY coordination report must not expose guarded execution inputs")
    for artifact_path in report.get("planning_artifacts", {}).values():
        if not isinstance(artifact_path, str):
            errors.append("planning_artifacts values must be strings")
            continue
        if v2.is_protected_output_name(Path(artifact_path).name):
            errors.append(f"planning artifact targets protected status artifact: {artifact_path}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coordinate bounded planning candidates without executing guarded plans.")
    parser.add_argument("--goal", default=str(DEFAULT_GOAL))
    parser.add_argument("--stage3-preflight-report", default=str(DEFAULT_STAGE3_PREFLIGHT_REPORT))
    parser.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--route", choices=sorted(SUPPORTED_ROUTES), default="auto")
    parser.add_argument("--max-repair-attempts", type=int, default=repair_loop.DEFAULT_MAX_REPAIR_ATTEMPTS)
    args = parser.parse_args(argv)

    try:
        output_path = Path(args.output)
        work_dir = Path(args.work_dir)
        report = build_coordination_report(
            Path(args.goal),
            Path(args.stage3_preflight_report),
            work_dir,
            output_path,
            args.route,
            args.max_repair_attempts,
        )
        errors = validate_coordination_report(report)
        write_json(output_path, report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report["status"] != PASS_STATUS:
        print(f"NOT_READY: {report.get('selection_reason', 'planning coordination did not approve a candidate')}", file=sys.stderr)
        return 1
    print(f"OK: {report['status']} ({report['candidate_count']} candidates) -> {args.output}")
    print("planning completeness gate approved")
    print(f"selected candidate {report['selected_candidate_id']}")
    print("shared candidate schema recorded")
    print("selection ledger written")
    print("guarded execution not invoked by coordinator")
    print("handoff bound to guarded_execution_v2")
    print("certifier-only authority preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
