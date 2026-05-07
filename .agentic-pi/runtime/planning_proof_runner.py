#!/usr/bin/env python3
"""Run the deterministic v1.2 planning proof path.

This is proof glue, not an autonomous planner. It wires the existing branch
candidate selector into merged_plan.json, then lets the normal worker and
certifier path decide final status.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / ".agentic-runs"
STATUS_FILES = {"final_status.md", "certification.json", "policy_decision.json"}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_tool(args: list[str]) -> str:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}"
        )
    return result.stdout


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute path is not allowed: {raw_path}")
    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {raw_path}")
    return resolved


def run_relative(run_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(run_dir.resolve()).as_posix()


def status_artifacts_absent(run_dir: Path) -> bool:
    return not any((run_dir / name).exists() for name in STATUS_FILES)


def candidate_for_decision(run_dir: Path, decision: dict) -> tuple[dict, str]:
    selected_branch = decision.get("selected_branch")
    if not selected_branch:
        raise RuntimeError("branch_decision.json has no selected_branch")

    manifest = load_json(run_dir / "branch_manifest.json")
    for row in manifest.get("branches", []):
        if row.get("branch_id") != selected_branch:
            continue
        rel_path = row.get("branch_candidate_path", "")
        candidate_path = resolve_run_path(run_dir, rel_path)
        if not candidate_path.is_file():
            raise FileNotFoundError(f"selected branch candidate missing: {rel_path}")
        return load_json(candidate_path), run_relative(run_dir, candidate_path)

    raise RuntimeError(f"selected branch not found in branch_manifest.json: {selected_branch}")


def first_planned_artifact(run_dir: Path, candidate: dict) -> dict:
    registry_rel = candidate.get("artifact_registry_path", "")
    registry_path = resolve_run_path(run_dir, registry_rel)
    registry = load_json(registry_path)
    artifacts = registry.get("artifacts", [])
    if not artifacts:
        raise RuntimeError(f"selected branch artifact registry is empty: {registry_rel}")
    artifact = artifacts[0]
    artifact_id = artifact.get("artifact_id")
    artifact_path = artifact.get("path")
    if not isinstance(artifact_id, str) or not artifact_id:
        raise RuntimeError("selected branch artifact missing artifact_id")
    if not isinstance(artifact_path, str) or not artifact_path:
        raise RuntimeError("selected branch artifact missing path")
    resolve_run_path(run_dir, artifact_path)
    return {"artifact_id": artifact_id, "path": artifact_path}


def materialize_selected_branch(run_dir: Path, decision: dict) -> dict:
    goal = load_json(run_dir / "goal_contract.json")
    candidate, candidate_path = candidate_for_decision(run_dir, decision)
    branch_artifact = first_planned_artifact(run_dir, candidate)
    final_outputs = goal.get("final_outputs", [])
    if not final_outputs:
        raise RuntimeError("goal_contract.json final_outputs is empty")
    final_output = final_outputs[0]
    resolve_run_path(run_dir, final_output)

    selected_branch = decision["selected_branch"]
    branch_task_id = "T.SELECTED_BRANCH_ARTIFACT"
    final_task_id = "T.SELECTED_BRANCH_FINAL_OUTPUT"

    merged_plan = {
        "planner": "planning-proof-runner-v1.2",
        "selected_branch": selected_branch,
        "branch_candidate_path": candidate_path,
        "selection_reason": decision.get("reason", ""),
        "steps": [
            {
                "task_id": branch_task_id,
                "action": "create_file",
                "path": branch_artifact["path"],
                "content": (
                    f"Selected branch {selected_branch} produced artifact "
                    f"{branch_artifact['artifact_id']}.\n"
                ),
                "requires": [],
                "produces": [
                    {
                        "artifact_id": branch_artifact["artifact_id"],
                        "path": branch_artifact["path"],
                    }
                ],
            },
            {
                "task_id": final_task_id,
                "action": "create_file",
                "path": final_output,
                "content": (
                    "# Harness Planning Proof\n\n"
                    f"Selected branch: {selected_branch}\n\n"
                    f"Consumed exact artifact ID: {branch_artifact['artifact_id']}\n\n"
                    "The harness still requires verifier provenance before final certification.\n"
                ),
                "requires": [branch_artifact["artifact_id"]],
                "produces": [
                    {
                        "artifact_id": "A.FINAL_OUTPUT",
                        "path": final_output,
                    }
                ],
            },
        ],
    }
    write_json(run_dir / "merged_plan.json", merged_plan)
    return merged_plan


def run_planning_proof(run_id: str) -> dict:
    run_dir = RUN_ROOT / run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run folder missing: {run_dir}")
    if not (run_dir / "goal_contract.json").is_file():
        raise FileNotFoundError(f"goal_contract.json missing: {run_dir / 'goal_contract.json'}")

    proof = {
        "run_id": run_id,
        "generated_by": "planning-proof-runner-v1.2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "invariant": "Planner selects; certifier decides.",
        "steps": [],
    }

    run_tool([".agentic-pi/runtime/branch_generator.py", str(run_dir)])
    proof["steps"].append("branch candidates generated")

    run_tool([".agentic-pi/runtime/branch_generator.py", str(run_dir), "--validate"])
    proof["steps"].append("branch set validated")

    run_tool([".agentic-pi/runtime/evidence_branch_selector.py", str(run_dir)])
    decision = load_json(run_dir / "branch_decision.json")
    if decision.get("decision_status") != "SELECTED":
        raise RuntimeError(f"branch selector did not select a branch: {decision}")
    proof["steps"].append("branch selected by verifier-provenance evidence path")
    proof["selected_branch"] = decision["selected_branch"]
    proof["selector_status_artifacts_absent"] = status_artifacts_absent(run_dir)

    merged_plan = materialize_selected_branch(run_dir, decision)
    proof["steps"].append("selected branch materialized into merged_plan.json")
    proof["merged_plan_step_count"] = len(merged_plan["steps"])
    proof["merged_plan_selected_branch"] = merged_plan["selected_branch"]

    for args, label in [
        ([".agentic-pi/runtime/plan_graph_builder.py", run_id], "plan_graph.json built"),
        ([".agentic-pi/runtime/guarded_worker.py", "--run-id", run_id], "guarded worker executed selected plan"),
        ([".agentic-pi/runtime/artifact_linker.py", run_id], "artifact_registry.json built"),
        ([".agentic-pi/runtime/task_graph_builder.py", run_id], "task_graph.json built"),
        ([".agentic-pi/validators/certify_run.py", str(run_dir)], "certifier decided final status"),
    ]:
        run_tool(args)
        proof["steps"].append(label)

    certification = load_json(run_dir / "certification.json")
    proof["final_status"] = certification.get("status", "")
    proof["final_status_source"] = "certification.json"
    if (run_dir / "policy_decision.json").is_file():
        proof["policy_status"] = load_json(run_dir / "policy_decision.json").get("status", "")
    else:
        proof["policy_status"] = "SKIPPED_LEGACY"

    write_json(run_dir / "planning_proof.json", proof)
    return proof


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic planning proof: branches -> selected branch -> merged_plan -> certifier."
    )
    parser.add_argument("run_id")
    args = parser.parse_args(argv)

    try:
        proof = run_planning_proof(args.run_id)
    except Exception as exc:
        print(f"PLANNING_PROOF_FAILED: {exc}")
        return 1

    print(json.dumps(proof, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
