#!/usr/bin/env python3
"""Deterministically score Stage 1 normal-vs-multiframe fixtures.

This scorer does not call live models and does not certify DONE. It compares
structured response fixtures against prompt-set target lists.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage1_multiframe"
PROTECTED_STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}
MODES = ("normal_prompt", "multiframe_harness")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    if path.name in PROTECTED_STATUS_ARTIFACTS:
        raise ValueError(f"refusing to write protected status artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def recall(found: list[str], expected: list[str]) -> float:
    if not expected:
        return 0.0
    return round(len(set(found) & set(expected)) / len(set(expected)), 4)


def score_response(response: dict[str, Any], prompt: dict[str, Any]) -> dict[str, Any]:
    alternative_recall = recall(response["frames_found"], prompt["expected_frames"])
    assumption_recall = recall(response["assumptions_found"], prompt["expected_assumptions"])
    failure_mode_recall = recall(response["failure_modes_found"], prompt["expected_failure_modes"])
    bad_frame_rejection_rate = recall(response["bad_frames_rejected"], prompt["bad_frames_to_reject"])
    quality = round(float(response["final_answer_quality"]), 4)
    composite = round(
        (alternative_recall + assumption_recall + failure_mode_recall + bad_frame_rejection_rate + quality) / 5,
        4,
    )
    return {
        "mode": response["mode"],
        "frame_count": len(response["frames_found"]),
        "assumption_count": len(response["assumptions_found"]),
        "failure_modes_found_count": len(response["failure_modes_found"]),
        "rejected_bad_frames_count": len(response["bad_frames_rejected"]),
        "alternative_recall": alternative_recall,
        "assumption_recall": assumption_recall,
        "failure_mode_recall": failure_mode_recall,
        "bad_frame_rejection_rate": bad_frame_rejection_rate,
        "quality_of_final_answer": quality,
        "composite_score": composite,
    }


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def relative_improvement(new_value: float, baseline: float) -> float:
    if baseline == 0:
        return 1.0 if new_value > 0 else 0.0
    return round((new_value - baseline) / baseline, 4)


def make_starter_gate(prompt_count: int, multiframe_wins: int, assumption_improved: bool, failure_improved: bool, quality_not_reduced: bool) -> dict[str, Any]:
    if prompt_count != 5:
        return {
            "status": "NOT_APPLICABLE",
            "required_prompt_wins": 4,
            "actual_prompt_wins": multiframe_wins,
            "assumption_recall_improved": assumption_improved,
            "failure_mode_recall_improved": failure_improved,
            "quality_not_reduced": quality_not_reduced,
        }
    gate_pass = multiframe_wins >= 4 and assumption_improved and failure_improved and quality_not_reduced
    return {
        "status": "STARTER_GATE_PASS" if gate_pass else "STARTER_GATE_FAIL",
        "required_prompt_wins": 4,
        "actual_prompt_wins": multiframe_wins,
        "assumption_recall_improved": assumption_improved,
        "failure_mode_recall_improved": failure_improved,
        "quality_not_reduced": quality_not_reduced,
    }


def make_settlement_50_gate(prompt_count: int, multiframe_wins: int, assumption_relative_improvement: float, failure_relative_improvement: float, quality_not_reduced: bool) -> dict[str, Any]:
    if prompt_count != 50:
        return {
            "status": "NOT_APPLICABLE",
            "required_prompt_wins": 35,
            "actual_prompt_wins": multiframe_wins,
            "minimum_assumption_recall_relative_improvement": 0.2,
            "actual_assumption_recall_relative_improvement": assumption_relative_improvement,
            "minimum_failure_mode_recall_relative_improvement": 0.2,
            "actual_failure_mode_recall_relative_improvement": failure_relative_improvement,
            "quality_not_reduced": quality_not_reduced,
        }
    gate_pass = (
        multiframe_wins >= 35
        and assumption_relative_improvement >= 0.2
        and failure_relative_improvement >= 0.2
        and quality_not_reduced
    )
    return {
        "status": "SETTLEMENT_50_PASS" if gate_pass else "SETTLEMENT_50_FAIL",
        "required_prompt_wins": 35,
        "actual_prompt_wins": multiframe_wins,
        "minimum_assumption_recall_relative_improvement": 0.2,
        "actual_assumption_recall_relative_improvement": assumption_relative_improvement,
        "minimum_failure_mode_recall_relative_improvement": 0.2,
        "actual_failure_mode_recall_relative_improvement": failure_relative_improvement,
        "quality_not_reduced": quality_not_reduced,
    }


def build_report(prompt_set: dict[str, Any], response_fixtures: dict[str, Any], *, run_id: str) -> dict[str, Any]:
    prompts = {prompt["prompt_id"]: prompt for prompt in prompt_set["prompts"]}
    responses_by_prompt: dict[str, dict[str, dict[str, Any]]] = {prompt_id: {} for prompt_id in prompts}
    for response in response_fixtures["responses"]:
        responses_by_prompt.setdefault(response["prompt_id"], {})[response["mode"]] = response

    prompt_results = []
    multiframe_wins = 0
    per_mode_scores: dict[str, list[dict[str, Any]]] = {mode: [] for mode in MODES}
    for prompt_id, prompt in prompts.items():
        mode_scores = []
        for mode in MODES:
            response = responses_by_prompt.get(prompt_id, {}).get(mode)
            if response is None:
                raise ValueError(f"missing response for prompt {prompt_id!r} mode {mode!r}")
            score = score_response(response, prompt)
            mode_scores.append(score)
            per_mode_scores[mode].append(score)
        normal = next(item for item in mode_scores if item["mode"] == "normal_prompt")
        multiframe = next(item for item in mode_scores if item["mode"] == "multiframe_harness")
        if multiframe["composite_score"] > normal["composite_score"]:
            winner = "multiframe_harness"
            multiframe_beats_normal = True
            multiframe_wins += 1
        elif normal["composite_score"] > multiframe["composite_score"]:
            winner = "normal_prompt"
            multiframe_beats_normal = False
        else:
            winner = "tie"
            multiframe_beats_normal = False
        prompt_results.append(
            {
                "prompt_id": prompt_id,
                "mode_scores": mode_scores,
                "winner": winner,
                "multiframe_beats_normal": multiframe_beats_normal,
            }
        )

    aggregate_by_mode = {}
    for mode, scores in per_mode_scores.items():
        aggregate_by_mode[mode] = {
            "alternative_recall": average([item["alternative_recall"] for item in scores]),
            "assumption_recall": average([item["assumption_recall"] for item in scores]),
            "failure_mode_recall": average([item["failure_mode_recall"] for item in scores]),
            "bad_frame_rejection_rate": average([item["bad_frame_rejection_rate"] for item in scores]),
            "quality_of_final_answer": average([item["quality_of_final_answer"] for item in scores]),
            "composite_score": average([item["composite_score"] for item in scores]),
        }

    normal_agg = aggregate_by_mode["normal_prompt"]
    multiframe_agg = aggregate_by_mode["multiframe_harness"]
    assumption_improved = multiframe_agg["assumption_recall"] > normal_agg["assumption_recall"]
    failure_improved = multiframe_agg["failure_mode_recall"] > normal_agg["failure_mode_recall"]
    quality_not_reduced = multiframe_agg["quality_of_final_answer"] >= normal_agg["quality_of_final_answer"]
    assumption_relative_improvement = relative_improvement(multiframe_agg["assumption_recall"], normal_agg["assumption_recall"])
    failure_relative_improvement = relative_improvement(multiframe_agg["failure_mode_recall"], normal_agg["failure_mode_recall"])

    return {
        "schema_version": "stage1_multiframe_eval_v1",
        "run_id": run_id,
        "generated_by": "stage1_multiframe_fixture_scorer_v1",
        "authority": {
            "authority_level": "evaluation_only",
            "final_status_authority": "certifier_only",
            "can_certify_done": False,
        },
        "prompt_count": len(prompts),
        "prompt_results": prompt_results,
        "aggregate_metrics": {
            "mode_averages": aggregate_by_mode,
            "multiframe_prompt_wins": multiframe_wins,
            "assumption_recall_relative_improvement": assumption_relative_improvement,
            "failure_mode_recall_relative_improvement": failure_relative_improvement,
        },
        "starter_gate": make_starter_gate(len(prompts), multiframe_wins, assumption_improved, failure_improved, quality_not_reduced),
        "settlement_50_gate": make_settlement_50_gate(
            len(prompts),
            multiframe_wins,
            assumption_relative_improvement,
            failure_relative_improvement,
            quality_not_reduced,
        ),
        "claim_boundary": "This report tests deterministic fixtures only; it cannot certify final DONE or prove general reasoning superiority beyond this benchmark.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score deterministic Stage 1 multi-frame evaluation fixtures")
    parser.add_argument("--prompt-set", default=str(DEFAULT_DIR / "prompt_set.json"))
    parser.add_argument("--responses", default=str(DEFAULT_DIR / "response_fixtures.json"))
    parser.add_argument("--output", default=str(DEFAULT_DIR / "stage1_score_report.json"))
    parser.add_argument("--run-id", default="stage1_multiframe_settlement_50")
    args = parser.parse_args(argv)

    report = build_report(load_json(Path(args.prompt_set)), load_json(Path(args.responses)), run_id=args.run_id)
    write_json(Path(args.output), report)
    print(f"OK: wrote Stage 1 multi-frame score report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
