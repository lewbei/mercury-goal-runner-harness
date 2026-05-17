#!/usr/bin/env python3
"""Run-folder roadmap planner for the current strict harness path.

This replaces the legacy hardcoded `.agentic-runs/roadmap/` planner. It reads a
run-local `goal_contract.json`, routes the task, selects a deterministic
strategy, builds milestones/local steps, writes a planner-owned plan candidate,
then runs the strict `plan_selector.py` + `plan_merger.py` handoff.

It does not execute worker steps and it does not certify DONE. All artifacts are
written under `.agentic-runs/<run_id>/`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = ROOT / ".agentic-runs"
VALIDATORS = ROOT / ".agentic-pi" / "validators"
ARTIFACT_VALIDATORS = ROOT / ".agentic-pi" / "artifacts" / "validators"
GOAL_SCHEMA = ROOT / ".agentic-pi" / "schemas" / "goal_contract.schema.json"
STATUS_ARTIFACTS = {
    "final_status.json",
    "final_status.md",
    "certification.json",
    "policy_decision.json",
}
STOP_AFTER_CHOICES = {"strategy", "milestones", "local_steps", "plan_graph"}


class RoadmapPlannerError(RuntimeError):
    """Raised when roadmap planning cannot continue safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_run_dir(raw: str | None, run_id: str | None) -> Path:
    if run_id:
        candidate = RUNS_ROOT / run_id
    elif raw:
        raw_path = Path(raw)
        if raw_path.is_absolute():
            candidate = raw_path
        elif raw_path.parts and raw_path.parts[0] == ".agentic-runs":
            candidate = ROOT / raw_path
        else:
            candidate = RUNS_ROOT / raw_path
    else:
        raise RoadmapPlannerError("provide a run id/path or --run-id")

    run_dir = candidate.resolve()
    runs_root = RUNS_ROOT.resolve()
    if run_dir != runs_root and runs_root not in run_dir.parents:
        raise RoadmapPlannerError(f"run directory must be under .agentic-runs: {candidate}")
    if not run_dir.is_dir():
        raise RoadmapPlannerError(f"run directory does not exist: {run_relative(run_dir)}")
    return run_dir


def ensure_run_relative_path(run_dir: Path, raw_path: str) -> str:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise RoadmapPlannerError("artifact path must be a non-empty string")
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise RoadmapPlannerError(f"absolute artifact path is not allowed: {raw_path}")
    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise RoadmapPlannerError(f"artifact path escapes run folder: {raw_path}")
    return resolved.relative_to(run_root).as_posix()


def validate_goal_contract(goal_path: Path) -> dict:
    if not goal_path.is_file():
        raise RoadmapPlannerError(f"goal_contract.json missing: {run_relative(goal_path)}")
    goal = load_json(goal_path)
    if not isinstance(goal, dict):
        raise RoadmapPlannerError("goal_contract.json must be a JSON object")

    validator = load_module("validate_schema_for_roadmap", VALIDATORS / "validate_schema.py")
    schema = load_json(GOAL_SCHEMA)
    errors = validator.validate(goal, schema)
    if errors:
        raise RoadmapPlannerError("goal_contract.json schema invalid: " + "; ".join(errors[:10]))

    final_outputs = goal.get("final_outputs")
    if not isinstance(final_outputs, list) or not final_outputs:
        raise RoadmapPlannerError("goal_contract.final_outputs must be a non-empty list")
    if not goal.get("done_criteria"):
        raise RoadmapPlannerError("goal_contract.done_criteria must be non-empty")
    return goal


def assert_no_authority_artifacts(run_dir: Path, *, allow_existing_authority: bool) -> None:
    existing = sorted(name for name in STATUS_ARTIFACTS if (run_dir / name).exists())
    if existing and not allow_existing_authority:
        raise RoadmapPlannerError(
            "refusing to roadmap-plan over existing authority artifacts: " + ", ".join(existing)
        )


def run_tool(args: list[str], *, allow_failure: bool = False) -> dict:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output = result.stdout or ""
    if result.returncode != 0 and not allow_failure:
        raise RoadmapPlannerError(
            f"tool failed ({result.returncode}): {' '.join(args)}\n{output}"
        )
    return {
        "command": ["python", *args],
        "exit_code": result.returncode,
        "stdout_tail": "\n".join(output.splitlines()[-20:]),
    }


def step_record(label: str, tool_result: dict | None, outputs: list[str]) -> dict:
    record = {
        "label": label,
        "outputs": outputs,
    }
    if tool_result is not None:
        record.update(tool_result)
    return record


