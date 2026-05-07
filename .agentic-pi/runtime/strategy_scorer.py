#!/usr/bin/env python3
"""Score applicable strategy candidates deterministically."""
import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_retrieved_experience(retrieved: dict) -> None:
    schema = load_json(ROOT / ".agentic-pi" / "schemas" / "retrieved_experience.schema.json")
    validator_path = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate_schema_for_strategy_scorer", validator_path)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    errors = validator.validate(retrieved, schema)
    if errors:
        raise ValueError("retrieved_experience.json schema invalid: " + "; ".join(errors))


def score_level(score: int) -> str:
    if score >= 7:
        return "preferred"
    if score >= 3:
        return "usable"
    return "weak"


def adjustments_by_strategy(run_dir: Path) -> dict[str, list[dict]]:
    path = run_dir / "retrieved_experience.json"
    if not path.is_file():
        return {}
    retrieved = load_json(path)
    validate_retrieved_experience(retrieved)
    if retrieved.get("final_status_authority") != "certifier_only" or retrieved.get("can_certify_done") is not False:
        raise ValueError("retrieved_experience.json must be advisory and certifier_only")
    output = {}
    for adjustment in retrieved.get("strategy_adjustments", []):
        strategy_id = adjustment.get("strategy_id", "")
        if strategy_id:
            adjustment = dict(adjustment)
            adjustment["score_delta"] = max(-2, min(1, int(adjustment.get("score_delta", 0))))
            output.setdefault(strategy_id, []).append(adjustment)
    return output


def score_candidate(candidate: dict, provenance_mode: bool, experience_adjustments: list[dict] | None = None) -> dict:
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

    for adjustment in experience_adjustments or []:
        delta = adjustment.get("score_delta", 0)
        reason = adjustment.get("reason", "experience memory")
        if delta > 0:
            score += delta
            positives.append(reason)
        elif delta < 0:
            score += delta
            penalties.append(reason)

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
    memory_adjustments = adjustments_by_strategy(run_dir)
    scores = [
        score_candidate(candidate, provenance_mode, memory_adjustments.get(candidate.get("strategy_id", ""), []))
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
        "experience_memory_used": bool(memory_adjustments),
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
