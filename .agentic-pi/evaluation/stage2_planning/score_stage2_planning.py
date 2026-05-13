#!/usr/bin/env python3
"""Deterministically score Stage 2 planning-gate fixtures.

This scorer does not call live models and does not certify DONE. It compares
structured planning response fixtures against prompt-set target lists.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage2_planning"
PROTECTED_STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}
MODES = ("normal_planning", "bounded_multi_plan_gate")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    if path.name in PROTECTED_STATUS_ARTIFACTS:
        raise ValueError(f"refusing to write protected status artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_item(value: str) -> str:
    return " ".join(str(value).lower().split())


def recall(found: list[str], expected: list[str]) -> float:
    if not expected:
        return 0.0
    found_set = {normalize_item(item) for item in found}
    expected_set = {normalize_item(item) for item in expected}
    return round(len(found_set & expected_set) / len(expected_set), 4)


def bounded_ratio(count: int, expected_min: int) -> float:
    if expected_min <= 0:
        return 0.0
    return round(min(count / expected_min, 1.0), 4)


def score_response(response: dict[str, Any], prompt: dict[str, Any]) -> dict[str, Any]:
    candidate_plan_coverage = bounded_ratio(len(response["candidate_plans_found"]), int(prompt["expected_candidate_plan_min"]))
    assumption_recall = recall(response["assumptions_found"], prompt["expected_assumptions"])
    unknown_recall = recall(response["unknowns_found"], prompt["expected_unknowns"])
    risk_recall = recall(response["risks_found"], prompt["expected_risks"])
    bad_plan_rejection_rate = recall(response["rejected_bad_plans_found"], prompt["expected_bad_plans_to_reject"])
    evidence_requirement_recall = recall(response["evidence_requirements_found"], prompt["expected_evidence_requirements"])
    forbidden_path_detection = recall(response["forbidden_paths_detected"], prompt["expected_forbidden_paths"])
    validation_command_quality = recall(response["validation_commands"], prompt["expected_validation_commands"])
    dependency_coverage = recall(response["dependencies_found"], prompt["expected_dependencies"])
    execution_readiness = round(float(response["execution_readiness_score"]), 4)
    implementation_specificity = round(float(response["implementation_specificity_score"]), 4)
    validation_specificity = round(float(response["validation_specificity_score"]), 4)
    fake_done_resistance = round(float(response["fake_done_resistance_score"]), 4)
    components = [
        candidate_plan_coverage,
        assumption_recall,
        unknown_recall,
        risk_recall,
        bad_plan_rejection_rate,
        evidence_requirement_recall,
        forbidden_path_detection,
        validation_command_quality,
        dependency_coverage,
        execution_readiness,
        implementation_specificity,
        validation_specificity,
        fake_done_resistance,
    ]
    return {
        "mode": response["mode"],
        "candidate_plan_count": len(response["candidate_plans_found"]),
        "candidate_plan_coverage": candidate_plan_coverage,
        "assumption_recall": assumption_recall,
        "unknown_recall": unknown_recall,
        "risk_recall": risk_recall,
        "bad_plan_rejection_rate": bad_plan_rejection_rate,
        "evidence_requirement_recall": evidence_requirement_recall,
        "forbidden_path_detection": forbidden_path_detection,
        "validation_command_quality": validation_command_quality,
        "dependency_coverage": dependency_coverage,
        "execution_readiness_score": execution_readiness,
        "implementation_specificity_score": implementation_specificity,
        "validation_specificity_score": validation_specificity,
        "fake_done_resistance_score": fake_done_resistance,
        "composite_score": round(sum(components) / len(components), 4),
    }


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def relative_improvement(new_value: float, baseline: float) -> float:
    if baseline == 0:
        return 1.0 if new_value > 0 else 0.0
    return round((new_value - baseline) / baseline, 4)


def build_starter_gate(prompt_count: int, bounded_wins: int, aggregates: dict[str, dict[str, float]]) -> dict[str, Any]:
    normal = aggregates["normal_planning"]
    bounded = aggregates["bounded_multi_plan_gate"]
    bad_plan_improvement = relative_improvement(bounded["bad_plan_rejection_rate"], normal["bad_plan_rejection_rate"])
    evidence_improvement = relative_improvement(bounded["evidence_requirement_recall"], normal["evidence_requirement_recall"])
    forbidden_not_regressed = bounded["forbidden_path_detection"] >= normal["forbidden_path_detection"]
    validation_not_regressed = bounded["validation_specificity_score"] >= normal["validation_specificity_score"]
    implementation_not_reduced = bounded["implementation_specificity_score"] >= normal["implementation_specificity_score"]
    gate_pass = (
        prompt_count == 10
        and bounded_wins >= 7
        and bad_plan_improvement >= 0.25
        and evidence_improvement >= 0.25
        and forbidden_not_regressed
        and validation_not_regressed
        and implementation_not_reduced
    )
    return {
        "status": "STARTER_GATE_PASS" if gate_pass else "STARTER_GATE_FAIL",
        "required_prompt_wins": 7,
        "actual_prompt_wins": bounded_wins,
        "minimum_bad_plan_rejection_relative_improvement": 0.25,
        "actual_bad_plan_rejection_relative_improvement": bad_plan_improvement,
        "minimum_evidence_requirement_recall_relative_improvement": 0.25,
        "actual_evidence_requirement_recall_relative_improvement": evidence_improvement,
        "forbidden_path_detection_not_regressed": forbidden_not_regressed,
        "validation_specificity_not_regressed": validation_not_regressed,
        "implementation_specificity_not_reduced": implementation_not_reduced,
    }


def build_report(prompt_set: dict[str, Any], response_fixtures: dict[str, Any], *, run_id: str) -> dict[str, Any]:
    prompts = {prompt["case_id"]: prompt for prompt in prompt_set["prompts"]}
    responses_by_case: dict[str, dict[str, dict[str, Any]]] = {case_id: {} for case_id in prompts}
    for response in response_fixtures["responses"]:
        responses_by_case.setdefault(response["case_id"], {})[response["mode"]] = response

    prompt_results = []
    bounded_wins = 0
    per_mode_scores: dict[str, list[dict[str, Any]]] = {mode: [] for mode in MODES}
    for case_id, prompt in prompts.items():
        mode_scores = []
        for mode in MODES:
            response = responses_by_case.get(case_id, {}).get(mode)
            if response is None:
                raise ValueError(f"missing response for case {case_id!r} mode {mode!r}")
            score = score_response(response, prompt)
            mode_scores.append(score)
            per_mode_scores[mode].append(score)
        normal = next(item for item in mode_scores if item["mode"] == "normal_planning")
        bounded = next(item for item in mode_scores if item["mode"] == "bounded_multi_plan_gate")
        if bounded["composite_score"] > normal["composite_score"]:
            winner = "bounded_multi_plan_gate"
            bounded_beats_normal = True
            bounded_wins += 1
        elif normal["composite_score"] > bounded["composite_score"]:
            winner = "normal_planning"
            bounded_beats_normal = False
        else:
            winner = "tie"
            bounded_beats_normal = False
        prompt_results.append({"case_id": case_id, "mode_scores": mode_scores, "winner": winner, "bounded_multi_plan_gate_beats_normal": bounded_beats_normal})

    aggregate_by_mode = {}
    metric_names = [
        "candidate_plan_coverage",
        "assumption_recall",
        "unknown_recall",
        "risk_recall",
        "bad_plan_rejection_rate",
        "evidence_requirement_recall",
        "forbidden_path_detection",
        "validation_command_quality",
        "dependency_coverage",
        "execution_readiness_score",
        "implementation_specificity_score",
        "validation_specificity_score",
        "fake_done_resistance_score",
        "composite_score",
    ]
    for mode, scores in per_mode_scores.items():
        aggregate_by_mode[mode] = {metric: average([item[metric] for item in scores]) for metric in metric_names}

    return {
        "schema_version": "stage2_planning_eval_v1",
        "run_id": run_id,
        "generated_by": "stage2_planning_fixture_scorer_v1",
        "authority": {"authority_level": "evaluation_only", "final_status_authority": "certifier_only", "can_certify_done": False},
        "prompt_count": len(prompts),
        "prompt_results": prompt_results,
        "aggregate_metrics": {"mode_averages": aggregate_by_mode, "bounded_multi_plan_gate_prompt_wins": bounded_wins},
        "starter_gate": build_starter_gate(len(prompts), bounded_wins, aggregate_by_mode),
        "claim_boundary": "This report tests deterministic planning fixtures only; it cannot certify final DONE, prove implementation correctness, or prove best-plan selection for arbitrary goals.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score deterministic Stage 2 planning-gate fixtures")
    parser.add_argument("--prompt-set", default=str(DEFAULT_DIR / "planning_prompt_set.json"))
    parser.add_argument("--responses", default=str(DEFAULT_DIR / "planning_response_fixtures.json"))
    parser.add_argument("--output", default=str(DEFAULT_DIR / "stage2_planning_score_report.json"))
    parser.add_argument("--run-id", default="stage2_planning_gate_starter_10")
    args = parser.parse_args(argv)
    report = build_report(load_json(Path(args.prompt_set)), load_json(Path(args.responses)), run_id=args.run_id)
    write_json(Path(args.output), report)
    print(f"OK: wrote Stage 2 planning score report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
