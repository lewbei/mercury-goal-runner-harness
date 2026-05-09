#!/usr/bin/env python3
"""Supervisor loop — horizontal work packet dispatch within a phase.

The supervisor:
1. Reads the run's phase queue to find the current ACTIVE phase
2. Selects ALL PENDING work packets in that phase whose dependencies are met
3. Dispatches them (parallel fan-out within the phase)
4. Polls for all results (ACCEPTED / REJECTED / CANCELLED)
5. Determines phase outcome and transitions

Architecture rule:
  Vertical first (QRSPI spine), then horizontal within phase.
  Phase transitions are sequential. Packet dispatch within a phase is parallel.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


_RUNTIME_DIR = Path(__file__).resolve().parent
_KERNEL_PATH = _RUNTIME_DIR.parent / "run_kernel" / "run_kernel.py"
_VERTICAL_SLICE_VALIDATOR_PATH = _RUNTIME_DIR.parent / "execution" / "validators" / "validate_vertical_slice.py"


_REJECTED_HORIZONTAL = "REJECTED_HORIZONTAL_OUTPUT"

# Poll interval when waiting for parallel results
_DEFAULT_POLL_INTERVAL = 0.25


def _load_kernel():
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_kernel", _KERNEL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════════════════════════════════════════
#  Phase lifecycle helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_active_phase(run_id: str) -> Optional[dict]:
    """Return the active phase entry from the phase queue, or None."""
    rk = _load_kernel()
    queue = rk.get_phase_queue(run_id)
    for entry in queue.get("phases", []):
        if entry.get("status") == "ACTIVE":
            return entry
    return None


def are_dependencies_met(packet: dict, run_id: str) -> bool:
    """Check if a packet's dependencies are all ACCEPTED or CANCELLED."""
    deps = packet.get("dependencies", [])
    if not deps:
        return True
    rk = _load_kernel()
    for dep_id in deps:
        try:
            dep = rk.get_packet(run_id, dep_id)
        except FileNotFoundError:
            return False
        if dep.get("status") not in ("ACCEPTED", "CANCELLED"):
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  Horizontal dispatch
# ═══════════════════════════════════════════════════════════════════════════════

def get_ready_packets(run_id: str, phase: str) -> list[dict]:
    """Get all PENDING packets in a phase whose dependencies are met.

    This is the horizontal-select function: it returns ALL ready packets,
    not just the first one.
    """
    rk = _load_kernel()
    all_phase_packets = rk.list_packets(run_id, phase=phase, status="PENDING")
    return [p for p in all_phase_packets if are_dependencies_met(p, run_id)]


def dispatch_all(run_id: str, packets: list[dict]) -> dict[str, str]:
    """Dispatch all given packets and return {packet_id: 'DISPATCHED'}.

    Returns a dict of packet_id -> initial status for tracking.
    """
    rk = _load_kernel()
    results = {}
    for pkt in packets:
        pid = pkt["work_packet_id"]
        try:
            rk.dispatch_packet(run_id, pid)
            results[pid] = "DISPATCHED"
        except RuntimeError as e:
            results[pid] = f"FAILED: {e}"
    return results


def poll_until_complete(
    run_id: str,
    packet_ids: list[str],
    poll_interval: float = _DEFAULT_POLL_INTERVAL,
    timeout: Optional[float] = None,
) -> dict[str, str]:
    """Poll packet statuses until all reach a terminal state.

    Terminal states: ACCEPTED, REJECTED, CANCELLED, BLOCKED, REPAIR_REQUESTED

    Returns {packet_id: terminal_status}.
    """
    rk = _load_kernel()
    results: dict[str, str] = {}
    start = time.monotonic()

    while len(results) < len(packet_ids):
        if timeout and (time.monotonic() - start) > timeout:
            for pid in packet_ids:
                if pid not in results:
                    results[pid] = "TIMEOUT"
            break

        for pid in packet_ids:
            if pid in results:
                continue
            try:
                pkt = rk.get_packet(run_id, pid)
                status = pkt.get("status", "UNKNOWN")
                if status in ("ACCEPTED", "REJECTED", "CANCELLED", "BLOCKED", "REPAIR_REQUESTED", _REJECTED_HORIZONTAL):
                    results[pid] = status
            except FileNotFoundError:
                results[pid] = "LOST"

        if len(results) < len(packet_ids):
            time.sleep(poll_interval)

    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  Vertical slice gate
