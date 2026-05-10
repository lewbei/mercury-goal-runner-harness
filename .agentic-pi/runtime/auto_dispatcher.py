# .agentic-pi/runtime/auto_dispatcher.py
"""
Auto-Dispatcher Supervisor

Reads kernel work packets and auto-spawns agents by writing a spawn queue.
"""

import json
import logging
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
    """Read dispatch_log.jsonl from start_line (0-indexed) and return new records.

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


def _process_new_events(
    run_dir: Path,
    new_events: List[Dict[str, Any]],
    spawn_queue: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Process newly read dispatch log events.

    For each `work_packet_created` event, extract config and add a pending entry.
    For each `work_packet_result_received` event, mark the entry as completed.
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
            config = _extract_agent_config(packet)
            if not config:
                # Missing config – we deliberately do NOT add to the queue.
                continue
            entry = {
                "packet_id": packet_id,
                "subagent_type": config["subagent_type"],
                "model": config["model"],
                "prompt": config["prompt"],
                "run_id": run_dir.name,
                "status": "pending",
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
            spawn_queue.append(entry)
            logging.info("Queued packet %s for spawning", packet_id)

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
