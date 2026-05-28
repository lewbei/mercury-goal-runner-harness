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


def _run_full_verification(run_dir: Path, run_id: str, *, skip_memory_consolidation: bool = False) -> str:
    """Run all deterministic framework layers: artifact routing, provenance,
    policy engine, evidence indexing, replay, then certifier."""
    command = [sys.executable, ".agentic-pi/runtime/full_verify.py", str(run_dir)]
    if skip_memory_consolidation:
        command.append("--skip-memory-consolidation")
    result = subprocess.run(
        command,
        cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    print(result.stdout or "")
    # Parse final status from this verification process. Do not promote stale
    # certification artifacts if the verifier failed before printing FINAL.
    for line in reversed((result.stdout or "").splitlines()):
        if line.strip().startswith("FINAL:"):
            return line.strip().split(":", 1)[1].strip()
    if result.returncode != 0:
        return "DONE_FAIL"
    cert_path = run_dir / "certification.json"
    if cert_path.exists():
        cert_data = json.loads(cert_path.read_text(encoding="utf-8"))
        return cert_data.get("status", "DONE_FAIL")
    return "DONE_FAIL"


def _run_direct_certifier(run_dir: Path) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, ".agentic-pi/validators/certify_run.py", str(run_dir)],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = result.stdout or ""
    print(output[:500] if len(output) > 500 else output)
    cert_path = run_dir / "certification.json"
    if cert_path.is_file():
        cert = json.loads(cert_path.read_text(encoding="utf-8-sig"))
        return result.returncode, cert.get("status", "DONE_FAIL")
    return result.returncode, "DONE_FAIL"


def _normalize_for_certifier(run_dir: Path, run_id: str):
    """Strictly validate certifier inputs without mutating run evidence.

    This compatibility helper used to create trace files, infer step logs, and
    fill missing fields. Strict mode forbids that behavior: missing or malformed
    evidence now fails before certifier execution.
    """
    errors = []

    trace_path = run_dir / "trace.jsonl"
    if not trace_path.is_file():
        errors.append("trace.jsonl is missing")

    step_dir = run_dir / "step_logs"
    if not step_dir.is_dir():
        errors.append("step_logs/ is missing")
    else:
        step_files = sorted(step_dir.glob("*.json"))
        if not step_files:
            errors.append("step_logs/ contains no JSON step logs")
        for step_file in step_files:
            try:
                data = json.loads(step_file.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"{step_file.name} is not valid JSON: {exc}")
                continue

            required_types = {
                "run_id": str,
                "step_id": int,
                "status": str,
                "action_taken": str,
                "files_touched": list,
                "commands_run": list,
                "evidence": list,
                "pass_condition_satisfied": bool,
                "remaining_work": list,
            }
            for field, expected_type in required_types.items():
                if field not in data:
                    errors.append(f"{step_file.name} missing {field}")
                elif not isinstance(data[field], expected_type):
                    errors.append(f"{step_file.name} field {field} has wrong type")

            if data.get("run_id") != run_id:
                errors.append(f"{step_file.name} run_id does not match {run_id}")
            if data.get("status") not in ("PASSED", "FAILED"):
                errors.append(f"{step_file.name} status must be PASSED or FAILED")
            for touched in data.get("files_touched", []):
                if not isinstance(touched, str) or not touched.strip():
                    errors.append(f"{step_file.name} files_touched contains invalid path")

    if errors:
        preview = "; ".join(errors[:10])
        if len(errors) > 10:
            preview += f"; ... {len(errors) - 10} more"
        raise RuntimeError(f"Strict certifier precheck failed: {preview}")


