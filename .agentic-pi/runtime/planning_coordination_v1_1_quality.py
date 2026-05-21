#!/usr/bin/env python3
"""Planning Coordination v1.1 evidence-weighted quality gate.

This deterministic gate runs or consumes Planning Coordination v1, then applies
an evidence-weighted plan-quality score plus an explicit blocker/unknown budget
before exposing guarded_execution_v2 inputs. It does not execute guarded plans,
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
import planning_coordination_v1 as coordination
import planning_efficiency_v3_repair_loop as repair_loop


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOAL = ROOT / ".agentic-pi" / "runtime" / "planning_coordination_v1_goal.json"
DEFAULT_STAGE3_PREFLIGHT_REPORT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "stage3_runtime_preflight_report_v1.json"
DEFAULT_WORK_DIR = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_coordination_v1_1"
DEFAULT_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "planning_coordination_v1_1_quality_report.json"
PASS_STATUS = "PLANNING_COORDINATION_V1_1_QUALITY_APPROVED"
NOT_READY_STATUS = "PLANNING_COORDINATION_V1_1_NOT_READY"
PLAN_QUALITY_APPROVED = "PLAN_QUALITY_APPROVED"
PLAN_QUALITY_BLOCKED = "PLAN_QUALITY_BLOCKED"
SKEPTIC_REVIEW_APPROVED = "SKEPTIC_REVIEW_APPROVED"
SKEPTIC_REVIEW_BLOCKED = "SKEPTIC_REVIEW_BLOCKED"
ATTACK_RESOLUTION_APPROVED = "ATTACK_RESOLUTION_APPROVED"
ATTACK_RESOLUTION_BLOCKED = "ATTACK_RESOLUTION_BLOCKED"
BLOCKER_BUDGET_WITHIN = "WITHIN_BUDGET"
BLOCKER_BUDGET_EXCEEDED = "BLOCK_EXECUTION"
DEFAULT_MIN_QUALITY_SCORE = 0.85
DEFAULT_MAX_BLOCKING_UNKNOWNS = 0
DEFAULT_MAX_NONBLOCKING_UNKNOWNS = 3
CRITICAL_RISK_IDS = {
    "R.NO_VALID_CANDIDATE",
    "R.AMBIGUOUS_SELECTION",
    "R.GUARDED_EXECUTION_IN_COORDINATOR",
    "R.AUTHORITY_LEAK",
}
QUALITY_WEIGHTS = {
    "evidence_requirement_coverage": 0.12,
    "dependency_coverage": 0.12,
    "forbidden_path_safety": 0.10,
    "verifier_readiness": 0.12,
    "assumption_visibility": 0.10,
    "unknown_handling": 0.10,
    "validation_specificity": 0.07,
    "rejection_accountability": 0.03,
    "skeptic_attack_review": 0.12,
    "authority_safety": 0.12,
}


def rel_path(path: Path) -> str:
    return coordination.rel_path(path)


def resolve_reported_path(raw_path: str) -> Path:
    return coordination.resolve_reported_path(raw_path)


def write_json(path: Path, data: Any) -> dict[str, Any]:
    coordination.ensure_output_paths_allowed(path)
    return canonical_json.write_json_canonical(path, data, v2.is_protected_output_name)


def load_required_json(path: Path, label: str) -> dict[str, Any]:
    return coordination.load_required_json(path, label)


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, expected: Any, actual: Any) -> None:
    checks.append({
        "check_id": check_id,
        "status": "PASS" if passed else "FAIL",
        "expected": expected,
        "actual": actual,
    })


def quality_artifact_paths(work_dir: Path) -> dict[str, Path]:
    return {
        "coordination_work_dir": work_dir / "coordination_v1",
        "coordination_report": work_dir / "coordination_v1_report.json",
        "planning_skeptic_review_report": work_dir / "planning_skeptic_review_report.json",
        "planning_attack_resolution_report": work_dir / "planning_attack_resolution_report.json",
        "plan_quality_report": work_dir / "plan_quality_report.json",
        "blocker_budget_report": work_dir / "blocker_budget_report.json",
    }


def report_runtime_is_nonexecuting(report: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return errors
    runtime = report.get("runtime_execution")
    if runtime is None:
        if report.get("can_certify_done") is True:
            errors.append(f"{label}: can_certify_done must not be true")
        return errors
    if not isinstance(runtime, dict):
        errors.append(f"{label}: runtime_execution must be an object when present")
        return errors
    if runtime.get("goal_execution_attempted") is not False:
        errors.append(f"{label}: goal_execution_attempted must be false")
    if runtime.get("plan_execution_attempted") is not False:
        errors.append(f"{label}: plan_execution_attempted must be false")
    if runtime.get("guarded_execution_invoked", False) is not False:
        errors.append(f"{label}: guarded_execution_invoked must be false")
    if runtime.get("can_certify_done") is not False:
        errors.append(f"{label}: can_certify_done must be false")
    return errors


def add_dimension(
    dimensions: list[dict[str, Any]],
    name: str,
    score: float,
    blockers: list[str],
    warnings: list[str],
    evidence: Any,
    critical: bool = True,
) -> None:
    bounded_score = max(0.0, min(1.0, float(score)))
    dimensions.append({
        "dimension": name,
        "score": round(bounded_score, 4),
        "weight": QUALITY_WEIGHTS[name],
        "weighted_score": round(bounded_score * QUALITY_WEIGHTS[name], 4),
        "status": "PASS" if not blockers and bounded_score >= 0.999 else ("WARN" if not critical else "FAIL"),
        "blocking_failures": blockers,
        "nonblocking_warnings": warnings,
        "evidence": evidence,
        "critical": critical,
    })


def source_authority_ok(report: dict[str, Any]) -> bool:
    return report.get("authority") == v2.REQUIRED_AUTHORITY


def selected_inputs(coordination_report: dict[str, Any]) -> dict[str, str]:
    gate = coordination_report.get("execution_gate", {})
    inputs = gate.get("guarded_execution_inputs", {})
    return inputs if isinstance(inputs, dict) else {}


def load_package(coordination_report_path: Path) -> dict[str, Any]:
    coordination_report = load_required_json(coordination_report_path, "Planning Coordination v1 report")
    artifacts = coordination_report.get("planning_artifacts", {})
    package: dict[str, Any] = {"coordination_report": coordination_report}
    for key in [
        "candidate_plans",
        "planning_assumption_matrix",
        "planning_risk_attack_report",
        "planning_evidence_contract",
        "planning_selection_decision",
        "planning_completeness_report",
        "coordinator_selection_ledger",
    ]:
        raw_path = artifacts.get(key)
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"coordination report missing planning_artifacts.{key}")
        resolved_path = resolve_reported_path(raw_path)
        package[key] = load_required_json(resolved_path, key)
        package[f"{key}_path"] = resolved_path
    inputs = selected_inputs(coordination_report)
    for key in ["plan", "expected_artifacts", "planning_preflight_report", "preflight_report"]:
        raw_path = inputs.get(key)
        if not isinstance(raw_path, str) or not raw_path.strip():
            package[key] = None
            continue
        package[key] = load_required_json(resolve_reported_path(raw_path), key)
        package[f"{key}_path"] = resolve_reported_path(raw_path)
    return package


def evaluate_evidence_requirement_coverage(package: dict[str, Any]) -> tuple[float, list[str], list[str], dict[str, Any]]:
    contract = package["planning_evidence_contract"]
    required = contract.get("required_evidence", [])
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(required, list) or len(required) < 4:
        blockers.append("planning evidence contract must record at least four required evidence entries")
        return 0.0, blockers, warnings, {"required_evidence_count": len(required) if isinstance(required, list) else 0}
    usable = 0
    for item in required:
        if not isinstance(item, dict):
            warnings.append("required evidence item is not an object")
            continue
        if isinstance(item.get("evidence_id"), str) and item.get("evidence_id").strip() and isinstance(item.get("validator"), str) and item.get("validator").strip():
            usable += 1
        else:
            warnings.append(f"required evidence item lacks evidence_id or validator: {item}")
    score = usable / len(required)
    if score < 1.0:
        blockers.append("all required evidence entries must name validators")
    return score, blockers, warnings, {"required_evidence_count": len(required), "validator_named_count": usable}


def evaluate_dependency_coverage(package: dict[str, Any]) -> tuple[float, list[str], list[str], dict[str, Any]]:
    plan = package.get("plan")
    expected = package.get("expected_artifacts")
    planning_preflight = package.get("planning_preflight_report")
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(plan, dict) or not isinstance(expected, dict) or not isinstance(planning_preflight, dict):
        return 0.0, ["selected candidate handoff artifacts are missing"], warnings, {}
    contract_ok, contract_errors, declared = v2.validate_expected_artifacts(expected)
    plan_ok, plan_errors, actions = v2.validate_plan(plan)
    match_ok, match_errors, _ = v2.validate_plan_against_contract(actions, declared) if contract_ok and plan_ok else (False, ["plan cannot be matched to expected artifacts"], [])
    preflight_ok, preflight_errors = v2.planning_preflight_is_usable(
        planning_preflight,
        plan,
        expected,
        package["plan_path"].resolve(),
        package["expected_artifacts_path"].resolve(),
    )
    errors = [*contract_errors, *plan_errors, *match_errors, *preflight_errors]
    if errors:
        blockers.extend(errors)
    return 1.0 if contract_ok and plan_ok and match_ok and preflight_ok and not errors else 0.0, blockers, warnings, {
        "contract_ok": contract_ok,
        "plan_ok": plan_ok,
        "match_ok": match_ok,
        "planning_preflight_ok": preflight_ok,
        "action_count": len(actions),
        "declared_artifact_count": len(declared),
    }


def evaluate_forbidden_path_safety(package: dict[str, Any]) -> tuple[float, list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    plan = package.get("plan") or {}
    expected = package.get("expected_artifacts") or {}
    paths: list[str] = []
    for action in plan.get("actions", []) if isinstance(plan, dict) else []:
        if isinstance(action, dict) and isinstance(action.get("artifact_path"), str):
            paths.append(action["artifact_path"])
    for artifact in expected.get("artifacts", []) if isinstance(expected, dict) else []:
        if isinstance(artifact, dict) and isinstance(artifact.get("expected_path"), str):
            paths.append(artifact["expected_path"])
    for path in paths:
        try:
            v2.resolve_artifact_path(Path("/tmp/planning-coordination-v1-1"), path)
        except ValueError as exc:
            blockers.append(str(exc))
    if v2.contains_final_status_value([plan, expected, package.get("planning_preflight_report"), package.get("coordination_report")]):
        blockers.append("selected planning artifacts contain final status enum values")
    return 1.0 if not blockers else 0.0, blockers, warnings, {"checked_paths": paths}


def evaluate_verifier_readiness(package: dict[str, Any]) -> tuple[float, list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    coordination_report = package["coordination_report"]
    completeness = package["planning_completeness_report"]
    preflight = package.get("planning_preflight_report") or {}
    stage3 = package.get("preflight_report") or {}
    stage3_ok, stage3_errors = v2.preflight_is_usable(stage3) if isinstance(stage3, dict) else (False, ["Stage 3 preflight missing"])
    if coordination_report.get("status") != coordination.PASS_STATUS:
        blockers.append("Planning Coordination v1 report is not approved")
    if completeness.get("status") != coordination.COMPLETENESS_APPROVED:
        blockers.append("Planning Coordination v1 completeness report is not approved")
    if not isinstance(preflight, dict) or preflight.get("status") != "PLANNING_EFFICIENCY_V2_PREFLIGHT_PASS":
        blockers.append("selected planning preflight did not pass")
    if not stage3_ok:
        blockers.extend(stage3_errors)
    return 1.0 if not blockers else 0.0, blockers, warnings, {
        "coordination_status": coordination_report.get("status"),
        "completeness_status": completeness.get("status"),
        "selected_preflight_status": preflight.get("status") if isinstance(preflight, dict) else None,
        "stage3_preflight_ok": stage3_ok,
    }


def evaluate_assumption_visibility(package: dict[str, Any]) -> tuple[float, list[str], list[str], dict[str, Any]]:
    matrix = package["planning_assumption_matrix"]
    assumptions = matrix.get("assumptions", [])
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(assumptions, list) or len(assumptions) < 4:
        blockers.append("assumption matrix must record at least four assumptions")
        return 0.0, blockers, warnings, {"assumption_count": len(assumptions) if isinstance(assumptions, list) else 0}
    visible = 0
    unresolved_blocking = 0
    for item in assumptions:
        if not isinstance(item, dict):
            warnings.append("assumption entry is not an object")
            continue
        required = all(isinstance(item.get(key), str) and item.get(key).strip() for key in ["assumption_id", "statement", "source", "evidence"])
        if required:
            visible += 1
        else:
            warnings.append(f"assumption lacks required grounding fields: {item}")
        if item.get("blocks_execution_if_unresolved") is True and item.get("resolved") is not True:
            unresolved_blocking += 1
    if unresolved_blocking:
        blockers.append(f"blocking assumptions unresolved: {unresolved_blocking}")
    score = visible / len(assumptions)
    if score < 1.0:
        blockers.append("all assumptions must include id, statement, source, and evidence")
    return score, blockers, warnings, {"assumption_count": len(assumptions), "visible_count": visible, "unresolved_blocking": unresolved_blocking}


def evaluate_unknown_handling(package: dict[str, Any]) -> tuple[float, list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    matrix = package["planning_assumption_matrix"]
    risks = package["planning_risk_attack_report"].get("risks", [])
    completeness = package["planning_completeness_report"]
    unresolved_assumptions = [
        item.get("assumption_id", "<unknown>")
        for item in matrix.get("assumptions", [])
        if isinstance(item, dict) and item.get("blocks_execution_if_unresolved") is True and item.get("resolved") is not True
    ]
    failed_critical_risks = [
        item.get("risk_id", "<unknown>")
        for item in risks
        if isinstance(item, dict) and item.get("risk_id") in CRITICAL_RISK_IDS and item.get("status") != "PASS"
    ]
    if unresolved_assumptions:
        blockers.append(f"unresolved blocking assumptions: {unresolved_assumptions}")
    if failed_critical_risks:
        blockers.append(f"failed critical risks: {failed_critical_risks}")
    if completeness.get("blocking_failures"):
        blockers.append(f"planning completeness blocking failures: {completeness.get('blocking_failures')}")
    noncritical_failed_risks = [
        item.get("risk_id", "<unknown>")
        for item in risks
        if isinstance(item, dict) and item.get("risk_id") not in CRITICAL_RISK_IDS and item.get("status") != "PASS"
    ]
    if noncritical_failed_risks:
        warnings.append(f"non-selected or noncritical risks recorded: {noncritical_failed_risks}")
    return 1.0 if not blockers else 0.0, blockers, warnings, {
        "unresolved_blocking_assumptions": unresolved_assumptions,
        "failed_critical_risks": failed_critical_risks,
        "noncritical_failed_risks": noncritical_failed_risks,
    }


def evaluate_validation_specificity(package: dict[str, Any]) -> tuple[float, list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    evidence = package["planning_evidence_contract"].get("required_evidence", [])
    validators = [item.get("validator") for item in evidence if isinstance(item, dict)]
    named = [item for item in validators if isinstance(item, str) and ("validate" in item.lower() or "preflight" in item.lower() or "guarded_execution" in item.lower())]
    if len(named) < 3:
        blockers.append("at least three concrete validator/preflight/guarded-execution checks must be named")
    selected_preflight = package.get("planning_preflight_report") or {}
    generated_hashes = selected_preflight.get("generated_hashes", {}) if isinstance(selected_preflight, dict) else {}
    if not isinstance(generated_hashes, dict) or "plan" not in generated_hashes or "expected_artifacts" not in generated_hashes:
        blockers.append("selected planning preflight must include plan and expected_artifacts hashes")
    return 1.0 if not blockers else 0.0, blockers, warnings, {"validator_count": len(validators), "specific_validator_count": len(named), "generated_hash_keys": sorted(generated_hashes) if isinstance(generated_hashes, dict) else []}


def evaluate_rejection_accountability(package: dict[str, Any]) -> tuple[float, list[str], list[str], dict[str, Any]]:
    selection = package["planning_selection_decision"]
    rejected = selection.get("rejected_candidates", [])
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(selection.get("selection_reason"), str) or not selection.get("selection_reason").strip():
        blockers.append("selection decision must include a non-empty selection_reason")
    if not isinstance(rejected, list):
        blockers.append("rejected_candidates must be a list")
        rejected = []
    missing_reason = [item.get("candidate_id", "<unknown>") for item in rejected if isinstance(item, dict) and not item.get("reason")]
    if missing_reason:
        blockers.append(f"rejected candidates missing reasons: {missing_reason}")
    if not rejected:
        warnings.append("only one candidate was available; no rejected candidate accountability was exercised")
    return 1.0 if not blockers else 0.0, blockers, warnings, {"rejected_candidate_count": len(rejected)}


def severity_for_risk(risk: dict[str, Any], selected_candidate_id: str) -> str:
    """Classify a v1 risk as LOW/MEDIUM/HIGH/CRITICAL for skeptic review."""
    risk_id = str(risk.get("risk_id", ""))
    attack_text = str(risk.get("attack", "")).lower()
    if risk_id in CRITICAL_RISK_IDS or "authority" in risk_id.lower() or "certif" in attack_text or "final run status" in attack_text:
        return "CRITICAL"
    if risk_id == f"R.CANDIDATE_{selected_candidate_id}":
        return "HIGH"
    if risk_id.startswith("R.CANDIDATE_"):
        return "MEDIUM"
    return "LOW"


def risk_blocks_skeptic_review(risk: dict[str, Any], selected_candidate_id: str) -> bool:
    if risk.get("status") == "PASS":
        return False
    severity = severity_for_risk(risk, selected_candidate_id)
    return severity in {"HIGH", "CRITICAL"}


def runtime_nonexecution_contract() -> dict[str, Any]:
    return {
        "goal_execution_attempted": False,
        "plan_execution_attempted": False,
        "guarded_execution_invoked": False,
        "status_authority": "certifier_only",
        "requires_policy_certifier_for_status": True,
        "can_certify_done": False,
    }


def build_skeptic_review_reports(package: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    coordination_report = package["coordination_report"]
    risk_report = package["planning_risk_attack_report"]
    selected_candidate_id = str(coordination_report.get("selected_candidate_id") or risk_report.get("selected_candidate_id") or "")
    risks = risk_report.get("risks", []) if isinstance(risk_report, dict) else []
    reviewed_risks: list[dict[str, Any]] = []
    unresolved_high_or_authority: list[dict[str, Any]] = []
    unresolved_nonblocking: list[dict[str, Any]] = []
    resolved_attacks: list[dict[str, Any]] = []

    for risk in risks if isinstance(risks, list) else []:
        if not isinstance(risk, dict):
            continue
        risk_id = str(risk.get("risk_id", "<unknown>"))
        severity = severity_for_risk(risk, selected_candidate_id)
        applies_to_selected = risk_id in CRITICAL_RISK_IDS or risk_id == f"R.CANDIDATE_{selected_candidate_id}"
        finding = {
            "risk_id": risk_id,
            "attack": risk.get("attack", ""),
            "mitigation": risk.get("mitigation", ""),
            "status": risk.get("status", "UNKNOWN"),
            "severity": severity,
            "applies_to_selected_candidate": applies_to_selected,
            "authority_boundary_risk": severity == "CRITICAL",
            "blocking": risk_blocks_skeptic_review(risk, selected_candidate_id),
            "resolution": "resolved" if risk.get("status") == "PASS" else "unresolved",
        }
        reviewed_risks.append(finding)
        if finding["blocking"]:
            unresolved_high_or_authority.append(finding)
        elif finding["resolution"] == "unresolved":
            unresolved_nonblocking.append(finding)
        else:
            resolved_attacks.append({
                "risk_id": risk_id,
                "severity": severity,
                "mitigation": risk.get("mitigation", ""),
            })

    selected_risk_reviewed = any(item.get("risk_id") == f"R.CANDIDATE_{selected_candidate_id}" for item in reviewed_risks)
    authority_risk_reviewed = any(item.get("severity") == "CRITICAL" for item in reviewed_risks)
    blocking_failures: list[str] = []
    if not selected_candidate_id:
        blocking_failures.append("selected candidate id is missing from skeptic review input")
    if not reviewed_risks:
        blocking_failures.append("skeptic review has no attack cases")
    if not selected_risk_reviewed:
        blocking_failures.append("skeptic review must include the selected candidate risk")
    if not authority_risk_reviewed:
        blocking_failures.append("skeptic review must include authority-boundary attack coverage")
    if unresolved_high_or_authority:
        blocking_failures.append("unresolved high-severity or authority risks remain")

    approved = not blocking_failures
    review = {
        "schema_version": "planning_coordination_v1_1_skeptic_review_report_v1",
        "status": SKEPTIC_REVIEW_APPROVED if approved else SKEPTIC_REVIEW_BLOCKED,
        "authority": v2.REQUIRED_AUTHORITY,
        "review_mode": "planning_only",
        "reviewer_role": "deterministic_skeptic_gate",
        "selected_candidate_id": selected_candidate_id,
        "selected_generator": coordination_report.get("selected_generator", ""),
        "source_risk_attack_report": rel_path(package["planning_risk_attack_report_path"]),
        "review_scope": [
            "selected candidate attack surface",
            "authority-boundary risks",
            "guarded-execution handoff risks",
            "non-selected candidate rejection accountability",
        ],
        "attack_cases": reviewed_risks,
        "risk_findings": reviewed_risks,
        "unresolved_high_or_authority_risks": unresolved_high_or_authority,
        "unresolved_nonblocking_risks": unresolved_nonblocking,
        "blocking_failures": blocking_failures,
        "runtime_execution": runtime_nonexecution_contract(),
        "claim_boundary": "Skeptic review is a deterministic planning-only attack review. It does not execute plans, decide policy, certify, or prove exhaustive risk coverage.",
    }
    resolution = {
        "schema_version": "planning_coordination_v1_1_attack_resolution_report_v1",
        "status": ATTACK_RESOLUTION_APPROVED if approved else ATTACK_RESOLUTION_BLOCKED,
        "authority": v2.REQUIRED_AUTHORITY,
        "selected_candidate_id": selected_candidate_id,
        "source_skeptic_review_status": review["status"],
        "resolved_attacks": resolved_attacks,
        "unresolved_high_or_authority_risks": unresolved_high_or_authority,
        "unresolved_nonblocking_risks": unresolved_nonblocking,
        "resolution_policy": "unresolved HIGH or CRITICAL/authority risks block guarded execution handoff; non-selected candidate failures remain visible as warnings",
        "execution_gate": {
            "skeptic_review_approved": approved,
            "may_pass_plan_to_guarded_execution": approved,
            "blocked_before_execution": not approved,
        },
        "runtime_execution": runtime_nonexecution_contract(),
        "claim_boundary": "Attack resolution is a bounded pre-execution planning gate. It cannot certify DONE or replace verifier/policy/certifier authority.",
    }
    return review, resolution


def validate_skeptic_review_reports(review: dict[str, Any], resolution: dict[str, Any], selected_candidate_id: str) -> list[str]:
    errors: list[str] = []
    if review.get("schema_version") != "planning_coordination_v1_1_skeptic_review_report_v1":
        errors.append("skeptic review schema_version mismatch")
    if resolution.get("schema_version") != "planning_coordination_v1_1_attack_resolution_report_v1":
        errors.append("attack resolution schema_version mismatch")
    if review.get("authority") != v2.REQUIRED_AUTHORITY or resolution.get("authority") != v2.REQUIRED_AUTHORITY:
        errors.append("skeptic artifacts must preserve evaluation_only/certifier_only authority")
    if review.get("review_mode") != "planning_only":
        errors.append("skeptic review must be planning_only")
    if review.get("selected_candidate_id") != selected_candidate_id or resolution.get("selected_candidate_id") != selected_candidate_id:
        errors.append("skeptic artifacts must match selected candidate id")
    if not isinstance(review.get("attack_cases"), list) or not review.get("attack_cases"):
        errors.append("skeptic review must contain attack cases")
    if not any(isinstance(item, dict) and item.get("risk_id") == f"R.CANDIDATE_{selected_candidate_id}" for item in review.get("attack_cases", [])):
        errors.append("skeptic review must include selected candidate attack case")
    if not any(isinstance(item, dict) and item.get("authority_boundary_risk") is True for item in review.get("risk_findings", [])):
        errors.append("skeptic review must include authority-boundary risk coverage")
    if review.get("unresolved_high_or_authority_risks") or resolution.get("unresolved_high_or_authority_risks"):
        errors.append("unresolved high-severity or authority risks must block")
    if review.get("status") != SKEPTIC_REVIEW_APPROVED:
        errors.append("skeptic review is not approved")
    if resolution.get("status") != ATTACK_RESOLUTION_APPROVED:
        errors.append("attack resolution is not approved")
    for label, artifact in {"skeptic review": review, "attack resolution": resolution}.items():
        errors.extend(report_runtime_is_nonexecuting(artifact, label))
        if v2.contains_final_status_value(artifact):
            errors.append(f"{label} must not contain final status enum values")
    return errors


def evaluate_skeptic_attack_review(package: dict[str, Any]) -> tuple[float, list[str], list[str], dict[str, Any]]:
    review = package.get("planning_skeptic_review_report")
    resolution = package.get("planning_attack_resolution_report")
    selected_candidate_id = str(package["coordination_report"].get("selected_candidate_id", ""))
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(review, dict) or not isinstance(resolution, dict):
        return 0.0, ["skeptic review artifacts are missing"], warnings, {}
    blockers.extend(validate_skeptic_review_reports(review, resolution, selected_candidate_id))
    if resolution.get("unresolved_nonblocking_risks"):
        warnings.append(f"nonblocking unresolved risks remain visible: {[item.get('risk_id') for item in resolution.get('unresolved_nonblocking_risks', []) if isinstance(item, dict)]}")
    return 1.0 if not blockers else 0.0, blockers, warnings, {
        "selected_candidate_id": selected_candidate_id,
        "attack_case_count": len(review.get("attack_cases", [])) if isinstance(review.get("attack_cases"), list) else 0,
        "resolved_attack_count": len(resolution.get("resolved_attacks", [])) if isinstance(resolution.get("resolved_attacks"), list) else 0,
        "unresolved_high_or_authority_count": len(resolution.get("unresolved_high_or_authority_risks", [])) if isinstance(resolution.get("unresolved_high_or_authority_risks"), list) else 0,
    }


def evaluate_authority_safety(package: dict[str, Any]) -> tuple[float, list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    named_reports = {
        "coordination_report": package["coordination_report"],
        "candidate_plans": package["candidate_plans"],
        "planning_assumption_matrix": package["planning_assumption_matrix"],
        "planning_risk_attack_report": package["planning_risk_attack_report"],
        "planning_evidence_contract": package["planning_evidence_contract"],
        "planning_completeness_report": package["planning_completeness_report"],
        "coordinator_selection_ledger": package["coordinator_selection_ledger"],
        "planning_preflight_report": package.get("planning_preflight_report") or {},
        "planning_skeptic_review_report": package.get("planning_skeptic_review_report") or {},
        "planning_attack_resolution_report": package.get("planning_attack_resolution_report") or {},
    }
    for name, report in named_reports.items():
        if isinstance(report, dict) and "authority" in report and not source_authority_ok(report):
            blockers.append(f"{name} authority boundary mismatch")
        blockers.extend(report_runtime_is_nonexecuting(report, name))
    if v2.contains_final_status_value(list(named_reports.values())):
        blockers.append("planning quality source reports contain final status enum values")
    return 1.0 if not blockers else 0.0, blockers, warnings, {"checked_reports": sorted(named_reports)}


def compute_plan_quality_report(
    coordination_report_path: Path,
    plan_quality_path: Path,
    min_quality_score: float,
    max_blocking_unknowns: int,
    max_nonblocking_unknowns: int,
    package: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    package = package if package is not None else load_package(coordination_report_path)
    dimensions: list[dict[str, Any]] = []
    for name, evaluator, critical in [
        ("evidence_requirement_coverage", evaluate_evidence_requirement_coverage, True),
        ("dependency_coverage", evaluate_dependency_coverage, True),
        ("forbidden_path_safety", evaluate_forbidden_path_safety, True),
        ("verifier_readiness", evaluate_verifier_readiness, True),
        ("assumption_visibility", evaluate_assumption_visibility, True),
        ("unknown_handling", evaluate_unknown_handling, True),
        ("validation_specificity", evaluate_validation_specificity, True),
        ("rejection_accountability", evaluate_rejection_accountability, False),
        ("skeptic_attack_review", evaluate_skeptic_attack_review, True),
        ("authority_safety", evaluate_authority_safety, True),
    ]:
        score, blockers, warnings, evidence = evaluator(package)
        add_dimension(dimensions, name, score, blockers, warnings, evidence, critical)

    quality_score = round(sum(item["weighted_score"] for item in dimensions), 4)
    blocking_failures = [
        {"dimension": item["dimension"], "failures": item["blocking_failures"]}
        for item in dimensions
        if item.get("critical") and item.get("blocking_failures")
    ]
    nonblocking_warnings = [
        {"dimension": item["dimension"], "warnings": item["nonblocking_warnings"]}
        for item in dimensions
        if item.get("nonblocking_warnings")
    ]
    if quality_score < min_quality_score:
        blocking_failures.append({"dimension": "quality_score", "failures": [f"quality score {quality_score} is below threshold {min_quality_score}"]})

    blocker_budget = {
        "schema_version": "planning_coordination_v1_1_blocker_budget_v1",
        "authority": v2.REQUIRED_AUTHORITY,
        "max_blocking_unknowns": max_blocking_unknowns,
        "max_nonblocking_unknowns": max_nonblocking_unknowns,
        "current_blocking_unknowns": len(blocking_failures),
        "current_nonblocking_unknowns": len(nonblocking_warnings),
        "blocking_failures": blocking_failures,
        "nonblocking_warnings": nonblocking_warnings,
        "status": BLOCKER_BUDGET_WITHIN if len(blocking_failures) <= max_blocking_unknowns and len(nonblocking_warnings) <= max_nonblocking_unknowns else BLOCKER_BUDGET_EXCEEDED,
        "runtime_execution": {
            "goal_execution_attempted": False,
            "plan_execution_attempted": False,
            "guarded_execution_invoked": False,
            "status_authority": "certifier_only",
            "requires_policy_certifier_for_status": True,
            "can_certify_done": False,
        },
    }
    approved = blocker_budget["status"] == BLOCKER_BUDGET_WITHIN
    coordination_report = package["coordination_report"]
    quality_report = {
        "schema_version": "planning_coordination_v1_1_plan_quality_report_v1",
        "status": PLAN_QUALITY_APPROVED if approved else PLAN_QUALITY_BLOCKED,
        "authority": v2.REQUIRED_AUTHORITY,
        "source_coordination_report": rel_path(coordination_report_path),
        "selected_candidate_id": coordination_report.get("selected_candidate_id", ""),
        "selected_generator": coordination_report.get("selected_generator", ""),
        "quality_score": quality_score,
        "minimum_quality_score": min_quality_score,
        "quality_dimensions": dimensions,
        "unknown_budget": blocker_budget,
        "quality_scores": {item["dimension"]: item["score"] for item in dimensions},
        "skeptic_review_status": package.get("planning_skeptic_review_report", {}).get("status") if isinstance(package.get("planning_skeptic_review_report"), dict) else None,
        "attack_resolution_status": package.get("planning_attack_resolution_report", {}).get("status") if isinstance(package.get("planning_attack_resolution_report"), dict) else None,
        "blocking_failures": blocking_failures,
        "nonblocking_warnings": nonblocking_warnings,
        "execution_gate": {
            "planning_quality_approved": approved,
            "may_pass_plan_to_guarded_execution": approved,
            "required_next_runtime": "guarded_execution_v2" if approved else "none_until_plan_quality_approved",
            "runtime_module": ".agentic-pi/runtime/guarded_execution_v2.py" if approved else "",
            "guarded_execution_inputs": selected_inputs(coordination_report) if approved else {},
            "blocked_before_execution": not approved,
        },
        "runtime_execution": {
            "goal_execution_attempted": False,
            "plan_execution_attempted": False,
            "guarded_execution_invoked": False,
            "status_authority": "certifier_only",
            "requires_policy_certifier_for_status": True,
            "can_certify_done": False,
        },
        "claim_boundary": "Plan quality scoring is a bounded pre-execution quality gate. It does not execute plans, decide policy, certify, or prove arbitrary planning correctness.",
    }
    return quality_report, blocker_budget


def build_quality_gate_report(
    goal_path: Path,
    stage3_preflight_path: Path,
    work_dir: Path,
    output_path: Path,
    route: str = "auto",
    max_repair_attempts: int = repair_loop.DEFAULT_MAX_REPAIR_ATTEMPTS,
    min_quality_score: float = DEFAULT_MIN_QUALITY_SCORE,
    max_blocking_unknowns: int = DEFAULT_MAX_BLOCKING_UNKNOWNS,
    max_nonblocking_unknowns: int = DEFAULT_MAX_NONBLOCKING_UNKNOWNS,
    reuse_coordination_report: Path | None = None,
) -> dict[str, Any]:
    coordination.ensure_output_paths_allowed(work_dir, output_path)
    paths = quality_artifact_paths(work_dir)
    if reuse_coordination_report is None:
        coordination_report = coordination.build_coordination_report(
            goal_path,
            stage3_preflight_path,
            paths["coordination_work_dir"],
            paths["coordination_report"],
            route,
            max_repair_attempts,
        )
        coordination_errors = coordination.validate_coordination_report(coordination_report)
        write_json(paths["coordination_report"], coordination_report)
    else:
        paths["coordination_report"] = reuse_coordination_report
        coordination_report = load_required_json(reuse_coordination_report, "Planning Coordination v1 report")
        coordination_errors = coordination.validate_coordination_report(coordination_report)

    package = load_package(paths["coordination_report"])
    skeptic_review_report, attack_resolution_report = build_skeptic_review_reports(package)
    skeptic_metadata = write_json(paths["planning_skeptic_review_report"], skeptic_review_report)
    attack_metadata = write_json(paths["planning_attack_resolution_report"], attack_resolution_report)
    package["planning_skeptic_review_report"] = skeptic_review_report
    package["planning_attack_resolution_report"] = attack_resolution_report
    package["planning_skeptic_review_report_path"] = paths["planning_skeptic_review_report"]
    package["planning_attack_resolution_report_path"] = paths["planning_attack_resolution_report"]

    plan_quality_report, blocker_budget = compute_plan_quality_report(
        paths["coordination_report"],
        paths["plan_quality_report"],
        min_quality_score,
        max_blocking_unknowns,
        max_nonblocking_unknowns,
        package,
    )
    write_metadata = {
        "planning_skeptic_review_report": skeptic_metadata,
        "planning_attack_resolution_report": attack_metadata,
        "plan_quality_report": write_json(paths["plan_quality_report"], plan_quality_report),
        "blocker_budget_report": write_json(paths["blocker_budget_report"], blocker_budget),
    }

    criteria: list[dict[str, Any]] = []
    add_check(criteria, "coordination_v1_report_valid", not coordination_errors and coordination_report.get("status") == coordination.PASS_STATUS, "Planning Coordination v1 report validates and is approved", coordination_errors or coordination_report.get("status"))
    add_check(criteria, "evidence_weighted_quality_score_met", plan_quality_report.get("quality_score", 0) >= min_quality_score, f"quality_score >= {min_quality_score}", plan_quality_report.get("quality_score"))
    add_check(criteria, "blocker_budget_within_limits", blocker_budget.get("status") == BLOCKER_BUDGET_WITHIN, "blocking/nonblocking unknowns remain within budget", blocker_budget)
    add_check(criteria, "planning_only_skeptic_review_passed", skeptic_review_report.get("status") == SKEPTIC_REVIEW_APPROVED and attack_resolution_report.get("status") == ATTACK_RESOLUTION_APPROVED, "selected candidate has explicit skeptic review and no unresolved high/authority risks", {"skeptic_review_status": skeptic_review_report.get("status"), "attack_resolution_status": attack_resolution_report.get("status")})
    add_check(criteria, "plan_quality_approved", plan_quality_report.get("status") == PLAN_QUALITY_APPROVED, PLAN_QUALITY_APPROVED, plan_quality_report.get("status"))
    add_check(criteria, "guarded_execution_not_invoked", True, "v1.1 quality gate does not invoke guarded execution", False)
    add_check(criteria, "certifier_only_authority_preserved", True, "v1.1 quality gate is evaluation-only and cannot certify", v2.REQUIRED_AUTHORITY)

    approved = all(check["status"] == "PASS" for check in criteria)
    execution_gate = {
        "planning_quality_status": plan_quality_report.get("status"),
        "blocker_budget_status": blocker_budget.get("status"),
        "skeptic_review_status": skeptic_review_report.get("status"),
        "attack_resolution_status": attack_resolution_report.get("status"),
        "may_pass_plan_to_guarded_execution": approved,
        "required_next_runtime": "guarded_execution_v2" if approved else "none_until_plan_quality_approved",
        "runtime_module": ".agentic-pi/runtime/guarded_execution_v2.py" if approved else "",
        "guarded_execution_inputs": plan_quality_report.get("execution_gate", {}).get("guarded_execution_inputs", {}) if approved else {},
        "blocked_before_execution": not approved,
    }

    return {
        "schema_version": "planning_coordination_v1_1_quality_gate_report_v1",
        "status": PASS_STATUS if approved else NOT_READY_STATUS,
        "authority": v2.REQUIRED_AUTHORITY,
        "source_goal": rel_path(goal_path),
        "stage3_runtime_preflight_report": rel_path(stage3_preflight_path),
        "work_dir": rel_path(work_dir),
        "output": rel_path(output_path),
        "route": route,
        "selected_candidate_id": coordination_report.get("selected_candidate_id", "") if approved else "",
        "selected_generator": coordination_report.get("selected_generator", "") if approved else "",
        "quality_score": plan_quality_report.get("quality_score"),
        "minimum_quality_score": min_quality_score,
        "skeptic_review_status": skeptic_review_report.get("status"),
        "attack_resolution_status": attack_resolution_report.get("status"),
        "unknown_budget": blocker_budget,
        "criteria": criteria,
        "quality_artifacts": {
            "coordination_report": rel_path(paths["coordination_report"]),
            "planning_skeptic_review_report": rel_path(paths["planning_skeptic_review_report"]),
            "planning_attack_resolution_report": rel_path(paths["planning_attack_resolution_report"]),
            "plan_quality_report": rel_path(paths["plan_quality_report"]),
            "blocker_budget_report": rel_path(paths["blocker_budget_report"]),
        },
        "quality_artifact_hashes": {key: meta["sha256"] for key, meta in write_metadata.items()},
        "source_reports": {
            "coordination_v1_report": rel_path(paths["coordination_report"]),
            "planning_skeptic_review_report": rel_path(paths["planning_skeptic_review_report"]),
            "planning_attack_resolution_report": rel_path(paths["planning_attack_resolution_report"]),
            "plan_quality_report": rel_path(paths["plan_quality_report"]),
            "blocker_budget_report": rel_path(paths["blocker_budget_report"]),
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
        "claim_boundary": "Planning Coordination v1.1 adds evidence-weighted plan quality scoring and blocker-budget gating before guarded execution. It does not execute guarded plans, decide policy, certify, or prove arbitrary planning safety.",
    }


def validate_quality_gate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != "planning_coordination_v1_1_quality_gate_report_v1":
        errors.append("schema_version must be planning_coordination_v1_1_quality_gate_report_v1")
    if report.get("status") not in {PASS_STATUS, NOT_READY_STATUS}:
        errors.append("status must be a Planning Coordination v1.1 approved or NOT_READY status")
    if report.get("authority") != v2.REQUIRED_AUTHORITY:
        errors.append("authority must be evaluation_only/certifier_only/can_certify_done false")
    if v2.contains_final_status_value(report):
        errors.append("planning coordination v1.1 report must not contain final status enum values")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
    elif report.get("status") == PASS_STATUS and any(check.get("status") != "PASS" for check in criteria):
        errors.append("approved v1.1 reports must have all criteria PASS")
    artifacts = report.get("quality_artifacts", {})
    artifact_hashes = report.get("quality_artifact_hashes", {})
    source_reports = report.get("source_reports", {})
    for key in ["coordination_report", "planning_skeptic_review_report", "planning_attack_resolution_report", "plan_quality_report", "blocker_budget_report"]:
        raw_path = artifacts.get(key) if isinstance(artifacts, dict) else None
        if not isinstance(raw_path, str) or not raw_path.strip():
            errors.append(f"quality_artifacts.{key} is required")
        elif not resolve_reported_path(raw_path).is_file():
            errors.append(f"quality artifact does not exist: {raw_path}")
    for key in ["planning_skeptic_review_report", "planning_attack_resolution_report", "plan_quality_report", "blocker_budget_report"]:
        if not isinstance(artifact_hashes, dict) or not isinstance(artifact_hashes.get(key), str) or not artifact_hashes.get(key):
            errors.append(f"quality_artifact_hashes.{key} is required")
        if not isinstance(source_reports, dict) or not isinstance(source_reports.get(key), str) or not source_reports.get(key):
            errors.append(f"source_reports.{key} is required")
    if report.get("status") == PASS_STATUS:
        check_ids = {check.get("check_id") for check in criteria} if isinstance(criteria, list) else set()
        if "planning_only_skeptic_review_passed" not in check_ids:
            errors.append("approved v1.1 reports must include planning_only_skeptic_review_passed criterion")
        if report.get("skeptic_review_status") != SKEPTIC_REVIEW_APPROVED:
            errors.append("approved v1.1 report must have approved skeptic review")
        if report.get("attack_resolution_status") != ATTACK_RESOLUTION_APPROVED:
            errors.append("approved v1.1 report must have approved attack resolution")
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
            errors.append("approved v1.1 report must allow guarded execution handoff")
        if report.get("unknown_budget", {}).get("status") != BLOCKER_BUDGET_WITHIN:
            errors.append("approved v1.1 report must have blocker budget within limits")
        inputs = gate.get("guarded_execution_inputs", {})
        for key in ["preflight_report", "plan", "expected_artifacts", "planning_preflight_report"]:
            if not isinstance(inputs.get(key), str) or not inputs.get(key).strip():
                errors.append(f"approved v1.1 report missing guarded_execution_inputs.{key}")
            else:
                if not resolve_reported_path(inputs[key]).is_file():
                    errors.append(f"approved v1.1 report input does not exist: {inputs[key]}")
    else:
        if gate.get("may_pass_plan_to_guarded_execution") is not False:
            errors.append("NOT_READY v1.1 report must not allow guarded execution handoff")
        if gate.get("guarded_execution_inputs"):
            errors.append("NOT_READY v1.1 report must not expose guarded execution inputs")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Planning Coordination v1.1 quality gate without executing guarded plans.")
    parser.add_argument("--goal", default=str(DEFAULT_GOAL))
    parser.add_argument("--stage3-preflight-report", default=str(DEFAULT_STAGE3_PREFLIGHT_REPORT))
    parser.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--route", choices=sorted(coordination.SUPPORTED_ROUTES), default="auto")
    parser.add_argument("--max-repair-attempts", type=int, default=repair_loop.DEFAULT_MAX_REPAIR_ATTEMPTS)
    parser.add_argument("--min-quality-score", type=float, default=DEFAULT_MIN_QUALITY_SCORE)
    parser.add_argument("--max-blocking-unknowns", type=int, default=DEFAULT_MAX_BLOCKING_UNKNOWNS)
    parser.add_argument("--max-nonblocking-unknowns", type=int, default=DEFAULT_MAX_NONBLOCKING_UNKNOWNS)
    parser.add_argument("--reuse-coordination-report")
    args = parser.parse_args(argv)

    try:
        report = build_quality_gate_report(
            Path(args.goal),
            Path(args.stage3_preflight_report),
            Path(args.work_dir),
            Path(args.output),
            args.route,
            args.max_repair_attempts,
            args.min_quality_score,
            args.max_blocking_unknowns,
            args.max_nonblocking_unknowns,
            Path(args.reuse_coordination_report) if args.reuse_coordination_report else None,
        )
        errors = validate_quality_gate_report(report)
        write_json(Path(args.output), report)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if report["status"] != PASS_STATUS:
        print("NOT_READY: plan quality gate did not approve guarded execution handoff", file=sys.stderr)
        return 1
    print(f"OK: {report['status']} (quality_score={report['quality_score']}) -> {args.output}")
    print("evidence-weighted plan quality approved")
    print("blocker budget within limits")
    print(f"selected candidate {report['selected_candidate_id']}")
    print("plan_quality_report written")
    print("planning skeptic review approved")
    print("attack resolution report approved")
    print("guarded execution not invoked by v1.1")
    print("handoff bound to guarded_execution_v2")
    print("certifier-only authority preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
