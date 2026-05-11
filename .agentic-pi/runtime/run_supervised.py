#!/usr/bin/env python3
"""Supervised run — wires all layers together.

Flow:
  Vertical spine (QRSPI phases, sequential)
    → Horizontal dispatch within each phase (all ready packets in parallel)
    → Progressive skills injected into every packet
    → Execution layer validates write scope per role
    → Repair layer enforces budget on rejection
    → Phase completes only when ALL packets resolve

Usage:
  python .agentic-pi/runtime/run_supervised.py --run-id <id>
  python .agentic-pi/runtime/run_supervised.py --run-id bench_simple
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def _load_module(name: str, rel_path: str):
    import importlib.util
    path = BASE_DIR / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════════════════════════════════════════
#  Layer imports
# ═══════════════════════════════════════════════════════════════════════════════

def _get_rk():
    return _load_module("run_kernel", ".agentic-pi/run_kernel/run_kernel.py")


def _get_sl():
    return _load_module("supervisor_loop", ".agentic-pi/runtime/supervisor_loop.py")


def _get_skill():
    return _load_module("skill_dispatcher", ".agentic-pi/runtime/skill_dispatcher.py")


def _get_write_scope():
    return _load_module("validate_write_scope",
                        ".agentic-pi/execution/validators/validate_write_scope.py")


def _get_repair_budget():
    return _load_module("validate_repair_budget",
                        ".agentic-pi/repair/validators/validate_repair_budget.py")


def _get_repair_scope():
    return _load_module("validate_repair_scope",
                        ".agentic-pi/repair/validators/validate_repair_scope.py")


# ═══════════════════════════════════════════════════════════════════════════════
#  Phase → Tool mapping
# ═══════════════════════════════════════════════════════════════════════════════

PHASE_TOOLS: dict[str, list[dict]] = {
    "PLANNING": [
        {"tool": "plan_router", "cmd": ["python", ".agentic-pi/runtime/plan_router.py", "--run-id", "{run_id}"], "role": "Planner"},
        {"tool": "plan_selector", "cmd": ["python", ".agentic-pi/runtime/plan_selector.py", "--run-id", "{run_id}"], "role": "Planner"},
        {"tool": "plan_merger", "cmd": ["python", ".agentic-pi/runtime/plan_merger.py", "--run-id", "{run_id}"], "role": "Planner"},
        {"tool": "plan_graph_builder", "cmd": ["python", ".agentic-pi/runtime/plan_graph_builder.py", "{run_id}"], "role": "Planner"},
    ],
    "IMPLEMENTING": [
        {"tool": "guarded_worker", "cmd": ["python", ".agentic-pi/runtime/guarded_worker.py", "--run-id", "{run_id}"], "role": "Engineer"},
    ],
    "VALIDATOR_BUILDING": [],
    "VALIDATING": [],
    "EVIDENCE_INDEXING": [
        {"tool": "artifact_linker", "cmd": ["python", ".agentic-pi/runtime/artifact_linker.py", "{run_id}"], "role": "Critic"},
        {"tool": "task_graph_builder", "cmd": ["python", ".agentic-pi/runtime/task_graph_builder.py", "{run_id}"], "role": "Critic"},
    ],
    "CERTIFYING": [
        {"tool": "certify_run", "cmd": ["python", ".agentic-pi/validators/certify_run.py", "{run_dir}"], "role": "Certifier"},
    ],
    "MEMORY_CONSOLIDATING": [
        {"tool": "update_memory", "cmd": ["python", ".agentic-pi/runtime/update_memory_from_runs.py"], "role": "MemoryWriter", "cwd": str(BASE_DIR)},
    ],
}

# Phases where the supervisor dispatches packets (agent phases)
# Deterministic phases (POLICY_DECIDING, REPLAYING) are kernel-controlled
AGENT_PHASES = ["PLANNING", "IMPLEMENTING", "EVIDENCE_INDEXING", "CERTIFYING", "MEMORY_CONSOLIDATING"]


# ═══════════════════════════════════════════════════════════════════════════════
#  Tool executor (runs a dispatched packet's tool)
# ═══════════════════════════════════════════════════════════════════════════════

def run_tool(tool_spec: dict, run_id: str, run_dir: Path) -> dict:
    """Execute a tool for a dispatched work packet.

    Returns {"exit_code": int, "stdout": str, "failed": bool}.
    """
    cmd = [part.replace("{run_id}", run_id).replace("{run_dir}", str(run_dir))
           for part in tool_spec["cmd"]]
    cwd = tool_spec.get("cwd")
    print(f"    running {tool_spec['tool']}...")
    try:
        result = subprocess.run(
            cmd, cwd=cwd or BASE_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        tail = "\n".join(result.stdout.splitlines()[-5:]) if result.stdout else ""
        if result.returncode != 0:
            print(f"    {tool_spec['tool']} exit {result.returncode}")
            if tail:
                print(f"    last output: {tail}")
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout or "",
            "failed": result.returncode != 0,
        }
    except FileNotFoundError as e:
        return {"exit_code": -1, "stdout": str(e), "failed": True}


# ═══════════════════════════════════════════════════════════════════════════════
#  Work packet creation for a phase
# ═══════════════════════════════════════════════════════════════════════════════

def create_packets_for_phase(rk, run_id: str, phase: str, run_dir: Path) -> list[str]:
    """Create work packets for all tools in a phase. Returns list of packet IDs."""
    tool_specs = PHASE_TOOLS.get(phase, [])
    pids = []
    for spec in tool_specs:
        pid = rk.create_work_packet(
            run_id, phase=phase, role=spec["role"],
            task=f"Run {spec['tool']}",
        )
        pids.append(pid)
        print(f"    created packet {pid} for {spec['tool']}")
    return pids


# ═══════════════════════════════════════════════════════════════════════════════
#  Layer validators
# ═══════════════════════════════════════════════════════════════════════════════

def check_write_scope(file_path: str, role: str, run_id: str) -> dict:
    """Validate a file write against the execution layer's write scope policy."""
    ws = _get_write_scope()
    return ws.validate_write_scope(file_path, role, run_id)