def _certify_with_repair(run_dir: Path, run_id: str, max_repairs: int = 3) -> str:
    """Compatibility wrapper around the certifier with strict no-repair behavior."""
    if max_repairs:
        print("  strict mode: automatic repair loop disabled; max_repairs ignored")

    _normalize_for_certifier(run_dir, run_id)

    result = subprocess.run(
        [sys.executable, ".agentic-pi/validators/certify_run.py", str(run_dir)],
        cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    output = result.stdout or ""
    print(output[:500] if len(output) > 500 else output)

    if "DONE_PASS" in output and "FAILED_CHECK" not in output:
        return "DONE_PASS"
    if "CERTIFIED_DONE" in output:
        return "CERTIFIED_DONE"
    if "PROVISIONAL_DONE" in output:
        return "PROVISIONAL_DONE"
    if result.returncode != 0:
        return "DONE_FAIL"
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
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Run '{args.run_id}' has no run_state.json. Strict prepared-run mode requires "
            f"explicit initialization first: python .agentic-pi/runtime/init_run.py --run-id {args.run_id}"
        ) from exc

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

    # Cross-run learning: update patterns from past runs and inject context
    try:
        from cross_run_learner import update_cross_run_patterns, pre_run_inject
        update_cross_run_patterns()
        cross_run_context = pre_run_inject(args.run_id)
        if cross_run_context:
            print(f"  cross-run context: {cross_run_context[:200]}")
            # Write to run dir for planning phase to consume
            (run_dir / "cross_run_context.txt").write_text(cross_run_context, encoding="utf-8")
    except Exception as e:
        print(f"  cross-run learning unavailable: {e}")

    _maybe_transition(rk, args.run_id, "DESIGNING")
    _maybe_transition(rk, args.run_id, "STRUCTURING")
    _maybe_transition(rk, args.run_id, "PLANNING")
    planning_skills, planning_ctx = _inject_skill_context(run_dir, "PLANNING")
    if planning_skills:
        print(f"  QRSPI skills active: {', '.join(planning_skills)}")

    # 1. Build strict run-folder planning artifacts. The legacy plan_router path
    # requires pre-existing plans/*_plan.json and intentionally does not create
    # substitute plans. roadmap_planner.py is the current strict prepared-run
    # planner: it writes adaptive_research_inputs.json,
    # planning_search_tree.json, planning_coverage.json, expected_artifacts.json,
    # selected_plan.json, merged_plan.json, and
    # plan_graph.json without executing workers or certifying DONE.
    print("Running roadmap_planner...")
    try:
        _run_tool(rk, args.run_id, "roadmap_planner",
                  ["python", ".agentic-pi/runtime/roadmap_planner.py", "--run-id", args.run_id])
    except RuntimeError as e:
        print(f"  roadmap_planner failed: {e}")
        return 1

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
        print(f"  guarded_worker failed: {e}")
        return 1

    # ── Phase: Post-implementation setup ─────────────────────────────────
    _maybe_transition(rk, args.run_id, "VALIDATOR_BUILDING")

    # 6. Build post-worker views
    print("Running artifact_linker...")
    try:
        _run_tool(rk, args.run_id, "artifact_linker",
                  ["python", ".agentic-pi/runtime/artifact_linker.py", args.run_id])
    except RuntimeError as e:
        print(f"  artifact_linker failed: {e}")
        return 1

    print("Running task_graph_builder...")
    try:
        _run_tool(rk, args.run_id, "task_graph_builder",
                  ["python", ".agentic-pi/runtime/task_graph_builder.py", args.run_id])
    except RuntimeError as e:
        print(f"  task_graph_builder failed: {e}")
        return 1

    provenance_mode = (run_dir / "verifier_contract.json").is_file()
    if provenance_mode:
        print("Running validator_factory...")
        try:
            _run_tool(rk, args.run_id, "validator_factory",
                      ["python", ".agentic-pi/validators/validator_factory.py", str(run_dir)])
        except RuntimeError as e:
            print(f"  validator_factory failed: {e}")
            print("Running certifier to write fail-closed status artifacts...")
            _, status = _run_direct_certifier(run_dir)
            return 0 if status in {"DONE_PASS", "CERTIFIED_DONE", "PROVISIONAL_DONE"} else 1
    else:
        print("Skipping validator_factory for legacy non-provenance run.")

    print("Running audit_run...")
    try:
        _run_tool(rk, args.run_id, "audit_run",
                  ["python", ".agentic-pi/runtime/audit_run.py", str(run_dir)])
    except RuntimeError as e:
        print(f"  audit_run failed: {e}")
        return 1

    _maybe_transition(rk, args.run_id, "VALIDATING")
    validating_skills, validating_ctx = _inject_skill_context(run_dir, "VALIDATING")
    if validating_skills:
        print(f"  QRSPI skills active: {', '.join(validating_skills)}")
    _maybe_transition(rk, args.run_id, "EVIDENCE_INDEXING")

    # ── Phase: POLICY / REPLAY / CERTIFYING ─────────────────────────────
    # Strict mode does not synthesize expected_artifacts.json before certifying.
    ea_path = run_dir / "expected_artifacts.json"
    outputs = contract.get("final_outputs", [])
    if outputs and not ea_path.exists():
        print("  expected_artifacts.json missing; strict mode will not synthesize artifact contracts")
        return 1

    if not provenance_mode:
        print("Running legacy certifier compatibility path...")
        _, status = _run_direct_certifier(run_dir)
        return 0 if status == "DONE_PASS" else 1

    # ── 7. Full verification pipeline ───────────────────────────
    _maybe_transition(rk, args.run_id, "POLICY_DECIDING")
    _maybe_transition(rk, args.run_id, "REPLAYING")
    _maybe_transition(rk, args.run_id, "CERTIFYING")
    cert_skills, cert_ctx = _inject_skill_context(run_dir, "CERTIFYING")
    if cert_skills:
        print(f"  QRSPI skills active: {', '.join(cert_skills)}")
    print("Running full verification (artifact routing + provenance + policy + replay + certifier)...")
    verification_status = _run_full_verification(
        run_dir,
        args.run_id,
        skip_memory_consolidation=args.skip_memory_update,
    )

    # ── Phase: REPORTING / MEMORY ─────────────────────────────────────────
    _maybe_transition(rk, args.run_id, "REPORTING")
    print(f"Final kernel state: {rk.get_run_state(args.run_id)['current_phase']}")

    if not args.skip_memory_update:
        _maybe_transition(rk, args.run_id, "MEMORY_CONSOLIDATING")
        print("Updating memory from runs...")
        try:
            _run_tool(rk, args.run_id, "update_memory",
                      ["python", ".agentic-pi/runtime/update_memory_from_runs.py", "--run-dir", str(run_dir)], cwd=BASE_DIR)
        except RuntimeError as e:
            print(f"  memory update warning: {e}")

    # Read certification status to decide DONE transition and exit code.
    # If strict verification stopped before certification, keep that failure
    # status instead of treating missing certification as DONE.
    cert_status = verification_status
    cert_path = run_dir / "certification.json"
    if cert_path.exists():
        try:
            with cert_path.open(encoding='utf-8-sig') as f:
                cert_data = json.load(f)
            cert_status = cert_data.get("status")
        except Exception:
            pass

    # Only transition to DONE when certification passed.
    if cert_status in ("DONE_PASS", "CERTIFIED_DONE", "PROVISIONAL_DONE"):
        _maybe_transition(rk, args.run_id, "DONE")
    else:
        print(f"  certification status is {cert_status}; skipping DONE transition")

    print(f"Final state. Kernel phase: {rk.get_run_state(args.run_id)['current_phase']}")

    # Return non-zero unless certifier-owned status is a passing status.
    if cert_status in ("DONE_PASS", "CERTIFIED_DONE", "PROVISIONAL_DONE"):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
