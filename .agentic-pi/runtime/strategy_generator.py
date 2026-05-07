#!/usr/bin/env python3
"""Generate deterministic strategy candidates for a routed task type."""
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


def need_user_candidate(task_type: str) -> dict:
    return base_candidate(
        "S.UNKNOWN_NEED_USER",
        task_type,
        [],
        [],
        ["user must classify the task or provide verifier direction"],
        ["unknown or high-risk tasks should not be executed speculatively"],
        False,
    )


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
    if task_type in {"experiment", "devops"}:
        return [need_user_candidate(task_type)]
    return [need_user_candidate("unknown")]


def unique_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def load_domain_pack(run_dir: Path) -> tuple[dict | None, dict | None]:
    selection_path = run_dir / "domain_pack_selection.json"
    if not selection_path.is_file():
        return None, None
    selection = load_json(selection_path)
    if selection.get("selection_status") != "SELECTED":
        return selection, None
    pack_path_value = selection.get("domain_pack_path", "")
    if not pack_path_value:
        return selection, None
    pack_path = ROOT / pack_path_value
    pack = load_json(pack_path)
    return selection, pack


def apply_domain_pack(candidates: list[dict], pack: dict | None) -> tuple[list[dict], list[str]]:
    if not pack:
        return candidates, []

    allowed = set(pack.get("allowed_strategies", []))
    filtered = [
        candidate
        for candidate in candidates
        if candidate.get("strategy_id") in allowed
    ]
    selected = filtered or candidates
    notes = []
    if not filtered:
        notes.append("selected domain pack did not match base strategy ids; base candidates retained")

    enriched = []
    for candidate in selected:
        candidate = dict(candidate)
        candidate["required_capabilities"] = unique_preserve_order(
            candidate.get("required_capabilities", []) + pack.get("common_capabilities", [])
        )
        candidate["verifier_requirements"] = unique_preserve_order(
            candidate.get("verifier_requirements", []) + pack.get("verifier_requirements", [])
        )
        candidate["risk_notes"] = unique_preserve_order(
            candidate.get("risk_notes", []) + pack.get("risk_rules", [])
        )
        enriched.append(candidate)
    return enriched, notes


def generate_for_run(run_dir: Path) -> dict:
    task_decision = load_json(run_dir / "task_type_decision.json")
    goal = load_json(run_dir / "goal_contract.json")
    candidates = candidates_for_task_type(task_decision["task_type"], goal)
    selection, pack = load_domain_pack(run_dir)
    candidates, domain_notes = apply_domain_pack(candidates, pack)
    output = {
        "run_id": task_decision["run_id"],
        "task_type": task_decision["task_type"],
        "domain_pack_applied": pack.get("domain_pack_id", "") if pack else "",
        "domain_pack_selection_status": selection.get("selection_status", "NOT_RUN") if selection else "NOT_RUN",
        "domain_pack_notes": domain_notes,
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