def write_expected_artifacts_from_plan(run_dir: Path, goal: dict) -> dict:
    local_step_plan = load_json(run_dir / "local_step_plan.json")
    artifacts: list[dict] = []
    seen_paths: set[str] = set()
    done_criteria = [str(item) for item in goal.get("done_criteria", [])]

    for step in local_step_plan.get("local_steps", []):
        for produced in step.get("produces", []):
            path = ensure_run_relative_path(run_dir, produced.get("path", ""))
            if path in seen_paths:
                continue
            seen_paths.add(path)
            artifact_id = produced.get("artifact_id") or f"A.{len(artifacts) + 1:03d}"
            artifacts.append(
                {
                    "artifact_id": artifact_id,
                    "expected_path": path,
                    "description": "Roadmap-planned artifact; execution still requires worker evidence and certifier checks.",
                    "required": True,
                    "allowed_writers": ["Engineer"],
                    "forbidden_writers": ["Reporter", "Critic", "Certifier"],
                    "success_criteria": done_criteria,
                    "min_size_bytes": 1,
                }
            )

    if not artifacts:
        raise RoadmapPlannerError("local_step_plan.json produced no expected artifacts")

    output = {
        "schema_version": "expected_artifacts_v1",
        "run_id": run_dir.name,
        "phase": "PLANNING",
        "artifacts": artifacts,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    write_json(run_dir / "expected_artifacts.json", output)

    validator = load_module("validate_expected_artifacts_for_roadmap", ARTIFACT_VALIDATORS / "validate_expected_artifacts.py")
    errors = validator.validate_expected_artifacts(output)
    if errors:
        raise RoadmapPlannerError("expected_artifacts.json invalid: " + "; ".join(errors[:10]))
    return output


def write_vertical_slice_inputs_from_local_steps(run_dir: Path) -> dict:
    """Write run-kernel vertical-slice gate inputs from the roadmap plan.

    These artifacts are planning-only. They let the run kernel validate that a
    concrete first slice exists before IMPLEMENTING, but they do not execute,
    verify, or certify the run.
    """
    local_step_plan = load_json(run_dir / "local_step_plan.json")
    local_steps = local_step_plan.get("local_steps", [])
    if not local_steps:
        raise RoadmapPlannerError("local_step_plan.json has no local_steps for vertical slice gate")

    produced_paths = []
    milestone_ids = []
    for step in local_steps:
        milestone_id = str(step.get("milestone_id", "")).strip()
        if milestone_id and milestone_id not in milestone_ids:
            milestone_ids.append(milestone_id)
        for produced in step.get("produces", []):
            path = ensure_run_relative_path(run_dir, str(produced.get("path", "")))
            if path not in produced_paths:
                produced_paths.append(path)

    macro_plan = {
        "schema_version": "macro_plan_v1",
        "run_id": run_dir.name,
        "generated_by": "roadmap_planner.py",
        "generated_at": utc_now(),
        "authority": {
            "authority_level": "planning_only",
            "final_status_authority": "certifier_only",
            "can_certify_done": False,
        },
        "source": "local_step_plan.json",
        "selected_strategy": local_step_plan.get("selected_strategy", ""),
        "milestone_ids": milestone_ids,
        "expected_artifact_paths": produced_paths,
        "kernel_gate": "WORKTREE_READY_to_IMPLEMENTING",
    }
    write_json(run_dir / "macro_plan.json", macro_plan)

    candidates = {
        "schema_version": "vertical_slice_candidates_v1",
        "run_id": run_dir.name,
        "generated_by": "roadmap_planner.py",
        "generated_at": utc_now(),
        "authority": {
            "authority_level": "planning_only",
            "final_status_authority": "certifier_only",
            "can_certify_done": False,
        },
        "candidates": [
            {
                "slice_id": "VS.ROADMAP.PRIMARY",
                "fixture": "expected_artifacts.json",
                "expected_verdict": "planner_ready_not_certified",
                "end_to_end_layers": [
                    "planning_coverage",
                    "artifact_contract",
                    "guarded_execution",
                    "verifier_evidence",
                    "certifier_policy",
                ],
                "end_to_end_coverage": 5,
                "fake_done_risk": 1,
                "authority_boundary_value": 10,
                "validator_availability": 8,
                "low_implementation_cost": 8,
                "replay_certification_impact": 8,
                "source_plan": "local_step_plan.json",
                "planned_artifacts": produced_paths,
                "can_certify_done": False,
            }
        ],
    }
    write_json(run_dir / "vertical_slice_candidates.json", candidates)
    return {"candidate_count": len(candidates["candidates"]), "artifact_count": len(produced_paths)}


def write_planner_candidate_from_local_steps(run_dir: Path) -> Path:
    local_step_plan = load_json(run_dir / "local_step_plan.json")
    steps = []
    for index, step in enumerate(local_step_plan.get("local_steps", []), start=1):
        path = ensure_run_relative_path(run_dir, step.get("path", ""))
        normalized = {
            "task_id": step.get("task_id") or f"T.ROADMAP_{index:03d}",
            "milestone_id": step.get("milestone_id", ""),
            "local_step_id": step.get("local_step_id", ""),
            "action": "create_file",
            "path": path,
            "content": step.get("content", ""),
            "requires": [str(item) for item in step.get("requires", [])],
            "produces": [],
        }
        for produced in step.get("produces", []):
            normalized["produces"].append(
                {
                    "artifact_id": str(produced.get("artifact_id") or f"A.ROADMAP_{index:03d}"),
                    "path": ensure_run_relative_path(run_dir, str(produced.get("path", path))),
                }
            )
        steps.append(normalized)

    if not steps:
        raise RoadmapPlannerError("local_step_plan.json has no local_steps")

    plan = {
        "schema_version": "planner_plan_v1",
        "planner": "roadmap_planner.py",
        "run_id": run_dir.name,
        "source": "local_step_plan.json",
        "selected_strategy": local_step_plan.get("selected_strategy", ""),
        "strategy_task_type": local_step_plan.get("task_type", "unknown"),
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "steps": steps,
    }
    out_path = run_dir / "plans" / "roadmap_planner_plan.json"
    write_json(out_path, plan)
    return out_path


def run_roadmap_planner(
    run_dir: Path,
    *,
    stop_after: str = "plan_graph",
    allow_existing_authority: bool = False,
) -> dict:
    if stop_after not in STOP_AFTER_CHOICES:
        raise RoadmapPlannerError(f"invalid stop_after: {stop_after}")

    assert_no_authority_artifacts(run_dir, allow_existing_authority=allow_existing_authority)
    goal = validate_goal_contract(run_dir / "goal_contract.json")
    steps: list[dict] = []

    tools = [
        ("task type routed", [".agentic-pi/runtime/task_type_router.py", str(run_dir)], ["task_type_decision.json"], False),
        ("domain pack selected", [".agentic-pi/runtime/domain_pack_selector.py", str(run_dir)], ["domain_pack_selection.json"], False),
        ("capability inventory written", [".agentic-pi/runtime/capability_inventory.py", str(run_dir)], ["capability_inventory.json"], False),
        ("strategy candidates generated", [".agentic-pi/runtime/strategy_generator.py", str(run_dir)], ["strategy_candidates.json"], False),
        ("strategy applicability gated", [".agentic-pi/runtime/strategy_applicability_gate.py", str(run_dir)], ["strategy_applicability.json"], False),
        ("advisory experience retrieved", [".agentic-pi/runtime/experience_retriever.py", str(run_dir)], ["retrieved_experience.json"], False),
        ("adaptive research inputs recorded", [".agentic-pi/runtime/adaptive_research_inputs.py", str(run_dir)], ["adaptive_research_inputs.json"], False),
        ("adaptive research inputs validated", [".agentic-pi/validators/validate_adaptive_research_inputs.py", str(run_dir)], ["adaptive_research_inputs.json"], False),
        ("strategy scores recorded", [".agentic-pi/runtime/strategy_scorer.py", str(run_dir)], ["strategy_scores.json"], False),
        ("strategy selected", [".agentic-pi/runtime/strategy_selector.py", str(run_dir)], ["strategy_decision.json", "selected_strategy.json", "rejected_strategies.json"], True),
    ]

    for label, command, outputs, allow_failure in tools:
        result = run_tool(command, allow_failure=allow_failure)
        steps.append(step_record(label, result, outputs))
        if label == "strategy selected":
            decision = load_json(run_dir / "strategy_decision.json")
            for tree_label, tree_command, tree_outputs in [
                ("bounded planning search tree written", [".agentic-pi/runtime/planning_search_tree.py", str(run_dir)], ["planning_search_tree.json"]),
                ("bounded planning search tree validated", [".agentic-pi/validators/validate_planning_search_tree.py", str(run_dir)], ["planning_search_tree.json"]),
            ]:
                steps.append(step_record(tree_label, run_tool(tree_command), tree_outputs))
            if decision.get("decision_status") != "SELECTED":
                summary = build_summary(run_dir, "NEED_USER_STRATEGY", steps, extra={"strategy_decision": decision})
                write_json(run_dir / "roadmap_summary.json", summary)
                return summary

    if stop_after == "strategy":
        summary = build_summary(run_dir, "STRATEGY_SELECTED", steps)
        write_json(run_dir / "roadmap_summary.json", summary)
        return summary

    for label, command, outputs in [
        ("milestone plan built", [".agentic-pi/runtime/milestone_builder.py", str(run_dir)], ["milestone_plan.json"]),
        ("milestone status recorded", [".agentic-pi/runtime/milestone_tracker.py", str(run_dir)], ["milestone_status.json"]),
    ]:
        steps.append(step_record(label, run_tool(command), outputs))

    if stop_after == "milestones":
        summary = build_summary(run_dir, "MILESTONES_PLANNED", steps)
        write_json(run_dir / "roadmap_summary.json", summary)
        return summary

    for label, command, outputs in [
        ("local step plan built", [".agentic-pi/runtime/local_step_planner.py", str(run_dir)], ["local_step_plan.json"]),
    ]:
        steps.append(step_record(label, run_tool(command), outputs))

    expected = write_expected_artifacts_from_plan(run_dir, goal)
    steps.append(step_record("expected artifacts written", None, ["expected_artifacts.json"]))

    vertical_slice = write_vertical_slice_inputs_from_local_steps(run_dir)
    steps.append(step_record("vertical slice gate inputs written", None, ["macro_plan.json", "vertical_slice_candidates.json"]))

    plan_path = write_planner_candidate_from_local_steps(run_dir)
    steps.append(step_record("planner-owned plan candidate written", None, [plan_path.relative_to(run_dir).as_posix()]))

    if stop_after == "local_steps":
        summary = build_summary(run_dir, "LOCAL_STEPS_PLANNED", steps, extra={"expected_artifact_count": len(expected["artifacts"]), "vertical_slice_candidate_count": vertical_slice["candidate_count"]})
        write_json(run_dir / "roadmap_summary.json", summary)
        return summary

    for label, command, outputs in [
        ("strict plan selected", [".agentic-pi/runtime/plan_selector.py", "--run-id", run_dir.name], ["selected_plan.json"]),
        ("strict plan merged", [".agentic-pi/runtime/plan_merger.py", "--run-id", run_dir.name], ["merged_plan.json"]),
        ("plan graph built", [".agentic-pi/runtime/plan_graph_builder.py", run_dir.name], ["plan_graph.json"]),
        ("planning coverage written", [".agentic-pi/runtime/planning_coverage.py", str(run_dir)], ["planning_coverage.json"]),
        ("planning coverage validated", [".agentic-pi/validators/validate_planning_coverage.py", str(run_dir)], ["planning_coverage.json"]),
    ]:
        steps.append(step_record(label, run_tool(command), outputs))

    summary = build_summary(run_dir, "PLAN_GRAPH_READY", steps, extra={"expected_artifact_count": len(expected["artifacts"]), "vertical_slice_candidate_count": vertical_slice["candidate_count"]})
    write_json(run_dir / "roadmap_summary.json", summary)
    return summary


def build_summary(run_dir: Path, status: str, steps: list[dict], *, extra: dict | None = None) -> dict:
    summary = {
        "schema_version": "roadmap_summary_v1",
        "run_id": run_dir.name,
        "generated_at": utc_now(),
        "status": status,
        "authority": {
            "authority_level": "planning_only",
            "can_certify_done": False,
            "final_status_authority": "certifier_only",
        },
        "run_dir": run_relative(run_dir),
        "steps": steps,
        "next_steps": [
            "Review planning_coverage.json to see selected, rejected, and deferred planning branches.",
            "Run guarded_worker.py only after reviewing merged_plan.json and expected_artifacts.json.",
            "Add verifier_contract.json and verifier_artifacts/*.json before full_verify.py.",
            "Run full_verify.py for certifier-owned status; roadmap_summary.json cannot certify DONE.",
        ],
    }
    if extra:
        summary.update(extra)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build current run-folder roadmap planning artifacts without certifying DONE.")
    parser.add_argument("run", nargs="?", help="Run id or .agentic-runs/<run_id> path")
    parser.add_argument("--run-id", help="Run identifier under .agentic-runs/")
    parser.add_argument("--stop-after", choices=sorted(STOP_AFTER_CHOICES), default="plan_graph")
    parser.add_argument("--allow-existing-authority", action="store_true", help="Allow planning even if final-status artifacts already exist")
    args = parser.parse_args(argv)

    try:
        run_dir = resolve_run_dir(args.run, args.run_id)
        summary = run_roadmap_planner(
            run_dir,
            stop_after=args.stop_after,
            allow_existing_authority=args.allow_existing_authority,
        )
    except Exception as exc:
        print(f"ROADMAP_PLANNER_FAILED: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("status") != "NEED_USER_STRATEGY" else 1


if __name__ == "__main__":
    sys.exit(main())
