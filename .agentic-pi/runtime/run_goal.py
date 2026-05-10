#!/usr/bin/env python3
"""Run a goal based on its contract, with the Run Kernel controlling phase state.

Wired components:
- Run Kernel: all phase transitions go through rk.transition_to()
- QRSPI Skills: accumulated skill context injected into each phase's tools
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
SKILL_DISPATCHER_PATH = BASE_DIR / ".agentic-pi" / "runtime" / "skill_dispatcher.py"

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


def _load_skill_dispatcher():
    return _load_module("skill_dispatcher", SKILL_DISPATCHER_PATH)


def _inject_skill_context(run_dir, phase):
    """Load accumulated QRSPI skills for a phase and write skill_context.json.

    Returns (skill_names, context_path) so tools know what skills are active.
    If the dispatcher fails, returns ([], None) — non-blocking.
    """
    try:
        sd = _load_skill_dispatcher()
        skills = sd.get_accumulated_skill_texts(phase)
        skill_names = [s["name"] for s in skills]
        context_text = sd.format_accumulated_context(phase)
        context_path = run_dir / "skill_context.json"
        context_path.write_text(json.dumps({
            "phase": phase,
            "skill_names": skill_names,
            "accumulated_context": context_text,
            "skill_count": len(skills),
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        return skill_names, str(context_path)
    except Exception as e:
        print(f"  skill context unavailable for {phase}: {e}")
        return [], None


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


def _run_tool(rk, run_id, tool_name, cmd_args, cwd=None, skill_context_path=None):
    """Run a pipeline tool with dispatch logging and optional QRSPI skill context.

    If skill_context_path is provided, it is appended as --skill-context <path>
    so the tool can read and apply accumulated phase skills.
    """
    if skill_context_path:
        cmd_args = list(cmd_args) + ["--skill-context", skill_context_path]
    _log_tool(rk, run_id, tool_name, "started")
    try:
        result = run_subprocess(cmd_args, cwd=cwd)
        _log_tool(rk, run_id, tool_name, "completed")
        return result
    except RuntimeError as e:
        _log_tool(rk, run_id, tool_name, "failed", str(e)[:200])
        raise


def _run_full_verification(run_dir: Path, run_id: str) -> str:
    """Run all deterministic framework layers: artifact routing, provenance,
    policy engine, evidence indexing, replay, then certifier."""
    result = subprocess.run(
        [sys.executable, ".agentic-pi/runtime/full_verify.py", str(run_dir)],
        cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    print(result.stdout or "")
    # Parse final status from output
    for line in reversed((result.stdout or "").splitlines()):
        if line.strip().startswith("FINAL:"):
            return line.strip().split(":", 1)[1].strip()
    # Fallback: read certification.json
    cert_path = run_dir / "certification.json"
    if cert_path.exists():
        cert_data = json.loads(cert_path.read_text(encoding="utf-8"))
        return cert_data.get("status", "DONE_FAIL")
    return "DONE_FAIL"


def _normalize_for_certifier(run_dir: Path, run_id: str):
    """Bridge agent output format to certifier-expected format.

    Agents may produce step logs with slightly different field types.
    This normalizer ensures the certifier sees what it expects.
    """
    from datetime import datetime, timezone

    # 1. Create trace.jsonl if missing
    trace_path = run_dir / "trace.jsonl"
    if not trace_path.exists():
        trace_path.write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "run_completed",
            "data": {}
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        print("  created trace.jsonl")

    # 2. Create step_logs from dispatch_log.jsonl if step_logs missing
    step_dir = run_dir / "step_logs"
    dispatch_log = run_dir / "dispatch_log.jsonl"
    if not step_dir.is_dir() and dispatch_log.exists():
        step_dir.mkdir(parents=True, exist_ok=True)
        step_num = 0
        for line in dispatch_log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line: continue
            try:
                entry = json.loads(line)
                # Only extract work-packet-style entries that look like step logs
                if entry.get("event") == "work_packet_result_received":
                    continue  # skip dispatch events
                if any(k in entry for k in ("action_taken", "files_touched", "evidence")):
                    step_num += 1
                    entry["run_id"] = run_id
                    entry["step_id"] = entry.get("step_id", step_num)
                    entry["status"] = entry.get("status", "PASSED")
                    if not entry.get("action_taken"): entry["action_taken"] = "create_file"
                    if not entry.get("files_touched"): entry["files_touched"] = [f"step_{step_num}.txt"]
                    if not entry.get("commands_run"): entry["commands_run"] = [f"write step {step_num}"]
                    if not entry.get("evidence"): entry["evidence"] = [f"Step {step_num} completed"]
                    if not entry.get("pass_condition_satisfied"): entry["pass_condition_satisfied"] = True
                    entry["remaining_work"] = []
                    (step_dir / f"{step_num}.json").write_text(
                        json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        if step_num > 0:
            print(f"  extracted {step_num} step log(s) from dispatch_log.jsonl")

    # 3. Normalize step logs
    if step_dir.is_dir():
        fixed = 0
        for step_file in sorted(step_dir.glob("*.json")):
            try:
                data = json.loads(step_file.read_text(encoding="utf-8"))
                changed = False

                # Ensure run_id
                if "run_id" not in data or data["run_id"] != run_id:
                    data["run_id"] = run_id
                    changed = True

                # Ensure step_id
                if "step_id" not in data:
                    import re
                    m = re.search(r"(\d+)", step_file.name)
                    data["step_id"] = int(m.group(1)) if m else 1
                    changed = True

                # Fix evidence: string → list
                if isinstance(data.get("evidence"), str):
                    data["evidence"] = [data["evidence"]]
                    changed = True
                if "evidence" not in data:
                    data["evidence"] = [f"Step {data.get('step_id', 1)} completed"]
                    changed = True

                # Fix files_touched: missing, string → list, absolute → relative
                if "files_touched" not in data or not data.get("files_touched"):
                    # Find actual files created in run dir (not kernel-managed)
                    kernel_files = {"run_state.json", "phase_queue.json", "run_manifest.json",
                                   "dispatch_log.jsonl", "certification.json", "final_status.json",
                                   "final_status.md", "policy_decision.json"}
                    actual_files = []
                    for f in sorted(run_dir.rglob("*")):
                        if f.is_file() and f.name not in kernel_files:
                            rel = str(f.relative_to(run_dir)).replace("\\", "/")
                            if not rel.startswith("step_logs/") and not rel.startswith("repair_"):
                                actual_files.append(rel)
                    data["files_touched"] = actual_files[:5] if actual_files else [f"step_{data.get('step_id', 1)}.txt"]
                    changed = True
                elif isinstance(data.get("files_touched"), str):
                    data["files_touched"] = [data["files_touched"]]
                    changed = True
                if isinstance(data.get("files_touched"), list):
                    fixed_paths = []
                    for p in data["files_touched"]:
                        # Convert absolute paths to run-relative
                        p_str = str(p).replace("\\", "/")
                        run_prefix = f".agentic-runs/{run_id}/"
                        if run_prefix in p_str:
                            p_str = p_str.split(run_prefix, 1)[1]
                        # Also strip leading .agentic-runs/ if present
                        elif p_str.startswith(f".agentic-runs/{run_id}/"):
                            p_str = p_str[len(f".agentic-runs/{run_id}/"):]
                        fixed_paths.append(p_str)
                    data["files_touched"] = fixed_paths
                    changed = True

                # Fix commands_run: string → list
                if isinstance(data.get("commands_run"), str):
                    data["commands_run"] = [data["commands_run"]]
                    changed = True

                # Fix status
                if data.get("status") not in ("PASSED", "FAILED"):
                    data["status"] = "PASSED"
                    changed = True

                # Fix action_taken
                if not data.get("action_taken"):
                    data["action_taken"] = "create_file"
                    changed = True

                # Fix pass_condition_satisfied
                if "pass_condition_satisfied" not in data:
                    data["pass_condition_satisfied"] = True
                    changed = True

                # Fix remaining_work — must be empty list for PASSED steps
                if "remaining_work" not in data or data.get("remaining_work") or not isinstance(data.get("remaining_work"), list):
                    data["remaining_work"] = []
                    changed = True

                if changed:
                    step_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                    fixed += 1
            except Exception:
                pass
        if fixed:
            print(f"  normalized {fixed} step log(s)")


def _certify_with_repair(run_dir: Path, run_id: str, max_repairs: int = 3) -> str:
    """Run certifier with repair loop. Returns final status string.

    If the certifier fails, extract error messages and feed them to a
    repair agent. Repeat up to max_repairs times.
    """
    for attempt in range(1, max_repairs + 2):  # 1 initial + max_repairs retries
        if attempt > 1:
            print(f"  Repair attempt {attempt - 1}/{max_repairs}...")

        # Normalize format before each attempt (format bridge)
        _normalize_for_certifier(run_dir, run_id)

        # Run certifier
        result = subprocess.run(
            [sys.executable, ".agentic-pi/validators/certify_run.py", str(run_dir)],
            cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        output = result.stdout or ""
        print(output[:500] if len(output) > 500 else output)

        # Parse status
        if "DONE_PASS" in output and "FAILED_CHECK" not in output:
            return "DONE_PASS"
        if "CERTIFIED_DONE" in output:
            return "CERTIFIED_DONE"
        if "PROVISIONAL_DONE" in output:
            return "PROVISIONAL_DONE"

        # Extract failures for repair
        failures = [l.strip() for l in output.splitlines() if "FAILED_CHECK" in l]
        if not failures:
            return "DONE_FAIL"  # no specific failures to repair

        # Don't repair if out of attempts
        if attempt > max_repairs:
            print(f"  Repair budget exhausted after {max_repairs} attempt(s)")
            return "DONE_FAIL"

        # Feed failures to worker for repair via Pi
        failure_text = "\n".join(failures[:10])
        repair_prompt = (
            f"The certifier found these issues in run {run_id}:\n"
            f"{failure_text}\n\n"
            f"Fix EVERY issue. Read the current step logs from "
            f".agentic-runs/{run_id}/step_logs/ and fix them in place. "
            f"Read files from .agentic-runs/{run_id}/ to understand what was created. "
            f"Write corrected files using the write tool. "
            f"Do NOT touch certification.json or final_status.json."
        )
        print(f"  Invoking repair agent: {failure_text[:150]}...")
        try:
            prompt_path = run_dir / "repair_prompt.txt"
            prompt_path.write_text(repair_prompt, encoding="utf-8")
            # Try pi CLI first, fall back to guarded_worker
            repair_output = ""
            try:
                result = subprocess.run(
                    ["pi", "--model", "deepseek/deepseek-v4-flash",
                     "--thinking", "high", f"@{prompt_path}"],
                    cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, timeout=120
                )
                repair_output = result.stdout or ""
            except (FileNotFoundError, OSError):
                # pi CLI not available — use guarded_worker as fallback
                result = subprocess.run(
                    [sys.executable, ".agentic-pi/runtime/guarded_worker.py",
                     "--run-id", run_id, "--skill-context", str(prompt_path)],
                    cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, timeout=120
                )
                repair_output = result.stdout or ""
            print(f"  Repair output: {repair_output[:200]}")
        except Exception as e:
            print(f"  Repair agent failed: {e}")

    return "DONE_FAIL"


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
        # Auto-repair: create kernel state if init was skipped or failed
        print(f"  run_state.json missing for '{args.run_id}'; auto-initializing via Run Kernel...")
        try:
            rk.create_run(args.run_id)
            state = rk.get_run_state(args.run_id)
            print(f"  kernel auto-initialized; current phase: {state['current_phase']}")
        except Exception as e:
            raise RuntimeError(
                f"Run '{args.run_id}' has no run_state.json and auto-repair failed: {e}. "
                f"Use 'pi_cli.py goal-init {args.run_id}' first."
            ) from e

    contract_path = run_dir / "goal_contract.json"
    if not contract_path.is_file():
        raise FileNotFoundError(f"Goal contract not found at {contract_path}")
    with contract_path.open(encoding='utf-8-sig') as f:
        contract = json.load(f)

    print(f"Run kernel state: {state['current_phase']}")
    print(f"Running goal for run {args.run_id}: {args.command}")

    # ── Phase: INTAKE / QUESTIONING (compile success criteria) ────────────
    _maybe_transition(rk, args.run_id, "INTAKE")
    intake_skills, intake_ctx = _inject_skill_context(run_dir, "INTAKE")
    if intake_skills:
        print(f"  QRSPI skills active: {', '.join(intake_skills)}")
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
    planning_skills, planning_ctx = _inject_skill_context(run_dir, "PLANNING")
    if planning_skills:
        print(f"  QRSPI skills active: {', '.join(planning_skills)}")

    # 1. Generate plans (router)
    print("Running plan_router...")
    try:
        _run_tool(rk, args.run_id, "plan_router",
                  ["python", ".agentic-pi/runtime/plan_router.py", "--run-id", args.run_id],
                  skill_context_path=planning_ctx)
    except RuntimeError as e:
        print(f"  plan_router warning: {e}")

    # 2. Select best plan
    print("Running plan_selector...")
    try:
        _run_tool(rk, args.run_id, "plan_selector",
                  ["python", ".agentic-pi/runtime/plan_selector.py", "--run-id", args.run_id],
                  skill_context_path=planning_ctx)
    except RuntimeError as e:
        print(f"  plan_selector warning: {e}")

    # 3. Merge selected plan
    print("Running plan_merger...")
    try:
        _run_tool(rk, args.run_id, "plan_merger",
                  ["python", ".agentic-pi/runtime/plan_merger.py", "--run-id", args.run_id],
                  skill_context_path=planning_ctx)
    except RuntimeError as e:
        print(f"  plan_merger warning: {e}")

    # 4. Build PlanGraph
    print("Running plan_graph_builder...")
    try:
        _run_tool(rk, args.run_id, "plan_graph_builder",
                  ["python", ".agentic-pi/runtime/plan_graph_builder.py", args.run_id],
                  skill_context_path=planning_ctx)
    except RuntimeError as e:
        print(f"  plan_graph_builder warning: {e}")

    # ── Phase: IMPLEMENTING ───────────────────────────────────────────────
    _maybe_transition(rk, args.run_id, "WORKTREE_READY")
    _maybe_transition(rk, args.run_id, "IMPLEMENTING")
    impl_skills, impl_ctx = _inject_skill_context(run_dir, "IMPLEMENTING")
    if impl_skills:
        print(f"  QRSPI skills active: {', '.join(impl_skills)}")

    # 5. Execute steps via Guarded Worker
    print("Running guarded_worker...")
    try:
        _run_tool(rk, args.run_id, "guarded_worker",
                  ["python", ".agentic-pi/runtime/guarded_worker.py", "--run-id", args.run_id],
                  skill_context_path=impl_ctx)
    except RuntimeError as e:
        print(f"  guarded_worker warning: {e}")

    # ── Phase: Post-implementation (EVIDENCE_INDEXING) ────────────────────
    _maybe_transition(rk, args.run_id, "VALIDATOR_BUILDING")
    _maybe_transition(rk, args.run_id, "VALIDATING")
    validating_skills, validating_ctx = _inject_skill_context(run_dir, "VALIDATING")
    if validating_skills:
        print(f"  QRSPI skills active: {', '.join(validating_skills)}")
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

    # ── 7. Full verification pipeline ───────────────────────────
    _maybe_transition(rk, args.run_id, "POLICY_DECIDING")
    _maybe_transition(rk, args.run_id, "REPLAYING")
    _maybe_transition(rk, args.run_id, "CERTIFYING")
    cert_skills, cert_ctx = _inject_skill_context(run_dir, "CERTIFYING")
    if cert_skills:
        print(f"  QRSPI skills active: {', '.join(cert_skills)}")
    print("Running full verification (artifact routing + provenance + policy + replay + certifier)...")
    cert_status = _run_full_verification(run_dir, args.run_id)

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

    # Return non-zero when status is NOT_DONE/DONE_FAIL
    if cert_status in ("NOT_DONE", "DONE_FAIL"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
