#!/usr/bin/env python3
"""Generate deterministic strategy candidates for a routed task type."""
import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def base_candidate(strategy_id, task_type, required, expected, verifier, risk, certifying, executable=False):
    return {
        "strategy_id": strategy_id,
        "task_type": task_type,
        "required_capabilities": required,
        "expected_artifacts": expected,
        "verifier_requirements": verifier,
        "risk_notes": risk,
        "can_reach_certifying_evidence": certifying,
        "uses_artifact_tests": executable,
        "needs_executable_behavior": executable,
        "attempts_status_write": False,
        "attempts_verifier_forgery": False,
        "status_authority": "none",
        "risk_level": "LOW" if certifying else "MEDIUM",
    }


def candidates_for_task_type(task_type: str, goal: dict) -> list[dict]:
    final_outputs = goal.get("final_outputs") or ["artifacts/output.txt"]
    final_output = final_outputs[0]
    if task_type == "writing":
        return [
            base_candidate(
                "S.WRITE_SIMPLE",
                task_type,
                ["file_write_run_folder", "plan_graph", "policy_engine"],
                [final_output],
                ["P2/P3 verifier evidence required when provenance mode is active"],
                ["simple writing strategy is not semantic proof"],
                True,
            )
        ]
    if task_type == "coding":
        return [
            base_candidate(
                "S.CODE_ARTIFACT_TEST",
                task_type,
                ["file_write_run_folder", "python_command", "artifact_test", "plan_graph", "policy_engine"],
                [final_output],
                ["behavior must be checked by artifact tests or P2/P3 verifier evidence"],
                ["code can exist while behavior is wrong"],
                True,
                executable=True,
            )
        ]
    if task_type == "research":
        return [
            base_candidate(
                "S.RESEARCH_SOURCE_AUDIT",
                task_type,
                ["file_write_run_folder", "audit", "policy_engine"],
                [final_output],
                ["source-backed claims require independent verifier or human review"],
                ["research claims can overstate novelty"],
                False,
            )
        ]
    if task_type == "debugging":
        return [
            base_candidate(
                "S.DEBUG_REPRO_THEN_PATCH",
                task_type,
                ["file_write_run_folder", "python_command", "artifact_test", "plan_graph", "policy_engine"],
                [final_output],
                ["reproduction and regression behavior must be verified"],
                ["patch can hide failure without reproducing it"],
                True,
                executable=True,
            )
        ]
    if task_type == "benchmark":
        return [
            base_candidate(
                "S.BENCHMARK_DIAGNOSTIC",
                task_type,
                ["file_write_run_folder", "artifact_test", "plan_graph", "policy_engine"],
                [final_output],
                ["expected-vs-actual and false-pass metrics required"],
                ["benchmark reports can be stale or cherry-picked"],
                True,
                executable=True,
            )
        ]
    return [
        base_candidate(
            "S.UNKNOWN_NEED_USER",
            "unknown",
            [],
            [],
            ["user must classify the task or provide verifier direction"],
            ["unknown tasks should not be executed speculatively"],
            False,
        )
    ]


def generate_for_run(run_dir: Path) -> dict:
    task_decision = load_json(run_dir / "task_type_decision.json")
    goal = load_json(run_dir / "goal_contract.json")
    candidates = candidates_for_task_type(task_decision["task_type"], goal)
    output = {
        "run_id": task_decision["run_id"],
        "task_type": task_decision["task_type"],
        "candidates": candidates,
    }
    write_json(run_dir / "strategy_candidates.json", output)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic strategy candidates.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        output = generate_for_run(Path(args.run_dir))
    except Exception as exc:
        print(f"STRATEGY_GENERATION_FAILED: {exc}")
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