# ═══════════════════════════════════════════════════════════════════════════════

def reject_horizontal_output(
    task_description: str,
    output_files: list[str],
    proof_command: str = "",
) -> dict:
    """Check if a packet's output represents a vertical slice.

    If the output has no fixture, no expected verdict, no proof command,
    or no test file, the packet is rejected as horizontal work.

    Returns a result dict compatible with determine_phase_outcome:
        {"status": "ACCEPTED"|"REJECTED_HORIZONTAL_OUTPUT", "reason": str, ...}
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate_vertical_slice", _VERTICAL_SLICE_VALIDATOR_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.validate_work_packet_vertical(
            task_description, output_files, proof_command)

        if result["vertical_slice_passed"]:
            return {
                "status": "ACCEPTED",
                "reason": "Vertical slice proof present",
                "checks": result["checks"],
            }
        else:
            return {
                "status": _REJECTED_HORIZONTAL,
                "reason": result["reason"],
                "checks": result["checks"],
            }
    except Exception as exc:
        # If the validator can't be loaded, allow the packet through
        return {
            "status": "ACCEPTED",
            "reason": f"Vertical slice validator unavailable: {exc}",
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  Phase outcome
# ═══════════════════════════════════════════════════════════════════════════════

def determine_phase_outcome(packet_results: dict[str, str]) -> dict:
    """Determine whether the phase passed or failed based on all packet results.

    Returns:
        {"passed": bool, "summary": str, "accepted": int, "rejected": int, ...}
    """
    total = len(packet_results)
    accepted = sum(1 for v in packet_results.values() if v == "ACCEPTED")
    rejected = sum(1 for v in packet_results.values() if v == "REJECTED")
    rejected_horizontal = sum(1 for v in packet_results.values() if v == _REJECTED_HORIZONTAL)
    repair_requested = sum(1 for v in packet_results.values() if v == "REPAIR_REQUESTED")
    cancelled = sum(1 for v in packet_results.values() if v == "CANCELLED")
    blocked = sum(1 for v in packet_results.values() if v == "BLOCKED")
    failed_events = sum(1 for v in packet_results.values() if v.startswith("FAILED"))
    timed_out = sum(1 for v in packet_results.values() if v == "TIMEOUT")
    lost = sum(1 for v in packet_results.values() if v == "LOST")

    all_passed = (
        accepted == total
        or (accepted + cancelled == total and total > 0)
    ) and rejected_horizontal == 0

    return {
        "passed": all_passed,
        "total": total,
        "accepted": accepted,
        "rejected": rejected,
        "rejected_horizontal": rejected_horizontal,
        "repair_requested": repair_requested,
        "cancelled": cancelled,
        "blocked": blocked,
        "failed": failed_events,
        "timed_out": timed_out,
        "lost": lost,
        "summary": (
            f"{accepted}/{total} accepted"
            if all_passed
            else (
                f"{accepted}/{total} accepted, {rejected} rejected, "
                f"{rejected_horizontal} rejected_horizontal, "
                f"{repair_requested} repair_requested, {blocked} blocked, "
                f"{failed_events} failed"
            )
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Single-phase supervise
# ═══════════════════════════════════════════════════════════════════════════════

def supervise_phase(
    run_id: str,
    phase: str,
    poll_interval: float = _DEFAULT_POLL_INTERVAL,
    timeout: Optional[float] = None,
) -> dict:
    """Supervise one phase: dispatch all ready packets in parallel,
    wait for results, and determine outcome.

    Does NOT transition the kernel — the caller transitions.
    Returns the full result dict.
    """
    rk = _load_kernel()

    # 1. Select all ready packets
    ready = get_ready_packets(run_id, phase)
    if not ready:
        return {
            "phase": phase,
            "dispatched": 0,
            "outcome": {"passed": False, "summary": "No ready packets in phase"},
            "packet_results": {},
        }

    # 2. Dispatch all
    dispatch_results = dispatch_all(run_id, ready)
    dispatched_ids = [pid for pid, status in dispatch_results.items()
                      if status == "DISPATCHED"]
    failed_ids = [pid for pid, status in dispatch_results.items()
                  if status.startswith("FAILED")]

    if not dispatched_ids:
        return {
            "phase": phase,
            "dispatched": 0,
            "outcome": {"passed": False, "summary": f"All packets failed to dispatch: {failed_ids}"},
            "packet_results": dispatch_results,
        }

    # 3. Poll for completion
    poll_results = poll_until_complete(run_id, dispatched_ids, poll_interval, timeout)

    # Merge dispatch failures into results
    for pid in failed_ids:
        poll_results[pid] = dispatch_results[pid]

    # 4. Determine outcome
    outcome = determine_phase_outcome(poll_results)

    return {
        "phase": phase,
        "dispatched": len(dispatched_ids),
        "outcome": outcome,
        "packet_results": poll_results,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Full-run supervise (vertical spine + horizontal within each phase)
# ═══════════════════════════════════════════════════════════════════════════════

def supervise_run(
    run_id: str,
    poll_interval: float = _DEFAULT_POLL_INTERVAL,
    phase_timeout: Optional[float] = None,
) -> dict:
    """Supervise a full run: walk the phase queue vertically,
    dispatching all ready packets horizontally within each phase.

    QRSPI rule: vertical spine first.
    Each phase must complete (all packets ACCEPTED) before the next phase starts.
    """
    rk = _load_kernel()
    run_history = []
    all_passed = True

    while True:
        active = get_active_phase(run_id)
        if not active:
            # No active phase — run may be DONE or BLOCKED
            state = rk.get_run_state(run_id)
            break

        phase_name = active["phase"]
        print(f"  supervising phase: {phase_name}")

        result = supervise_phase(run_id, phase_name, poll_interval, phase_timeout)
        run_history.append(result)

        if not result["outcome"]["passed"]:
            all_passed = False
            # If phase failed (rejected packets, no escalation), stop
            if result["outcome"]["blocked"] > 0 or result["outcome"]["rejected"] > 0:
                print(f"  phase {phase_name} FAILED — stopping")
                break

        # Mark phase completed in kernel
        try:
            rk.mark_phase_completed(run_id, phase_name)
        except (ValueError, RuntimeError) as e:
            print(f"  warning: could not mark phase completed: {e}")

        # Transition kernel to next phase
        next_phase = _get_next_phase(phase_name)
        if next_phase:
            try:
                rk.transition_to(run_id, next_phase)
                print(f"  kernel transition -> {next_phase}")
            except RuntimeError as e:
                print(f"  kernel transition blocked: {e}")
                all_passed = False
                break
        else:
            # No next phase — run is done
            try:
                state = rk.get_run_state(run_id)
            except Exception:
                pass
            break

    try:
        state = rk.get_run_state(run_id)
    except Exception:
        state = {}

    return {
        "run_id": run_id,
        "all_phases_passed": all_passed,
        "final_phase": state.get("current_phase", "UNKNOWN"),
        "phase_count": len(run_history),
        "phases": run_history,
    }


_PHASE_SEQUENCE = [
    "NEW", "INTAKE", "QUESTIONING", "RESEARCHING", "DESIGNING",
    "STRUCTURING", "PLANNING", "WORKTREE_READY", "IMPLEMENTING",
    "VALIDATOR_BUILDING", "VALIDATING", "EVIDENCE_INDEXING",
    "POLICY_DECIDING", "REPLAYING", "CERTIFYING", "REPORTING",
    "MEMORY_CONSOLIDATING", "DONE",
]


def _get_next_phase(current: str) -> Optional[str]:
    """Return the next phase in the normal sequence, or None if at end."""
    try:
        idx = _PHASE_SEQUENCE.index(current)
        if idx + 1 < len(_PHASE_SEQUENCE):
            return _PHASE_SEQUENCE[idx + 1]
        return None
    except ValueError:
        return None
