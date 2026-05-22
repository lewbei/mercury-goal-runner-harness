#!/usr/bin/env python3
"""Run the deterministic v1.5 drift-aware proof path."""
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
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_tool(args: list[str], allow_failure: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0 and not allow_failure:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}"
        )
    return result


def run_drift_proof(run_id: str) -> dict:
    run_dir = RUN_ROOT / run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run folder missing: {run_dir}")
    if not (run_dir / "goal_contract.json").is_file():
        raise FileNotFoundError(f"goal_contract.json missing: {run_dir / 'goal_contract.json'}")

    proof = {
        "run_id": run_id,
        "generated_by": "drift-proof-runner-v1.5",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "invariant": "Drift reports can block; certifier decides.",
        "steps": [],
    }

    for args, label in [
        ([".agentic-pi/runtime/task_type_router.py", str(run_dir)], "task type routed"),
        ([".agentic-pi/runtime/domain_pack_selector.py", str(run_dir)], "domain pack selected"),
        ([".agentic-pi/runtime/capability_inventory.py", str(run_dir)], "capability inventory written"),
        ([".agentic-pi/runtime/strategy_generator.py", str(run_dir)], "strategy candidates generated"),
        ([".agentic-pi/runtime/strategy_applicability_gate.py", str(run_dir)], "strategy applicability gated"),
        ([".agentic-pi/runtime/experience_retriever.py", str(run_dir)], "advisory experience retrieved"),
        ([".agentic-pi/runtime/strategy_scorer.py", str(run_dir)], "strategy scores recorded"),
    ]:
        run_tool(args)
        proof["steps"].append(label)

    selector_result = run_tool([".agentic-pi/runtime/strategy_selector.py", str(run_dir)], allow_failure=True)
    decision = load_json(run_dir / "strategy_decision.json")
    proof["steps"].append("strategy selector completed")
    proof["decision_status"] = decision["decision_status"]
    if decision["decision_status"] != "SELECTED":
        proof["final_status"] = decision["decision_status"]
        proof["final_status_source"] = "strategy_decision.json"
        proof["selector_stdout"] = selector_result.stdout
        write_json(run_dir / "drift_proof.json", proof)
        return proof

    for args, label in [
        ([".agentic-pi/runtime/milestone_builder.py", str(run_dir)], "milestone_plan.json built"),
        ([".agentic-pi/runtime/milestone_tracker.py", str(run_dir)], "milestone_status.json recorded"),
        ([".agentic-pi/runtime/local_step_planner.py", str(run_dir)], "local_step_plan.json built"),
        ([".agentic-pi/runtime/step_compiler.py", str(run_dir)], "local steps compiled into merged_plan.json"),
        ([".agentic-pi/runtime/plan_graph_builder.py", run_id], "plan_graph.json built"),
        ([".agentic-pi/runtime/guarded_worker.py", "--run-id", run_id], "guarded worker executed milestone-derived plan"),
        ([".agentic-pi/runtime/checkpoint_writer.py", str(run_dir)], "checkpoints written"),
        ([".agentic-pi/runtime/plan_monitor.py", str(run_dir)], "plan monitor report written"),
        ([".agentic-pi/runtime/drift_detector.py", str(run_dir)], "drift report written"),
        ([".agentic-pi/runtime/replan_controller.py", str(run_dir)], "delta plan decision written"),
        ([".agentic-pi/validators/validate_delta_plan.py", str(run_dir)], "delta plan validated"),
    ]:
        run_tool(args)
        proof["steps"].append(label)

    drift = load_json(run_dir / "drift_report.json")
    proof["drift_level"] = drift["drift_level"]

    if drift.get("blocking") is True:
        proof["final_status"] = drift["recommended_action"]
        proof["final_status_source"] = "drift_report.json"
        write_json(run_dir / "drift_proof.json", proof)
        return proof

    for args, label in [
        ([".agentic-pi/runtime/artifact_linker.py", run_id], "artifact_registry.json built"),
        ([".agentic-pi/runtime/task_graph_builder.py", run_id], "task_graph.json built"),
        ([".agentic-pi/validators/validator_factory.py", str(run_dir)], "verifier quality certification recorded"),
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

    write_json(run_dir / "drift_proof.json", proof)
    return proof


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic drift proof: milestones -> checkpoints -> drift -> certifier."
    )
    parser.add_argument("run_id")
    args = parser.parse_args(argv)
    try:
        proof = run_drift_proof(args.run_id)
    except Exception as exc:
        print(f"DRIFT_PROOF_FAILED: {exc}")
        return 1
    print(json.dumps(proof, indent=2, ensure_ascii=False))
    return 0 if proof.get("final_status") not in {"NEED_USER_STRATEGY", "generate_delta_plan", "abort_requires_user"} else 1


if __name__ == "__main__":
    sys.exit(main())
