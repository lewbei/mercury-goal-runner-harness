# .agentic-pi/runtime/auto_dispatcher.py
"""
Auto-Dispatcher Supervisor

Reads kernel work packets and auto-spawns agents by writing a spawn queue.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Path constants
_ROOT_DIR = Path(__file__).resolve().parent.parent  # .agentic-pi
_RUNS_DIR = _ROOT_DIR.parent / ".agentic-runs"
_SPAWN_QUEUE_PATH = _ROOT_DIR / "runtime" / "agent_spawn_queue.json"
_STATE_FILE = _ROOT_DIR / "runtime" / "auto_dispatcher_state.json"


def _now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> Dict[str, int]:
    """Load persistent state tracking last processed line per run."""
    if not _STATE_FILE.exists():
        return {}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.error("Failed to load state file %s: %s", _STATE_FILE, exc)
        return {}


def _save_state(state: Dict[str, int]) -> None:
    """Persist state to disk."""
    try:
        _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        logging.error("Failed to write state file %s: %s", _STATE_FILE, exc)


def _read_dispatch_log(run_dir: Path, start_line: int) -> List[Dict[str, Any]]:
    """Read dispatch_log.jsonl from start_line (0‑indexed) and return new records.

    Args:
        run_dir: Path to the run directory.
        start_line: Index of the first line to read (exclusive of previous reads).

    Returns:
        List of JSON objects representing new log entries.
    """
    log_path = run_dir / "dispatch_log.jsonl"
    if not log_path.is_file():
        logging.warning("Dispatch log missing for run %s", run_dir.name)
        return []

    records = []
    try:
        with log_path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i < start_line:
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logging.error(
                        "Malformed JSON in %s at line %d: %s", log_path, i + 1, exc
                    )
    except Exception as exc:
        logging.error("Failed to read dispatch log %s: %s", log_path, exc)
    return records


def _load_packet(run_dir: Path, packet_id: str) -> Optional[Dict[str, Any]]:
    """Load a work packet JSON file."""
    packet_path = run_dir / "work_packets" / f"{packet_id}.json"
    if not packet_path.is_file():
        logging.error("Packet file %s does not exist", packet_path)
        return None
    try:
        return json.loads(packet_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.error("Failed to parse packet %s: %s", packet_path, exc)
        return None


def _extract_agent_config(packet: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Extract required agent configuration from a packet.

    Expected keys:
        - subagent_type
        - model
        - prompt

    Returns:
        dict with keys subagent_type, model, prompt, or None if missing.
    """
    missing = []
    for key in ("subagent_type", "model", "prompt"):
        if key not in packet:
            missing.append(key)
    if missing:
        logging.error(
            "Packet %s missing required config fields: %s",
            packet.get("work_packet_id", "<unknown>"),
            ", ".join(missing),
        )
        return None
    return {
        "subagent_type": packet["subagent_type"],
        "model": packet["model"],
        "prompt": packet["prompt"],
    }


