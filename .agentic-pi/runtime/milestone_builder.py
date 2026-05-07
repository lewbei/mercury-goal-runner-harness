#!/usr/bin/env python3
"""Build deterministic milestone_plan.json from the selected strategy."""
import argparse
import json
import sys
from pathlib import Path


MILESTONES_BY_TASK_TYPE = {
    "coding": [
        ("M.CODING_REPRODUCE_INSPECT", "reproduce/inspect", "Confirm the target behavior and inspect the expected artifact path."),
        ("M.CODING_PATCH", "patch", "Create the minimal target artifact needed by the selected strategy."),
        ("M.CODING_VERIFY", "verify", "Prepare behavior-verification evidence requirements."),
        ("M.CODING_CERTIFY", "certify", "Hand the run to the deterministic certifier."),
    ],
    "debugging": [
        ("M.DEBUG_REPRODUCE", "reproduce", "State the failure that the patch is expected to address."),
        ("M.DEBUG_INSPECT", "inspect", "Inspect the relevant artifact and constraint surface."),
        ("M.DEBUG_PATCH", "patch", "Create the minimal patch artifact."),
        ("M.DEBUG_REGRESSION_VERIFY", "regression verify", "Prepare regression-verification evidence requirements."),
        ("M.DEBUG_CERTIFY", "certify", "Hand the run to the deterministic certifier."),
    ],
    "research": [
        ("M.RESEARCH_DEFINE_CLAIM", "define claim", "State the claim and evidence standard."),
        ("M.RESEARCH_COLLECT_SOURCES", "collect closest sources", "List the source evidence needed before any strong claim."),
        ("M.RESEARCH_MATRIX", "build comparison matrix", "Compare the claim against closest evidence."),
        ("M.RESEARCH_ATTACK_NOVELTY", "attack novelty", "Record skeptical failure modes and overclaim risks."),
        ("M.RESEARCH_FINAL_VERDICT", "final verdict", "Write the bounded research verdict artifact."),
    ],
    "writing": [
        ("M.WRITING_OUTLINE", "outline", "Create the structure before drafting."),
        ("M.WRITING_DRAFT", "draft", "Draft the requested artifact."),
        ("M.WRITING_VERIFY_CONSTRAINTS", "verify constraints", "Check required wording, scope, and output path."),
        ("M.WRITING_FINALIZE", "finalize", "Write the final output artifact."),
    ],
    "benchmark": [
        ("M.BENCHMARK_DEFINE_EXPECTED", "define expected", "Record expected-vs-actual behavior before judging output."),
        ("M.BENCHMARK_RUN_DIAGNOSTIC", "run diagnostic", "Create diagnostic artifacts without trusting model self-report."),
        ("M.BENCHMARK_COMPARE", "compare", "Compare expected and actual statuses."),
        ("M.BENCHMARK_FALSE_PASS_CHECK", "false pass check", "Check for false PASS / false CERTIFIED_DONE risk."),
        ("M.BENCHMARK_CERTIFY", "certify", "Hand the run to the deterministic certifier."),
    ],
    "experiment": [
        ("M.EXPERIMENT_DEFINE_PROTOCOL", "define protocol", "Record protocol and evidence requirements."),
        ("M.EXPERIMENT_PREPARE_ARTIFACTS", "prepare artifacts", "Prepare deterministic experiment artifacts."),
        ("M.EXPERIMENT_CHECK_RESULTS", "check results", "Compare generated artifacts against expected results."),
        ("M.EXPERIMENT_CERTIFY", "certify", "Hand the run to the deterministic certifier."),
    ],
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def milestone_rows(task_type: str) -> list[tuple[str, str, str]]:
    return MILESTONES_BY_TASK_TYPE.get(task_type, [
        ("M.UNKNOWN_NEED_USER", "need user", "Unknown tasks need user classification before execution."),
    ])


def build_milestone_plan(run_dir: Path) -> dict:
    selected = load_json(run_dir / "selected_strategy.json")
    goal = load_json(run_dir / "goal_contract.json")
    task_type = selected.get("task_type", "unknown")
    final_outputs = goal.get("final_outputs") or ["artifacts/output.txt"]

    milestones = []
    rows = milestone_rows(task_type)
    for index, (milestone_id, title, purpose) in enumerate(rows, start=1):
        is_final = index == len(rows)
        milestones.append({
            "order": index,
            "milestone_id": milestone_id,
            "title": title,
            "purpose": purpose,
            "expected_artifacts": final_outputs if is_final else [
                f"artifacts/milestones/{milestone_id.lower().replace('.', '_')}.md"
            ],
            "verifier_relevance": (
                "Final output must still be judged by verifier provenance and certifier policy."
                if is_final
                else "Advisory planning evidence only; cannot certify DONE."
            ),
        })

    output = {
        "run_id": selected["run_id"],
        "generated_by": "milestone-builder-v1.4",
        "selected_strategy": selected["strategy_id"],
        "task_type": task_type,
        "final_status_authority": "certifier_only",
        "milestones": milestones,
    }
    write_json(run_dir / "milestone_plan.json", output)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic milestone_plan.json.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        output = build_milestone_plan(Path(args.run_dir))
    except Exception as exc:
        print(f"MILESTONE_BUILD_FAILED: {exc}")
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