def check_repair_budget(repair_type: str, attempt_count: int) -> dict:
    """Validate repair budget against the repair layer policy."""
    rb = _get_repair_budget()
    return rb.validate_repair_attempt(repair_type, attempt_count)


def check_repair_scope(action: str, repair_type: str) -> dict:
    """Validate a repair action against the repair layer scope policy."""
    rs = _get_repair_scope()
    return rs.validate_repair_action(action, repair_type)


# ═══════════════════════════════════════════════════════════════════════════════
#  Execute a single phase
# ═══════════════════════════════════════════════════════════════════════════════

def execute_phase(rk, sl, run_id: str, phase: str, run_dir: Path) -> dict:
    """Execute one phase: create packets, dispatch, run tools, collect results.

    Returns the phase execution report.
    """
    report = {
        "phase": phase,
        "packets_created": 0,
        "packets_succeeded": 0,
        "packets_failed": 0,
        "skills_loaded": [],
        "write_scope_checks": [],
        "repair_events": [],
        "errors": [],
        "passed": False,
    }

    # ── Skills ──────────────────────────────────────────────────────────
    try:
        skill = _get_skill()
        skills = skill.get_accumulated_skill_texts(phase)
        report["skills_loaded"] = [s["name"] for s in skills]
        if skills:
            print(f"    skills accumulated: {', '.join(report['skills_loaded'])}")
    except Exception as e:
        report["errors"].append(f"skill_dispatcher: {e}")

    # ── Create packets for this phase ───────────────────────────────────
    tool_specs = PHASE_TOOLS.get(phase, [])
    if not tool_specs:
        print(f"    no tools defined for {phase}")
        report["passed"] = True
        return report

    pids = create_packets_for_phase(rk, run_id, phase, run_dir)
    report["packets_created"] = len(pids)

    # ── Get ready packets (horizontal select) ───────────────────────────
    ready = sl.get_ready_packets(run_id, phase)
    if not ready:
        report["errors"].append(f"No ready packets in {phase}")
        return report

    # ── Dispatch all ────────────────────────────────────────────────────
    dispatch_map = sl.dispatch_all(run_id, ready)
    print(f"    dispatched {len(dispatch_map)} packet(s)")

    # ── Execute each dispatched packet ──────────────────────────────────
    for pkt in ready:
        pid = pkt["work_packet_id"]
        # Find matching tool spec
        pkt_role = pkt.get("role", "")
        matching = [s for s in tool_specs if s["role"] == pkt_role]
        if not matching:
            report["packets_failed"] += 1
            report["errors"].append(f"No tool spec for role {pkt_role!r}")
            continue
        spec = matching[0]

        # Execute the tool
        tool_result = run_tool(spec, run_id, run_dir)
        if tool_result["failed"]:
            report["packets_failed"] += 1
            report["errors"].append(f"{spec['tool']}: exit {tool_result['exit_code']}")

            # ── Repair layer: check budget ──────────────────────────
            budget_check = check_repair_budget(phase, 1)
            if budget_check["budget_exhausted"]:
                report["repair_events"].append({
                    "packet": pid,
                    "budget_exhausted": True,
                    "escalation": budget_check["escalation_target"],
                })
                rk.reject_packet(run_id, pid,
                                 error=f"Budget exhausted → {budget_check['escalation_target']}")

                # ── Repair scope check ─────────────────────────────
                scope_check = check_repair_scope(
                    f"rerun {spec['tool']}", phase)
                report["write_scope_checks"].append({
                    "action": f"rerun {spec['tool']}",
                    "repair_type": phase,
                    "allowed": scope_check["allowed"],
                })
            else:
                rk.reject_packet(run_id, pid, error=f"{spec['tool']} failed (repairable)")
                report["repair_events"].append({
                    "packet": pid,
                    "budget_exhausted": False,
                })
        else:
            report["packets_succeeded"] += 1
            # Accept at kernel level
            rk.receive_result(run_id, pid, f"results/{spec['tool']}.json")
            rk.start_validation(run_id, pid)
            rk.accept_packet(run_id, pid)

    # ── Phase outcome ───────────────────────────────────────────────────
    pids_all = [p["work_packet_id"] for p in ready]
    results = sl.poll_until_complete(run_id, pids_all, poll_interval=0.05)
    outcome = sl.determine_phase_outcome(results)
    report["passed"] = outcome["passed"]
    report["outcome"] = outcome

    # Mark phase completed if passed
    if outcome["passed"]:
        try:
            rk.mark_phase_completed(run_id, phase)
            print(f"    phase {phase} COMPLETED")
        except Exception as e:
            report["errors"].append(f"mark_phase_completed: {e}")
    else:
        print(f"    phase {phase} FAILED: {outcome['summary']}")

    return report


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a goal with the full supervised pipeline")
    parser.add_argument("--run-id", required=True, help="Run identifier (must exist)")
    parser.add_argument("--skip-memory-update", action="store_true", help="Skip memory consolidation")
    args = parser.parse_args(argv)

    rk = _get_rk()
    sl = _get_sl()

    run_dir = BASE_DIR / ".agentic-runs" / args.run_id
    if not run_dir.is_dir():
        print(f"ERROR: Run folder {run_dir} does not exist")
        return 1

    try:
        state = rk.get_run_state(args.run_id)
    except FileNotFoundError:
        print(f"ERROR: Run '{args.run_id}' has no run_state.json. Create run first.")
        return 1

    print(f"Run kernel state: {state['current_phase']}")
    print(f"Supervised run for {args.run_id}")
    print()

    # ── Phase sequence (QRSPI vertical spine) ─────────────────────────────
    phase_sequence = [
        "INTAKE", "QUESTIONING", "RESEARCHING", "DESIGNING",
        "STRUCTURING", "PLANNING", "WORKTREE_READY", "IMPLEMENTING",
        "VALIDATOR_BUILDING", "VALIDATING", "EVIDENCE_INDEXING",
        "POLICY_DECIDING", "REPLAYING", "CERTIFYING", "REPORTING",
    ]
    if not args.skip_memory_update:
        phase_sequence.append("MEMORY_CONSOLIDATING")

    all_phase_reports = []
    all_passed = True
    current_phase = state["current_phase"]

    for phase in phase_sequence:
        # Skip phases that have already been passed
        phase_order = [p["phase"] for p in rk.get_phase_queue(args.run_id)["phases"]]
        try:
            current_idx = phase_order.index(current_phase)
            target_idx = phase_order.index(phase)
        except ValueError:
            continue

        if target_idx < current_idx:
            continue  # already completed

        print(f"\n{'='*60}")
        print(f"Phase: {phase}")
        print(f"{'='*60}")

        # Transition kernel to this phase
        try:
            rk.transition_to(args.run_id, phase)
            print(f"  kernel -> {phase}")
        except RuntimeError as e:
            print(f"  transition skipped: {e}")
            all_passed = False
            break

        current_phase = phase

        # Execute phase (create packets, dispatch, run, collect)
        report = execute_phase(rk, sl, args.run_id, phase, run_dir)
        all_phase_reports.append(report)

        if not report["passed"]:
            all_passed = False
            if report["packets_failed"] > 0:
                print(f"  stopping due to failures in {phase}")
                break

    # ── Transition to DONE ────────────────────────────────────────────────
    if all_passed:
        try:
            rk.transition_to(args.run_id, "DONE")
            print(f"\n  kernel -> DONE")
        except RuntimeError as e:
            print(f"  done transition: {e}")

    # ── Final report ──────────────────────────────────────────────────────
    try:
        final_state = rk.get_run_state(args.run_id)
    except Exception:
        final_state = {}

    print(f"\n{'='*60}")
    print(f"RUN COMPLETE: {args.run_id}")
    print(f"{'='*60}")
    print(f"Final kernel phase: {final_state.get('current_phase', 'UNKNOWN')}")
    print(f"All phases passed:  {all_passed}")
    print()

    for report in all_phase_reports:
        mark = "✅" if report["passed"] else "❌"
        skills = ", ".join(report["skills_loaded"]) if report["skills_loaded"] else "(none)"
        outcome_str = report.get("outcome", {}).get("summary", "no packets")
        print(f"  {mark} {report['phase']:25s} packets={report['packets_created']}  {outcome_str}")
        if report["skills_loaded"]:
            print(f"     skills: {skills}")

    if not all_passed:
        print(f"\nFAILURES:")
        for report in all_phase_reports:
            for err in report.get("errors", []):
                print(f"  - {report['phase']}: {err}")

    repair_events = [r for report in all_phase_reports for r in report.get("repair_events", [])]
    if repair_events:
        exhausted = sum(1 for r in repair_events if r.get("budget_exhausted"))
        print(f"\nRepair events: {len(repair_events)} total, {exhausted} budget-exhausted")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