def _load_spawn_queue() -> List[Dict[str, Any]]:
    """Load the current spawn queue, returning an empty list if missing."""
    if not _SPAWN_QUEUE_PATH.is_file():
        return []
    try:
        return json.loads(_SPAWN_QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.error("Failed to load spawn queue %s: %s", _SPAWN_QUEUE_PATH, exc)
        return []


def _write_spawn_queue(entries: List[Dict[str, Any]]) -> None:
    """Write the spawn queue atomically."""
    try:
        _SPAWN_QUEUE_PATH.write_text(
            json.dumps(entries, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        logging.error("Failed to write spawn queue %s: %s", _SPAWN_QUEUE_PATH, exc)


def _update_spawn_entry(
    queue: List[Dict[str, Any]],
    packet_id: str,
    status: str,
) -> List[Dict[str, Any]]:
    """Update status of a specific entry, returning the updated queue."""
    updated = False
    for entry in queue:
        if entry.get("packet_id") == packet_id:
            entry["status"] = status
            entry["updated_at"] = _now_iso()
            updated = True
            break
    if not updated:
        # If entry does not exist, create a placeholder with minimal info.
        queue.append(
            {
                "packet_id": packet_id,
                "subagent_type": None,
                "model": None,
                "prompt": None,
                "run_id": None,
                "status": status,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )
    return queue

# ---------------------------------------------------------------------------
# Durable‑agent helper functions
# ---------------------------------------------------------------------------

def _packet_dir(run_dir: Path, packet_id: str) -> Path:
    """Return a dedicated directory for a packet (created on demand)."""
    pkt_dir = run_dir / "work_packets" / packet_id
    pkt_dir.mkdir(parents=True, exist_ok=True)
    return pkt_dir


def _load_checkpoint(pkt_dir: Path) -> List[int]:
    """Load checkpoint.json if it exists and return the list of completed steps.

    Returns an empty list when the file is missing or malformed.
    """
    ck_path = pkt_dir / "checkpoint.json"
    if not ck_path.is_file():
        return []
    try:
        data = json.loads(ck_path.read_text(encoding="utf-8"))
        steps = data.get("completed_steps", [])
        # Ensure we only return integers
        return [int(s) for s in steps if isinstance(s, (int, str)) and str(s).isdigit()]
    except Exception as exc:
        logging.error("Failed to read checkpoint %s: %s", ck_path, exc)
        return []


def _write_checkpoint(pkt_dir: Path, completed_steps: List[int]) -> None:
    """Write checkpoint.json with the given list of completed step numbers.
    """
    ck_path = pkt_dir / "checkpoint.json"
    payload = {"completed_steps": sorted(set(completed_steps))}
    try:
        ck_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        logging.error("Failed to write checkpoint %s: %s", ck_path, exc)


def _scan_step_logs(pkt_dir: Path) -> List[int]:
    """Inspect <packet_dir>/step_logs for *.json files named like "1.json".

    Returns a sorted list of step numbers that have a corresponding log file.
    """
    step_dir = pkt_dir / "step_logs"
    if not step_dir.is_dir():
        return []
    steps = []
    for entry in step_dir.iterdir():
        if entry.is_file() and entry.suffix == ".json":
            stem = entry.stem
            if stem.isdigit():
                steps.append(int(stem))
    return sorted(steps)


def _is_output_valid(file_path: Path) -> bool:
    """Validate that a file exists, is non‑empty, and (for JSON) is parseable.
    """
    if not file_path.is_file():
        return False
    try:
        if file_path.stat().st_size == 0:
            return False
        if file_path.suffix.lower() == ".json":
            json.loads(file_path.read_text(encoding="utf-8"))
        # For non‑JSON files we only require non‑empty content.
        return True
    except Exception as exc:
        logging.error("Invalid output file %s: %s", file_path, exc)
        return False


def _check_idempotent(packet: Dict[str, Any], run_dir: Path) -> bool:
    """Return True if all files listed in packet["expected_outputs"] are present and valid.
    """
    expected = packet.get("expected_outputs", [])
    if not isinstance(expected, list) or not expected:
        return False
    for rel_path in expected:
        out_path = run_dir / rel_path
        if not _is_output_valid(out_path):
            return False
    return True


def _modify_prompt_for_resume(original_prompt: str, completed_steps: List[int]) -> str:
    """Prefix the original prompt with a concise continuation instruction.

    Example prefix:
        "CONTINUE from step 3. Steps 1,2 already done. Read existing files before proceeding.\n\n"
    """
    if not completed_steps:
        return original_prompt
    next_step = max(completed_steps) + 1
    steps_str = ", ".join(str(s) for s in sorted(completed_steps))
    prefix = f"CONTINUE from step {next_step}. Steps {steps_str} already done. Read existing files before proceeding.\n\n"
    return prefix + original_prompt


def _update_checkpoint_for_packet(pkt_dir: Path) -> None:
    """Scan step logs and write the latest checkpoint.
    """
    steps = _scan_step_logs(pkt_dir)
    _write_checkpoint(pkt_dir, steps)


# ---------------------------------------------------------------------------
# Post-certify check: detect FAILED_CHECK and create repair packet
# ---------------------------------------------------------------------------

def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """Append a single JSON line to a JSONL file, creating it if necessary."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        logging.error("Failed to append to %s: %s", path, exc)


def _post_certify_check(run_dir: Path) -> None:
    """Check final_status.json after CERTIFYING phase completes.

    If the status is FAILED_CHECK, create a REPAIR work packet with the error message.
    """
    # Locate the final status file produced by the CERTIFYING phase
    status_path = run_dir / "final_status.json"
    if not status_path.is_file():
        # No status file – nothing to do
        return

    try:
        final_status = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        # Corrupt or unreadable status – abort the check
        return

    if final_status.get("status") == "DONE_PASS":
        return  # All good

    # Check if there are actual failures to repair
    failed = final_status.get("failed_checks", [])
    if not failed:
        return

    error_msg = "; ".join(failed)

    # ---------------------------------------------------------------------
    # Create a new work packet JSON file for the REPAIRING_IMPLEMENTATION phase
    # ---------------------------------------------------------------------
    packets_dir = run_dir / "work_packets"
    packets_dir.mkdir(parents=True, exist_ok=True)
    existing = list(packets_dir.glob("WP.REPAIRING_IMPLEMENTATION.*.json"))
    seq = len(existing) + 1
    packet_id = f"WP.REPAIRING_IMPLEMENTATION.{seq:03d}"

    packet = {
        "schema_version": "work_packet_v1",
        "work_packet_id": packet_id,
        "phase": "REPAIRING_IMPLEMENTATION",
        "role": "repair",
        "task": f"Repair after certification failure: {error_msg}",
        "subagent_type": "guarded-worker",
        "model": "deepseek/deepseek-v4-flash",
        "prompt": f"run_id={run_dir.name}. Repair: {error_msg}. Read the existing files first, then fix the issue. Write step_logs and trace.jsonl.",
        "input_artifacts": [],
        "input_summaries": {},
        "allowed_write_paths": [],
        "forbidden_write_paths": [
            "final_status.json",
            "final_status.md",
            "certification.json",
            "policy_decision.json",
            "evidence_freeze.json",
            "run_state.json",
            "phase_queue.json",
        ],
        "status": "PENDING",
        "max_model_calls": 3,
        "max_repair_attempts": 2,
        "repair_attempt_count": 0,
        "output_schema": "default_result.schema.json",
        "status_claim_allowed": False,
        "result_path": None,
        "validation_result_path": None,
        "error": None,
        "dispatch_timestamp": None,
        "result_timestamp": None,
        "dependencies": [],
        "accumulated_skills_context": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }

    packet_path = packets_dir / f"{packet_id}.json"
    packet_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")

    # ---------------------------------------------------------------------
    # Log the creation of the repair packet so the kernel can pick it up
    # ---------------------------------------------------------------------
    _append_jsonl(
        run_dir / "dispatch_log.jsonl",
        {
            "event": "work_packet_created",
            "run_id": run_dir.name,
            "work_packet_id": packet_id,
            "phase": "REPAIRING_IMPLEMENTATION",
            "role": "repair",
            "timestamp": _now_iso(),
        },
    )

    logging.info(
        "Post-certify check created repair packet %s for run %s",
        packet_id,
        run_dir.name,
    )

    # No return value – the function's side‑effects are the packet file and log entry


# ---------------------------------------------------------------------------
# Core event processing (augmented with durable logic + phase_transition hook)
# ---------------------------------------------------------------------------

def _process_new_events(
    run_dir: Path,
    new_events: List[Dict[str, Any]],
    spawn_queue: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Process newly read dispatch log events.

    For each `work_packet_created` event, extract config and add a pending entry.
    For each `work_packet_result_received` event, mark the entry as completed.
    For each `phase_transition` event, trigger post‑certify checks when CERTIFYING completes.
    """
    for event in new_events:
        ev_type = event.get("event")
        if ev_type == "work_packet_created":
            packet_id = event.get("work_packet_id")
            if not packet_id:
                logging.warning("work_packet_created event missing packet_id")
                continue
            packet = _load_packet(run_dir, packet_id)
            if not packet:
                continue
            # ----- Durable‑agent pre‑processing -----
            pkt_dir = _packet_dir(run_dir, packet_id)
            # 1) Idempotent check
            if _check_idempotent(packet, run_dir):
                # Mark as already completed – no need to spawn.
                entry = {
                    "packet_id": packet_id,
                    "subagent_type": packet.get("subagent_type"),
                    "model": packet.get("model"),
                    "prompt": packet.get("prompt"),
                    "run_id": run_dir.name,
                    "status": "already_completed",
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                }
                spawn_queue.append(entry)
                logging.info("Packet %s is idempotent – skipping dispatch", packet_id)
                # Still write a checkpoint (all steps considered done)
                _write_checkpoint(pkt_dir, [])
                continue
            # 2) Checkpoint‑based prompt modification
            completed = _load_checkpoint(pkt_dir)
            if completed:
                new_prompt = _modify_prompt_for_resume(packet.get("prompt", ""), completed)
            else:
                new_prompt = packet.get("prompt", "")
            # 3) Extract configuration (subagent_type, model, prompt)
            config = _extract_agent_config(packet)
            if not config:
                # Missing config – we deliberately do NOT add to the queue.
                continue
            # 4) Build spawn entry (use possibly modified prompt)
            entry = {
                "packet_id": packet_id,
                "subagent_type": config["subagent_type"],
                "model": config["model"],
                "prompt": new_prompt,
                "run_id": run_dir.name,
                "status": "pending",
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
            spawn_queue.append(entry)
            logging.info("Queued packet %s for spawning (status=pending)", packet_id)
            # 5) Update checkpoint after queuing (captures any step logs already present)
            _update_checkpoint_for_packet(pkt_dir)

        elif ev_type == "work_packet_result_received":
            packet_id = event.get("work_packet_id")
            if not packet_id:
                logging.warning("work_packet_result_received event missing packet_id")
                continue
            packet = _load_packet(run_dir, packet_id)
            if not packet:
                continue
            status = packet.get("status")
            new_status = "completed" if status == "ACCEPTED" else "failed"
            spawn_queue = _update_spawn_entry(spawn_queue, packet_id, new_status)
            logging.info(
                "Updated spawn entry %s to status %s", packet_id, new_status
            )

        elif ev_type == "phase_transition":
            # New handling: after CERTIFYING finishes, run the post‑certify check
            from_phase = event.get("from_phase")
            to_phase = event.get("to_phase")
            if from_phase == "CERTIFYING" and to_phase != "CERTIFYING":
                # The CERTIFYING phase has just completed
                _post_certify_check(run_dir)

        # Other events are ignored for now.
    return spawn_queue


def main() -> None:
    """Main entry point for the auto-dispatcher."""
    logging.info("Auto-Dispatcher started")
    state = _load_state()
    spawn_queue = _load_spawn_queue()

    # Accept optional run_dir from command line
    if len(sys.argv) >= 2:
        target_run_dir = Path(sys.argv[1]).resolve()
        if not target_run_dir.is_dir():
            logging.error("Run dir not found: %s", target_run_dir)
            return
        target_run_id = target_run_dir.name
    else:
        target_run_dir = None

    # Iterate over runs (filtered or all)
    for run_dir in sorted(_RUNS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        if target_run_dir is not None and run_dir.resolve() != target_run_dir:
            continue
        run_id = run_dir.name
        last_line = state.get(run_id, 0)
        new_events = _read_dispatch_log(run_dir, last_line)
        if not new_events:
            continue
        logging.info(
            "Run %s: %d new dispatch events (starting at line %d)",
            run_id,
            len(new_events),
            last_line,
        )
        spawn_queue = _process_new_events(run_dir, new_events, spawn_queue)
        # Update state with new line count
        state[run_id] = last_line + len(new_events)

    # Persist updated spawn queue and state
    _write_spawn_queue(spawn_queue)
    _save_state(state)
    logging.info("Auto-Dispatcher finished")


if __name__ == "__main__":
    main()
