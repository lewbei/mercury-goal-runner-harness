#!/usr/bin/env python3
"""Select the best deterministic strategy without certifying DONE."""
import argparse
import json
import sys
from pathlib import Path


STATUS_FILES = {"final_status.md", "certification.json", "policy_decision.json"}
LEVEL_ORDER = {"preferred": 3, "usable": 2, "weak": 1, "blocked": 0}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def status_artifacts_absent(run_dir: Path) -> bool:
    return not any((run_dir / name).exists() for name in STATUS_FILES)


def advisory_memory_summary(run_dir: Path) -> dict:
    path = run_dir / "retrieved_experience.json"
    if not path.is_file():
        return {
            "advisory_memory_used": False,
            "advisory_memory_learning_ids": [],
            "advisory_memory_authority": "advisory_only",
            "advisory_memory_can_certify_done": False,
        }
    retrieved = load_json(path)
    return {
        "advisory_memory_used": bool(retrieved.get("matched_learning_ids")),
        "advisory_memory_learning_ids": retrieved.get("matched_learning_ids", []),
        "advisory_memory_authority": "advisory_only",
        "advisory_memory_can_certify_done": False,
    }


def select_run(run_dir: Path) -> dict:
    scores_doc = load_json(run_dir / "strategy_scores.json")
    candidates_doc = load_json(run_dir / "strategy_candidates.json")
    candidate_by_id = {
        candidate["strategy_id"]: candidate
        for candidate in candidates_doc.get("candidates", [])
    }
    usable_scores = [
        score for score in scores_doc.get("scores", [])
        if score.get("score_level") != "blocked" and score.get("strategy_id") != "S.UNKNOWN_NEED_USER"
    ]

    rejected = []
    if not usable_scores:
        for score in scores_doc.get("scores", []):
            rejected.append({
                "strategy_id": score.get("strategy_id", ""),
                "reason": "no applicable executable strategy",
            })
        decision = {
            "run_id": scores_doc.get("run_id", ""),
            "decision_status": "NEED_USER_STRATEGY",
            "selected_strategy": "",
            "reason": "No applicable executable strategy is available.",
            "rejected_strategies": rejected,
            "selector_checks": ["strategy selector did not write certification status artifacts"],
            "status_artifacts_absent_before_selection": status_artifacts_absent(run_dir),
            **advisory_memory_summary(run_dir),
        }
        write_decision_files(run_dir, decision)
        return decision

    selected_score = sorted(
        usable_scores,
        key=lambda item: (
            -item.get("score", 0),
            -LEVEL_ORDER.get(item.get("score_level", "weak"), 0),
            item.get("strategy_id", ""),
        ),
    )[0]
    selected_id = selected_score["strategy_id"]
    for score in scores_doc.get("scores", []):
        if score.get("strategy_id") != selected_id:
            rejected.append({
                "strategy_id": score.get("strategy_id", ""),
                "reason": "not selected by deterministic score ordering",
            })

    decision = {
        "run_id": scores_doc.get("run_id", ""),
        "decision_status": "SELECTED",
        "selected_strategy": selected_id,
        "reason": "Selected strategy has the best deterministic score and passed applicability checks.",
        "rejected_strategies": rejected,
        "selector_checks": [
            f"selected score level: {selected_score['score_level']}",
            "strategy selector did not write certification status artifacts",
        ],
        "status_artifacts_absent_before_selection": status_artifacts_absent(run_dir),
        **advisory_memory_summary(run_dir),
    }
    write_decision_files(run_dir, decision, candidate_by_id.get(selected_id))
    return decision


def write_decision_files(run_dir: Path, decision: dict, selected_candidate: dict | None = None) -> None:
    write_json(run_dir / "strategy_decision.json", decision)
    if selected_candidate:
        write_json(
            run_dir / "selected_strategy.json",
            {
                "run_id": decision["run_id"],
                "strategy_id": selected_candidate["strategy_id"],
                "task_type": selected_candidate["task_type"],
                "required_capabilities": selected_candidate["required_capabilities"],
                "expected_artifacts": selected_candidate["expected_artifacts"],
                "verifier_requirements": selected_candidate["verifier_requirements"],
                "risk_notes": selected_candidate["risk_notes"],
                "can_reach_certifying_evidence": selected_candidate["can_reach_certifying_evidence"],
            },
        )
    write_json(
        run_dir / "rejected_strategies.json",
        {
            "run_id": decision["run_id"],
            "rejected_strategies": decision["rejected_strategies"],
        },
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Select deterministic strategy candidate.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        decision = select_run(Path(args.run_dir))
    except Exception as exc:
        print(f"STRATEGY_SELECTION_FAILED: {exc}")
        return 1
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0 if decision["decision_status"] == "SELECTED" else 1


if __name__ == "__main__":
    sys.exit(main())
