#!/usr/bin/env python3
"""Run Kernel — deterministic state machine controller for RPG-Harness v5.

This is a trusted core component. It controls:
- Run state management (run_state.json)
- Phase queue management (phase_queue.json)
- Work packet lifecycle (dispatch, receive, accept, reject)
- Dispatch ledger (dispatch_log.jsonl)
- Budget enforcement
- Transition validation delegation

The supervisor controller reads the ledger and state files.
The kernel writes them. No agent writes kernel-owned files.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


_RUN_KERNEL_DIR = Path(__file__).resolve().parent
_AGENTIC_PI_DIR = _RUN_KERNEL_DIR.parent
_RUNS_DIR = _AGENTIC_PI_DIR.parent / ".agentic-runs"
_VALIDATE_TRANSITION_PATH = _RUN_KERNEL_DIR / "validate_transition.py"

# Ensure we can import sibling modules
if str(_RUN_KERNEL_DIR) not in sys.path:
    sys.path.insert(0, str(_RUN_KERNEL_DIR))

# Lazy import for transition validation
_validate_transition_module = None


def _load_validate_transition():
    global _validate_transition_module
    if _validate_transition_module is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_transition", _VALIDATE_TRANSITION_PATH
        )
        _validate_transition_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_validate_transition_module)
    return _validate_transition_module


# ─── helpers ──────────────────────────────────────────────────────────────────


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_run_dir(run_id: str) -> Path:
    return _RUNS_DIR / run_id


# ─── Kernel API ───────────────────────────────────────────────────────────────


def create_run(run_id: str, goal_contract_path: Optional[str] = None) -> Path:
    """Initialize a new run with run_state.json and phase_queue.json.

    Returns the run directory path.
    Raises FileExistsError if the run already exists.
    """
    run_dir = _get_run_dir(run_id)
    if run_dir.exists():
        raise FileExistsError(f"Run '{run_id}' already exists at {run_dir}")

    run_dir.mkdir(parents=True, exist_ok=True)

    now = _now_iso()

    # Initial run state
    run_state = {
        "schema_version": "run_state_v1",
        "run_id": run_id,
        "current_phase": "NEW",
        "previous_phase": "",
        "phase_history": [
            {"phase": "NEW", "entered_at": now, "exited_at": None}
        ],
        "overall_status": "IN_PROGRESS",
        "created_at": now,
        "updated_at": now,
        "kernel_version": "rpg_harness_v5_kernel_v1",
    }
    _write_json(run_dir / "run_state.json", run_state)

    # Initial phase queue (QRSPI phases + certification pipeline)
    default_phases = [
        "INTAKE", "QUESTIONING", "RESEARCHING", "DESIGNING",
        "STRUCTURING", "PLANNING", "WORKTREE_READY", "IMPLEMENTING",
        "VALIDATOR_BUILDING", "VALIDATING", "EVIDENCE_INDEXING",
        "POLICY_DECIDING", "REPLAYING", "CERTIFYING", "REPORTING",
        "MEMORY_CONSOLIDATING",
    ]
    phase_queue = {
        "schema_version": "phase_queue_v1",
        "run_id": run_id,
        "phases": [
            {
                "phase": p,
                "status": "PENDING",
                "order": idx,
                "work_packet_ids": [],
                "dependencies": [],
                "result_summary": None,
                "started_at": None,
                "completed_at": None,
            }
            for idx, p in enumerate(default_phases)
        ],
        "created_at": now,
        "updated_at": now,
    }
    _write_json(run_dir / "phase_queue.json", phase_queue)

    # Create subdirectories
    (run_dir / "work_packets").mkdir(exist_ok=True)
    (run_dir / "work_results").mkdir(exist_ok=True)
    (run_dir / "validation_results").mkdir(exist_ok=True)

    # Initialize dispatch log
    _append_jsonl(run_dir / "dispatch_log.jsonl", {
        "event": "run_created",
        "run_id": run_id,
        "timestamp": now,
        "goal_contract_path": goal_contract_path,
    })

    # Write run manifest
    _write_json(run_dir / "run_manifest.json", {
        "schema_version": "run_manifest_v1",
        "run_id": run_id,
        "created_at": now,
        "kernel_version": "rpg_harness_v5_kernel_v1",
        "goal_contract_path": goal_contract_path,
    })

    return run_dir


# ─── State reading ────────────────────────────────────────────────────────────


def get_run_state(run_id: str) -> dict:
    """Return the run_state.json dict."""
    run_dir = _get_run_dir(run_id)
    return _load_json(run_dir / "run_state.json")


def get_phase_queue(run_id: str) -> dict:
    """Return the phase_queue.json dict."""
    run_dir = _get_run_dir(run_id)
    return _load_json(run_dir / "phase_queue.json")


def list_runs() -> list[str]:
    """List all run IDs that have a run_state.json."""
    if not _RUNS_DIR.exists():
        return []
    return sorted(
        d.name for d in _RUNS_DIR.iterdir()
        if d.is_dir() and (d / "run_state.json").exists()
    )


def get_dispatch_log(run_id: str) -> list[dict]:
    """Read dispatch_log.jsonl and return list of event records."""
    log_path = _get_run_dir(run_id) / "dispatch_log.jsonl"
    if not log_path.exists():
        return []
    records = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ─── Phase transitions ────────────────────────────────────────────────────────


def _run_pre_transition_gates(run_id: str, target_phase: str) -> None:
    """Run pre-transition gates before entering certain phases.

    Raises RuntimeError if a gate blocks the transition.
    """
    run_dir = _get_run_dir(run_id)

    if target_phase == "PLANNING":
        # Gate: plan_coverage_matrix.json must exist and be complete
        _gate_plan_completeness(run_dir)
    elif target_phase == "IMPLEMENTING":
        # Gate: vertical slice must be selected
        _gate_vertical_slice_selected(run_dir)
    elif target_phase == "VALIDATING":
        # Gate: validator factory must have certified the verifier
        _gate_validator_certified(run_dir)


def _gate_plan_completeness(run_dir: Path) -> None:
    """Run Plan Completeness Gate. Blocks if plan is incomplete."""
    planning_dir = Path(__file__).resolve().parents[1] / "planning"
    gate_path = planning_dir / "plan_completeness_gate.py"
    if not gate_path.is_file():
        return
    matrix_path = run_dir / "plan_coverage_matrix.json"
    if not matrix_path.is_file():
        raise RuntimeError(
            "PLANNING blocked: plan_coverage_matrix.json missing in run_dir"
        )
    import subprocess
    result = subprocess.run(
        [sys.executable, str(gate_path), str(run_dir)],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f"Plan Completeness Gate failed: {result.stderr.strip()}")
    report_path = run_dir / "plan_completeness_report.json"
    if report_path.is_file():
        report = _load_json(report_path)
        if not report.get("plan_complete", False):
            gaps = report.get("gaps", [])
            raise RuntimeError(
                f"PLANNING blocked: plan incomplete. Gaps: {'; '.join(gaps[:5])}"
            )


def _gate_vertical_slice_selected(run_dir: Path) -> None:
    """Run Vertical Slice Selector. Blocks if no slice was selected."""
    supervisor_dir = Path(__file__).resolve().parents[1] / "supervisor"
    selector_path = supervisor_dir / "vertical_slice_selector.py"
    if not selector_path.is_file():
        return
    candidates_path = run_dir / "vertical_slice_candidates.json"
    if not candidates_path.is_file():
        raise RuntimeError(
            "IMPLEMENT blocked: vertical_slice_candidates.json missing"
        )
    import subprocess
    result = subprocess.run(
        [sys.executable, str(selector_path), str(run_dir)],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Vertical Slice Selector failed: {result.stderr.strip()}"
        )
    selection_path = run_dir / "vertical_slice_selection.json"
    if not selection_path.is_file():
        raise RuntimeError(
            "IMPLEMENT blocked: vertical_slice_selection.json not produced"
        )
    selection = _load_json(selection_path)
    if not selection.get("selected_slice_id"):
        raise RuntimeError(
            "IMPLEMENTING blocked: no vertical slice selected \u2014 all candidates failed validation"
        )


def _gate_validator_certified(run_dir: Path) -> None:
    """Gate: validator_factory must have certified the verifier before validation."""
    cert_path = run_dir / "validator_certification.json"
    if not cert_path.is_file():
        raise RuntimeError(
            "VALIDATING blocked: validator_certification.json missing \u2014 "
            "run validator_factory first"
        )
    cert = _load_json(cert_path)
    if not cert.get("certified", False):
        reasons = cert.get("reasons", [])
        raise RuntimeError(
            f"VALIDATING blocked: verifier not certified. Reasons: {'; '.join(reasons[:3])}"
        )


def transition_to(run_id: str, target_phase: str) -> dict:
    """Attempt to transition the run to a new phase.

    Validates the transition against transition_rules.json.
    Updates run_state.json and phase_queue.json.

    Returns the updated run_state dict.
    Raises RuntimeError if the transition is not allowed.
    """
    vt = _load_validate_transition()
    run_state = get_run_state(run_id)
    current = run_state["current_phase"]

    # Validate transition
    errors = vt.validate_transition_with_registry(current, target_phase)
    if errors:
        raise RuntimeError(f"Transition rejected: {'; '.join(errors)}")

    # ── Pre-transition gates ──────────────────────────────────────────
    _run_pre_transition_gates(run_id, target_phase)

    now = _now_iso()

    # Update phase history
    if run_state["phase_history"]:
        run_state["phase_history"][-1]["exited_at"] = now
    run_state["phase_history"].append({
        "phase": target_phase,
        "entered_at": now,
        "exited_at": None,
    })

    run_state["previous_phase"] = current
    run_state["current_phase"] = target_phase
    run_state["updated_at"] = now

    # Update overall_status for blocked/terminal states
    if target_phase.startswith("BLOCKED_BY_"):
        run_state["overall_status"] = "BLOCKED"
    elif target_phase == "DONE":
        run_state["overall_status"] = "DONE"
    elif target_phase in ("FAILED_AUTHORITY_VIOLATION",):
        run_state["overall_status"] = "FAILED"

    _write_json(_get_run_dir(run_id) / "run_state.json", run_state)

    # Update phase queue entry if this is a forward phase
    phase_queue = get_phase_queue(run_id)
    for entry in phase_queue["phases"]:
        if entry["phase"] == target_phase:
            entry["status"] = "ACTIVE"
            entry["started_at"] = now
        if entry["phase"] == current and current != target_phase:
            if entry["status"] == "ACTIVE":
                entry["status"] = "COMPLETED"
                entry["completed_at"] = now
    phase_queue["updated_at"] = now
    _write_json(_get_run_dir(run_id) / "phase_queue.json", phase_queue)

    # Log transition
    _append_jsonl(_get_run_dir(run_id) / "dispatch_log.jsonl", {
        "event": "phase_transition",
        "run_id": run_id,
        "from_phase": current,
        "to_phase": target_phase,
        "timestamp": now,
    })

    return run_state


# ─── Work packet lifecycle ────────────────────────────────────────────────────


def _load_accumulated_skills(phase: str) -> Optional[str]:
    """Auto-load accumulated QRSPI skills for the given phase.

    Returns None if skill_dispatcher cannot be loaded (graceful fallback).
    """
    try:
        import importlib.util
        _RKDIR = Path(__file__).resolve().parent
        dispatcher_path = _RKDIR.parent / "runtime" / "skill_dispatcher.py"
        if not dispatcher_path.exists():
            return None
        spec = importlib.util.spec_from_file_location("skill_dispatcher", dispatcher_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.format_accumulated_context(phase)
    except Exception:
        return None


def create_work_packet(
    run_id: str,
    phase: str,
    role: str,
    task: str,
    *,
    input_artifacts: Optional[list[str]] = None,
    allowed_write_paths: Optional[list[str]] = None,
    forbidden_write_paths: Optional[list[str]] = None,
    max_model_calls: int = 3,
    max_repair_attempts: int = 2,
    output_schema: str = "default_result.schema.json",
    status_claim_allowed: bool = False,
    dependencies: Optional[list[str]] = None,
    accumulated_skills_context: Optional[str] = None,
) -> str:
    """Create a work packet and add it to the phase's queue.

    Returns the work_packet_id (format: WP.<PHASE>.<NNN>).
    """
    run_dir = _get_run_dir(run_id)
    packets_dir = run_dir / "work_packets"

    # Determine next sequence number
    existing = list(packets_dir.glob(f"WP.{phase}.*.json"))
    seq = len(existing) + 1
    work_packet_id = f"WP.{phase}.{seq:03d}"

    packet = {
        "schema_version": "work_packet_v1",
        "work_packet_id": work_packet_id,
        "phase": phase,
        "role": role,
        "task": task,
        "input_artifacts": input_artifacts or [],
        "input_summaries": {},
        "allowed_write_paths": allowed_write_paths or [],
        "forbidden_write_paths": forbidden_write_paths or [
            "final_status.json",
            "final_status.md",
            "certification.json",
            "policy_decision.json",
            "evidence_freeze.json",
            "run_state.json",
            "phase_queue.json",
        ],
        "status": "PENDING",
        "max_model_calls": max_model_calls,
        "max_repair_attempts": max_repair_attempts,
        "repair_attempt_count": 0,
        "output_schema": output_schema,
        "status_claim_allowed": status_claim_allowed,
        "result_path": None,
        "validation_result_path": None,
        "error": None,
        "dispatch_timestamp": None,
        "result_timestamp": None,
        "dependencies": dependencies or [],
        "accumulated_skills_context": accumulated_skills_context
            if accumulated_skills_context is not None
            else _load_accumulated_skills(phase),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }

    _write_json(packets_dir / f"{work_packet_id}.json", packet)

    # Add to phase queue
    phase_queue = get_phase_queue(run_id)
    for entry in phase_queue["phases"]:
        if entry["phase"] == phase:
            entry.setdefault("work_packet_ids", []).append(work_packet_id)
            break
    phase_queue["updated_at"] = _now_iso()
    _write_json(run_dir / "phase_queue.json", phase_queue)

    # Log
    _append_jsonl(run_dir / "dispatch_log.jsonl", {
        "event": "work_packet_created",
        "run_id": run_id,
        "work_packet_id": work_packet_id,
        "phase": phase,
        "role": role,
        "timestamp": _now_iso(),
    })

    return work_packet_id


def _get_packet_path(run_id: str, work_packet_id: str) -> Path:
    return _get_run_dir(run_id) / "work_packets" / f"{work_packet_id}.json"


def _update_packet(run_id: str, work_packet_id: str, updates: dict) -> dict:
    """Load a work packet, apply updates, save, and return it."""
    path = _get_packet_path(run_id, work_packet_id)
    packet = _load_json(path)
    packet.update(updates)
    packet["updated_at"] = _now_iso()
    _write_json(path, packet)
    return packet


def dispatch_packet(run_id: str, work_packet_id: str) -> dict:
    """Mark a PENDING work packet as DISPATCHED.

    Returns the updated packet.
    Raises RuntimeError if not in PENDING state.
    """
    # Check current status before mutating
    pkt_path = _get_packet_path(run_id, work_packet_id)
    current = _load_json(pkt_path)
    if current.get("status") != "PENDING":
        raise RuntimeError(
            f"Cannot dispatch packet '{work_packet_id}': "
            f"current status is '{current.get('status')}', expected 'PENDING'"
        )
    packet = _update_packet(run_id, work_packet_id, {
        "status": "DISPATCHED",
        "dispatch_timestamp": _now_iso(),
    })
    _append_jsonl(_get_run_dir(run_id) / "dispatch_log.jsonl", {
        "event": "work_packet_dispatched",
        "run_id": run_id,
        "work_packet_id": work_packet_id,
        "timestamp": _now_iso(),
    })
    return packet


def receive_result(run_id: str, work_packet_id: str, result_path: str) -> dict:
    """Mark a DISPATCHED packet as RESULT_RECEIVED.

    Args:
        run_id: The run identifier.
        work_packet_id: The work packet identifier.
        result_path: Path to the result file (relative to run_dir).

    Returns the updated packet.
    """
    packet = _update_packet(run_id, work_packet_id, {
        "status": "RESULT_RECEIVED",
        "result_path": result_path,
        "result_timestamp": _now_iso(),
    })
    _append_jsonl(_get_run_dir(run_id) / "dispatch_log.jsonl", {
        "event": "work_packet_result_received",
        "run_id": run_id,
        "work_packet_id": work_packet_id,
        "result_path": result_path,
        "timestamp": _now_iso(),
    })
    return packet


def start_validation(run_id: str, work_packet_id: str) -> dict:
    """Mark a RESULT_RECEIVED packet as VALIDATING."""
    return _update_packet(run_id, work_packet_id, {"status": "VALIDATING"})


def accept_packet(run_id: str, work_packet_id: str,
                  validation_result_path: Optional[str] = None) -> dict:
    """Mark a VALIDATING or RESULT_RECEIVED packet as ACCEPTED."""
    packet = _update_packet(run_id, work_packet_id, {
        "status": "ACCEPTED",
        "validation_result_path": validation_result_path,
    })
    _append_jsonl(_get_run_dir(run_id) / "dispatch_log.jsonl", {
        "event": "work_packet_accepted",
        "run_id": run_id,
        "work_packet_id": work_packet_id,
        "timestamp": _now_iso(),
    })
    return packet


def reject_packet(run_id: str, work_packet_id: str,
                  error: str = "",
                  validation_result_path: Optional[str] = None) -> dict:
    """Mark a VALIDATING or RESULT_RECEIVED packet as REJECTED.

    If repairable and budget remains, creates a REPAIR_REQUESTED entry
    by incrementing repair_attempt_count.
    """
    packet = _get_packet_path(run_id, work_packet_id)
    data = _load_json(packet)

    current_repairs = data.get("repair_attempt_count", 0)
    max_repairs = data.get("max_repair_attempts", 2)

    if current_repairs < max_repairs:
        new_status = "REPAIR_REQUESTED"
        data["repair_attempt_count"] = current_repairs + 1
    else:
        new_status = "REJECTED"

    data["status"] = new_status
    data["error"] = error
    data["validation_result_path"] = validation_result_path
    data["updated_at"] = _now_iso()
    _write_json(packet, data)

    _append_jsonl(_get_run_dir(run_id) / "dispatch_log.jsonl", {
        "event": "work_packet_rejected",
        "run_id": run_id,
        "work_packet_id": work_packet_id,
        "new_status": new_status,
        "repair_attempt_count": data["repair_attempt_count"],
        "error": error,
        "timestamp": _now_iso(),
    })

    return data


def block_packet(run_id: str, work_packet_id: str, error: str = "") -> dict:
    """Mark any active packet as BLOCKED."""
    return _update_packet(run_id, work_packet_id, {
        "status": "BLOCKED",
        "error": error,
    })


def cancel_packet(run_id: str, work_packet_id: str, error: str = "") -> dict:
    """Mark any packet as CANCELLED."""
    return _update_packet(run_id, work_packet_id, {
        "status": "CANCELLED",
        "error": error,
    })


# ─── Packet queries ───────────────────────────────────────────────────────────


def get_packet(run_id: str, work_packet_id: str) -> dict:
    """Read a work packet by ID."""
    return _load_json(_get_packet_path(run_id, work_packet_id))


def list_packets(run_id: str, phase: Optional[str] = None,
                 status: Optional[str] = None) -> list[dict]:
    """List all work packets, optionally filtered by phase and/or status."""
    packets_dir = _get_run_dir(run_id) / "work_packets"
    if not packets_dir.exists():
        return []

    results = []
    for path in sorted(packets_dir.glob("WP.*.*.json")):
        data = _load_json(path)
        if phase and data.get("phase") != phase:
            continue
        if status and data.get("status") != status:
            continue
        results.append(data)
    return results


def get_next_pending_packet(run_id: str) -> Optional[dict]:
    """Find the next PENDING work packet whose dependencies are all ACCEPTED.

    Returns the packet dict, or None if none available.
    """
    packets_dir = _get_run_dir(run_id) / "work_packets"
    if not packets_dir.exists():
        return None

    for path in sorted(packets_dir.glob("WP.*.*.json")):
        data = _load_json(path)
        if data.get("status") != "PENDING":
            continue
        deps = data.get("dependencies", [])
        if not deps:
            return data
        # Check all dependencies are ACCEPTED
        all_deps_met = True
        for dep_id in deps:
            dep_path = packets_dir / f"{dep_id}.json"
            if not dep_path.exists():
                all_deps_met = False
                break
            dep_data = _load_json(dep_path)
            if dep_data.get("status") not in ("ACCEPTED", "CANCELLED"):
                all_deps_met = False
                break
        if all_deps_met:
            return data

    return None


def mark_phase_completed(run_id: str, phase: str) -> None:
    """Mark a phase as COMPLETED in the phase queue."""
    phase_queue = get_phase_queue(run_id)
    now = _now_iso()
    found = False
    for entry in phase_queue["phases"]:
        if entry["phase"] == phase:
            entry["status"] = "COMPLETED"
            entry["completed_at"] = now
            found = True
            break
    if not found:
        raise ValueError(f"Phase '{phase}' not found in phase queue for run '{run_id}'")
    phase_queue["updated_at"] = now
    _write_json(_get_run_dir(run_id) / "phase_queue.json", phase_queue)

    _append_jsonl(_get_run_dir(run_id) / "dispatch_log.jsonl", {
        "event": "phase_completed",
        "run_id": run_id,
        "phase": phase,
        "timestamp": now,
    })


# ─── Path helpers ─────────────────────────────────────────────────────────────


def get_run_dir(run_id: str) -> Path:
    """Return the run directory path."""
    return _get_run_dir(run_id)


def get_runs_dir() -> Path:
    """Return the runs root directory."""
    return _RUNS_DIR


# ─── CLI entry point ──────────────────────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RPG-Harness v5 Run Kernel CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create_parser = subparsers.add_parser("create", help="Create a new run")
    create_parser.add_argument("run_id", help="Run identifier")
    create_parser.add_argument("--goal-contract", help="Path to goal contract")

    # state
    state_parser = subparsers.add_parser("state", help="Show current run state")
    state_parser.add_argument("run_id", help="Run identifier")

    # transition
    trans_parser = subparsers.add_parser("transition", help="Transition to a new phase")
    trans_parser.add_argument("run_id", help="Run identifier")
    trans_parser.add_argument("target_phase", help="Target phase name")

    # packet
    packet_parser = subparsers.add_parser("create-packet", help="Create a work packet")
    packet_parser.add_argument("run_id", help="Run identifier")
    packet_parser.add_argument("--phase", required=True, help="Phase")
    packet_parser.add_argument("--role", required=True, help="Role")
    packet_parser.add_argument("--task", required=True, help="Task description")

    # list runs
    subparsers.add_parser("list-runs", help="List all runs")

    # list packets
    lp_parser = subparsers.add_parser("list-packets", help="List work packets")
    lp_parser.add_argument("run_id", help="Run identifier")
    lp_parser.add_argument("--phase", help="Filter by phase")
    lp_parser.add_argument("--status", help="Filter by status")

    # dispatch
    dispatch_parser = subparsers.add_parser("dispatch", help="Dispatch a work packet")
    dispatch_parser.add_argument("run_id", help="Run identifier")
    dispatch_parser.add_argument("work_packet_id", help="Work packet ID")

    # receive
    receive_parser = subparsers.add_parser("receive", help="Receive a work packet result")
    receive_parser.add_argument("run_id", help="Run identifier")
    receive_parser.add_argument("work_packet_id", help="Work packet ID")
    receive_parser.add_argument("result_path", help="Path to result file")

    # log
    log_parser = subparsers.add_parser("log", help="Show dispatch log")
    log_parser.add_argument("run_id", help="Run identifier")

    args = parser.parse_args()

    if args.command == "create":
        run_dir = create_run(args.run_id, args.goal_contract)
        print(f"Run '{args.run_id}' created at {run_dir}")

    elif args.command == "state":
        state = get_run_state(args.run_id)
        print(json.dumps(state, indent=2))

    elif args.command == "transition":
        try:
            state = transition_to(args.run_id, args.target_phase)
            print(f"Transitioned to '{args.target_phase}'")
            print(f"Current state: {state['current_phase']}")
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "create-packet":
        pid = create_work_packet(
            args.run_id,
            phase=args.phase,
            role=args.role,
            task=args.task,
        )
        print(f"Created packet: {pid}")

    elif args.command == "list-runs":
        runs = list_runs()
        if runs:
            print("Runs:")
            for r in runs:
                state = get_run_state(r)
                print(f"  {r}  [{state['current_phase']}]")
        else:
            print("No runs found.")

    elif args.command == "list-packets":
        packets = list_packets(args.run_id, phase=args.phase, status=args.status)
        if packets:
            for pkt in packets:
                print(f"  {pkt['work_packet_id']}  [{pkt['status']}]  {pkt['phase']}")
        else:
            print("No packets found.")

    elif args.command == "dispatch":
        try:
            pkt = dispatch_packet(args.run_id, args.work_packet_id)
            print(f"Dispatched: {pkt['work_packet_id']}")
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "receive":
        pkt = receive_result(args.run_id, args.work_packet_id, args.result_path)
        print(f"Received result for: {pkt['work_packet_id']}")

    elif args.command == "log":
        records = get_dispatch_log(args.run_id)
        for rec in records:
            print(json.dumps(rec))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
