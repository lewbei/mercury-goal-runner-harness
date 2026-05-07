#!/usr/bin/env python3
"""Score verifier strength from provenance metadata and smell reports."""
import json
import sys
from pathlib import Path


INDEPENDENT_SOURCES = {
    "independent_verifier_agent",
    "user_provided",
    "hidden_oracle",
    "external_benchmark",
    "human_review",
}

POSITIVE_POINTS = {
    "executes_target_artifact": 2,
    "has_assertions": 2,
    "multiple_assertions": 2,
    "p2_or_p3_authority": 2,
    "independent_authority": 2,
    "pre_solution_or_preexisting": 1,
}

PENALTY_POINTS = {
    "same_worker_self_test": 3,
    "p0_self_authored": 3,
    "post_solution_test": 2,
    "depends_on_solution": 2,
    "does_not_execute_code": 2,
    "zero_assertions": 2,
    "file_existence_only": 2,
    "exit_code_only": 2,
    "print_only_observation": 2,
    "mock_heavy": 2,
    "implementation_coupled_oracle": 3,
}

CRITICAL_STRENGTH_CAPS = {
    "does_not_execute_code": 1,
    "zero_assertions": 4,
    "mock_heavy": 7,
    "implementation_coupled_oracle": 4,
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_strength_report_filename(artifact_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in artifact_id)
    return f"{safe or 'UNKNOWN'}.json"


def strength_level(score: int) -> str:
    if score <= 1:
        return "weak"
    if score <= 4:
        return "advisory"
    if score <= 7:
        return "gating"
    return "certifying"


def positive_factors_for_artifact(artifact: dict) -> list:
    factors = []

    if artifact.get("executes_code") is True:
        factors.append("executes_target_artifact")

    assertion_count = artifact.get("assertion_count")
    if isinstance(assertion_count, int) and assertion_count > 0:
        factors.append("has_assertions")
    if isinstance(assertion_count, int) and assertion_count >= 2:
        factors.append("multiple_assertions")

    if artifact.get("provenance_level") in {"P2", "P3"}:
        factors.append("p2_or_p3_authority")

    if artifact.get("source") in INDEPENDENT_SOURCES:
        factors.append("independent_authority")

    if artifact.get("created_at_phase") in {"pre_solution", "external_preexisting"}:
        factors.append("pre_solution_or_preexisting")

    return factors


def penalties_from_smell_report(smell_report: dict) -> list:
    flags = smell_report.get("smell_flags", [])
    if not isinstance(flags, list):
        return []
    return [flag for flag in flags if flag in PENALTY_POINTS]


def apply_critical_caps(score: int, penalties: list) -> int:
    capped_score = score
    for penalty in penalties:
        if penalty in CRITICAL_STRENGTH_CAPS:
            capped_score = min(capped_score, CRITICAL_STRENGTH_CAPS[penalty])
    return capped_score


def score_verifier_artifact(artifact: dict, smell_report: dict = None) -> dict:
    smell_report = smell_report or {"smell_flags": []}
    factors = positive_factors_for_artifact(artifact)
    penalties = penalties_from_smell_report(smell_report)
    score = sum(POSITIVE_POINTS[factor] for factor in factors)
    score -= sum(PENALTY_POINTS[penalty] for penalty in penalties)
    score = apply_critical_caps(score, penalties)

    return {
        "artifact_id": artifact.get("artifact_id", ""),
        "run_id": artifact.get("run_id", ""),
        "score": score,
        "strength_level": strength_level(score),
        "positive_factors": factors,
        "penalties": penalties,
        "smell_flags_used": smell_report.get("smell_flags", []),
    }


def score_artifact_file(artifact_path: Path, smell_report_path: Path = None) -> dict:
    artifact = load_json(artifact_path)
    smell_report = load_json(smell_report_path) if smell_report_path else None
    return score_verifier_artifact(artifact, smell_report)


def score_run_dir(run_dir: Path) -> list:
    verifier_dir = run_dir / "verifier_artifacts"
    smell_dir = run_dir / "verifier_smell_reports"
    if not verifier_dir.exists():
        return []

    reports = []
    for artifact_path in sorted(verifier_dir.glob("*.json")):
        artifact = load_json(artifact_path)
        artifact_id = str(artifact.get("artifact_id") or "UNKNOWN")
        smell_path = smell_dir / safe_strength_report_filename(artifact_id)
        smell_report = load_json(smell_path) if smell_path.exists() else None
        reports.append(score_verifier_artifact(artifact, smell_report))
    return reports


def main():
    if len(sys.argv) not in {2, 3, 4}:
        print(
            "Usage: python strength_scorer.py <verifier_artifact.json|run_dir> "
            "[smell_report.json] [output_dir]"
        )
        sys.exit(2)

    input_path = Path(sys.argv[1])
    second_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else None
    output_dir = Path(sys.argv[3]) if len(sys.argv) == 4 else None

    if input_path.is_dir():
        reports = score_run_dir(input_path)
        if second_path and output_dir is None:
            output_dir = second_path
    else:
        reports = [score_artifact_file(input_path, second_path)]

    if output_dir:
        for report in reports:
            write_json(output_dir / safe_strength_report_filename(report["artifact_id"]), report)

    print(json.dumps(reports, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
