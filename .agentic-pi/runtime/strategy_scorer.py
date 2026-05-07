#!/usr/bin/env python3
"""Score applicable strategy candidates deterministically."""
import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def score_level(score: int) -> str:
    if score >= 7:
        return "preferred"
    if score >= 3:
        return "usable"
    return "weak"


def score_candidate(candidate: dict, provenance_mode: bool) -> dict:
    score = 0
    positives = []
    penalties = []

    if candidate.get("can_reach_certifying_evidence") is True:
        score += 3
        positives.append("can_reach_certifying_evidence")
    elif provenance_mode:
        score -= 3
        penalties.append("no_verifier_path_in_provenance_mode")

    if candidate.get("uses_artifact_tests") is True and candidate.get("needs_executable_behavior") is True:
        score += 2
        positives.append("uses_artifact_tests_for_executable_behavior")

    if candidate.get("expected_artifacts"):
        score += 2
        positives.append("produces_expected_artifacts")

    if candidate.get("risk_level") == "LOW":
        score += 1
        positives.append("low_risk")

    if len(candidate.get("required_capabilities", [])) <= 3:
        score += 1
        positives.append("small_capability_surface")

    return {
        "strategy_id": candidate.get("strategy_id", ""),
        "score": score,
        "score_level": score_level(score),
        "positive_factors": positives,
        "penalties": penalties,
    }


def score_run(run_dir: Path) -> dict:
    applicability = load_json(run_dir / "strategy_applicability.json")
    provenance_mode = (run_dir / "verifier_contract.json").is_file()
    scores = [
        score_candidate(candidate, provenance_mode)
        for candidate in applicability.get("applicable_strategies", [])
    ]
    for blocked in applicability.get("blocked_strategies", []):
        scores.append({
            "strategy_id": blocked.get("strategy_id", ""),
            "score": -99,
            "score_level": "blocked",
            "positive_factors": [],
            "penalties": blocked.get("block_reasons", []),
        })

    output = {
        "run_id": applicability.get("run_id", ""),
        "task_type": applicability.get("task_type", "unknown"),
        "scores": scores,
    }
    write_json(run_dir / "strategy_scores.json", output)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Score deterministic strategy candidates.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        output = score_run(Path(args.run_dir))
    except Exception as exc:
        print(f"STRATEGY_SCORING_FAILED: {exc}")
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
