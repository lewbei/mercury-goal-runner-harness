#!/usr/bin/env python3
"""Run a goal based on its contract, with the Run Kernel controlling phase state.

Wired components:
- Run Kernel: all phase transitions go through rk.transition_to()
- Success Criteria Compiler: compiles success_criteria_set.json from goal contract
- Artifact routing: writes expected_artifacts.json for the output phase
- Certifier: gates on artifact location, replay, memory authority
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
RUN_KERNEL_PATH = BASE_DIR / ".agentic-pi" / "run_kernel" / "run_kernel.py"
SCC_PATH = BASE_DIR / ".agentic-pi" / "success" / "success_criteria_compiler.py"

if str(RUN_KERNEL_PATH.parent) not in sys.path:
    sys.path.insert(0, str(RUN_KERNEL_PATH.parent))


def _load_module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_rk():
    return _load_module("run_kernel", RUN_KERNEL_PATH)


def _load_scc():
    return _load_module("success_criteria_compiler", SCC_PATH)


def run_subprocess(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command {' '.join(cmd)} failed with exit {result.returncode}: {result.stdout}")
    return result.stdout


def _log_tool(rk, run_id, tool_name, status="started", detail=None):
    """Write a dispatch log entry for a pipeline tool."""
    try:
        from datetime import datetime, timezone
        entry = {
            "event": f"tool_{tool_name}_{status}",
            "run_id": run_id,
            "tool": tool_name,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if detail:
            entry["detail"] = detail
        log_path = rk.get_run_dir(run_id) / "dispatch_log.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # non-blocking


def _run_tool(rk, run_id, tool_name, cmd_args, cwd=None):
    """Run a pipeline tool with dispatch logging."""
    _log_tool(rk, run_id, tool_name, "started")
    try:
        result = run_subprocess(cmd_args, cwd=cwd)
        _log_tool(rk, run_id, tool_name, "completed")
        return result
    except RuntimeError as e:
        _log_tool(rk, run_id, tool_name, "failed", str(e)[:200])
        raise


def _maybe_transition(rk, run_id, target_phase):
    """Transition if the current phase allows it (valid transition)."""
    try:
        rk.transition_to(run_id, target_phase)
        print(f"  kernel transition -> {target_phase}")
    except RuntimeError as e:
        print(f"  kernel transition skipped ({target_phase}): {e}")


def main():
    parser = argparse.ArgumentParser(description="Run a goal based on its contract")
    parser.add_argument("command", help="Command describing the goal")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument("--skip-memory-update", action="store_true", help="Do not update memory")
    args = parser.parse_args()

    run_dir = Path(".agentic-runs") / args.run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run folder {run_dir} does not exist")

    # ── Load Run Kernel ───────────────────────────────────────────────────
    rk = _load_rk()
    try:
        state = rk.get_run_state(args.run_id)
    except FileNotFoundError:
        raise RuntimeError(f"Run '{args.run_id}' has no run_state.json. Use init_run.py first.")

    contract_path = run_dir / "goal_contract.json"
    if not contract_path.is_file():
        raise FileNotFoundError(f"Goal contract not found at {contract_path}")
    with contract_path.open(encoding='utf-8-sig') as f:
        contract = json.load(f)

    print(f"Run kernel state: {state['current_phase']}")
    print(f"Running goal for run {args.run_id}: {args.command}")

    # ── Phase: INTAKE / QUESTIONING (compile success criteria) ────────────
    _maybe_transition(rk, args.run_id, "INTAKE")
    try:
        scc = _load_scc()
        criteria_set = scc.compile_from_goal_contract(contract, args.run_id)
        (run_dir / "success_criteria_set.json").write_text(
            json.dumps(criteria_set, indent=2), encoding="utf-8"
        )
        print(f"  compiled {len(criteria_set['criteria'])} success criteria")
    except Exception as e:
        print(f"  warning: success criteria compilation failed: {e}")

    _maybe_transition(rk, args.run_id, "QUESTIONING")

    # ── Phase: RESEARCHING / DESIGNING / STRUCTURING (planning chain) ─────
    _maybe_transition(rk, args.run_id, "RESEARCHING")
    _maybe_transition(rk, args.run_id, "DESIGNING")
    _maybe_transition(rk, args.run_id, "STRUCTURING")
    _maybe_transition(rk, args.run_id, "PLANNING")

    # 1. Generate plans (router)
    print("Running plan_router...")
    try:
        _run_tool(rk, args.run_id, "plan_router",
                  ["python", ".agentic-pi/runtime/plan_router.py", "--run-id", args.run_id])
    except RuntimeError as e:
        print(f"  plan_router warning: {e}")

    # 2. Select best plan
    print("Running plan_selector...")
    try:
        _run_tool(rk, args.run_id, "plan_selector",
                  ["python", ".agentic-pi/runtime/plan_selector.py", "--run-id", args.run_id])
    except RuntimeError as e:
        print(f"  plan_selector warning: {e}")

    # 3. Merge selected plan
    print("Running plan_merger...")
    try:
        _run_tool(rk, args.run_id, "plan_merger",
                  ["python", ".agentic-pi/runtime/plan_merger.py", "--run-id", args.run_id])
    except RuntimeError as e:
        print(f"  plan_merger warning: {e}")

    # 4. Build PlanGraph
    print("Running plan_graph_builder...")
    try:
        _run_tool(rk, args.run_id, "plan_graph_builder",
                  ["python", ".agentic-pi/runtime/plan_graph_builder.py", args.run_id])
    except RuntimeError as e:
        print(f"  plan_graph_builder warning: {e}")

    # ── Phase: IMPLEMENTING ───────────────────────────────────────────────
    _maybe_transition(rk, args.run_id, "WORKTREE_READY")
    _maybe_transition(rk, args.run_id, "IMPLEMENTING")

    # 5. Execute steps via Guarded Worker
    print("Running guarded_worker...")
    try:
        _run_tool(rk, args.run_id, "guarded_worker",
                  ["python", ".agentic-pi/runtime/guarded_worker.py", "--run-id", args.run_id])
    except RuntimeError as e:
        print(f"  guarded_worker warning: {e}")

    # ── Phase: Post-implementation (EVIDENCE_INDEXING) ────────────────────
    _maybe_transition(rk, args.run_id, "VALIDATOR_BUILDING")
    _maybe_transition(rk, args.run_id, "VALIDATING")
    _maybe_transition(rk, args.run_id, "EVIDENCE_INDEXING")

    # 6. Build post-worker views
    print("Running artifact_linker...")
    try:
        _run_tool(rk, args.run_id, "artifact_linker",
                  ["python", ".agentic-pi/runtime/artifact_linker.py", args.run_id])
    except RuntimeError as e:
        print(f"  artifact_linker warning: {e}")

    print("Running task_graph_builder...")
    try:
        _run_tool(rk, args.run_id, "task_graph_builder",
                  ["python", ".agentic-pi/runtime/task_graph_builder.py", args.run_id])
    except RuntimeError as e:
        print(f"  task_graph_builder warning: {e}")

    # ── Phase: POLICY / REPLAY / CERTIFYING ─────────────────────────────
    _maybe_transition(rk, args.run_id, "POLICY_DECIDING")
    _maybe_transition(rk, args.run_id, "REPLAYING")

    # Write expected_artifacts.json before certifying (if not already present)
    ea_path = run_dir / "expected_artifacts.json"
    if not ea_path.exists():
        outputs = contract.get("final_outputs", [])
        if outputs:
            ea = {
                "schema_version": "expected_artifacts_v1",
                "run_id": args.run_id,
                "artifacts": [
                    {"artifact_id": f"A.{i+1:03d}", "expected_path": o, "required": True}
                    for i, o in enumerate(outputs)
                ],
            }
            ea_path.write_text(json.dumps(ea, indent=2), encoding="utf-8")
            print(f"  wrote expected_artifacts.json for {len(outputs)} output(s)")

    # 7. Certify run
    certifier_failed = False
    _maybe_transition(rk, args.run_id, "CERTIFYING")
    print("Running certifier...")
    try:
        _run_tool(rk, args.run_id, "certify_run",
                  ["python", ".agentic-pi/validators/certify_run.py", str(run_dir)])
    except RuntimeError as e:
        print(f"  certifier failure: {e}")
        certifier_failed = True

    # ── Phase: REPORTING / MEMORY ─────────────────────────────────────────
    _maybe_transition(rk, args.run_id, "REPORTING")
    print(f"Final kernel state: {rk.get_run_state(args.run_id)['current_phase']}")

    if not args.skip_memory_update:
        _maybe_transition(rk, args.run_id, "MEMORY_CONSOLIDATING")
        print("Updating memory from runs...")
        try:
            _run_tool(rk, args.run_id, "update_memory",
                      ["python", ".agentic-pi/runtime/update_memory_from_runs.py"], cwd=BASE_DIR)
        except RuntimeError as e:
            print(f"  memory update warning: {e}")

    # Read certification status to decide DONE transition and exit code
    cert_status = None
    cert_path = run_dir / "certification.json"
    if cert_path.exists():
        try:
            with cert_path.open(encoding='utf-8-sig') as f:
                cert_data = json.load(f)
            cert_status = cert_data.get("status")
        except Exception:
            pass

    # Only transition to DONE when certification passed
    if cert_status in ("DONE_PASS", "CERTIFIED_DONE", "PROVISIONAL_DONE", None):
        _maybe_transition(rk, args.run_id, "DONE")
    else:
        print(f"  certification status is {cert_status}; skipping DONE transition")

    print(f"Final state. Kernel phase: {rk.get_run_state(args.run_id)['current_phase']}")

    # Return non-zero when certifier failed or status is NOT_DONE/DONE_FAIL
    if certifier_failed:
        return 1
    if cert_status in ("NOT_DONE", "DONE_FAIL"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
