#!/usr/bin/env python3
"""Long-horizon support for multi-hour tasks.

Provides checkpoint mechanism, progress tracking, and resume capability
for tasks that span hours. This addresses the MEDIUM priority gap from
the planning analysis (task duration doubling every 7 months).

The long-horizon manager:
1. Creates checkpoints at key milestones
2. Tracks progress across steps
3. Provides resume capability for interrupted tasks
4. Logs progress metrics

It does NOT certify DONE. It does NOT write final_status.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = ROOT / ".agentic-runs"
STATUS_ARTIFACTS = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}


class LongHorizonError(RuntimeError):
    """Raised when long-horizon manager cannot continue safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        if default is not None:
            return default
        raise


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def resolve_run_dir(raw: str | None, run_id: str | None) -> Path:
    if raw:
        p = Path(raw)
        if p.is_dir():
            return p.resolve()
    if run_id:
        p = RUNS_ROOT / run_id
        if p.is_dir():
            return p.resolve()
    raise LongHorizonError("Provide --run-dir or --run-id with an existing run folder.")


def load_run_state(run_dir: Path) -> dict:
    """Load run state from run_state.json."""
    state_path = run_dir / "run_state.json"
    if not state_path.exists():
        return {}
    return load_json(state_path, {})


def load_merged_plan(run_dir: Path) -> dict:
    """Load merged plan from merged_plan.json."""
    plan_path = run_dir / "merged_plan.json"
    if not plan_path.exists():
        return {}
    return load_json(plan_path, {})


def load_step_logs(run_dir: Path) -> list[dict]:
    """Load step logs from step_logs directory."""
    step_logs_dir = run_dir / "step_logs"
    if not step_logs_dir.exists():
        return []
    
    logs = []
    for log_file in sorted(step_logs_dir.glob("*.json")):
        try:
            log = load_json(log_file)
            logs.append(log)
        except Exception:
            pass
    return logs


def calculate_progress(step_logs: list[dict], total_steps: int) -> dict:
    """Calculate progress from step logs."""
    completed_steps = len(step_logs)
    failed_steps = sum(1 for log in step_logs if log.get("status") == "FAILED")
    passed_steps = sum(1 for log in step_logs if log.get("status") == "PASSED")
    
    if total_steps == 0:
        percentage = 0.0
    else:
        percentage = (completed_steps / total_steps) * 100
    
    return {
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "passed_steps": passed_steps,
        "failed_steps": failed_steps,
        "percentage": round(percentage, 2),
        "remaining_steps": max(0, total_steps - completed_steps),
    }


def create_checkpoint(run_dir: Path, step_id: int, status: str, details: dict = None) -> dict:
    """Create a checkpoint at a key milestone."""
    checkpoint = {
        "checkpoint_id": f"checkpoint_{step_id}_{int(datetime.now().timestamp())}",
        "step_id": step_id,
        "status": status,
        "timestamp": utc_now(),
        "details": details or {},
    }
    
    # Write checkpoint file
    checkpoint_dir = run_dir / "checkpoints"
    checkpoint_dir.mkdir(exist_ok=True)
    checkpoint_path = checkpoint_dir / f"checkpoint_{step_id}.json"
    write_json(checkpoint_path, checkpoint)
    
    return checkpoint


def load_checkpoints(run_dir: Path) -> list[dict]:
    """Load all checkpoints."""
    checkpoint_dir = run_dir / "checkpoints"
    if not checkpoint_dir.exists():
        return []
    
    checkpoints = []
    for checkpoint_file in sorted(checkpoint_dir.glob("checkpoint_*.json")):
        try:
            checkpoint = load_json(checkpoint_file)
            checkpoints.append(checkpoint)
        except Exception:
            pass
    return checkpoints


def get_last_checkpoint(run_dir: Path) -> dict | None:
    """Get the last checkpoint."""
    checkpoints = load_checkpoints(run_dir)
    if not checkpoints:
        return None
    return checkpoints[-1]


def calculate_eta(progress: dict, step_logs: list[dict]) -> dict:
    """Calculate estimated time remaining."""
    if not step_logs or progress["remaining_steps"] == 0:
        return {"eta_seconds": 0, "eta_human": "0s"}
    
    # Calculate average time per step
    timestamps = []
    for log in step_logs:
        if "timestamp" in log:
            try:
                ts = datetime.fromisoformat(log["timestamp"])
                timestamps.append(ts)
            except Exception:
                pass
    
    if len(timestamps) < 2:
        return {"eta_seconds": None, "eta_human": "unknown"}
    
    # Calculate average time between steps
    time_diffs = []
    for i in range(1, len(timestamps)):
        diff = (timestamps[i] - timestamps[i-1]).total_seconds()
        time_diffs.append(diff)
    
    if not time_diffs:
        return {"eta_seconds": None, "eta_human": "unknown"}
    
    avg_time_per_step = sum(time_diffs) / len(time_diffs)
    eta_seconds = avg_time_per_step * progress["remaining_steps"]
    
    # Format as human-readable
    if eta_seconds < 60:
        eta_human = f"{int(eta_seconds)}s"
    elif eta_seconds < 3600:
        eta_human = f"{int(eta_seconds / 60)}m"
    else:
        hours = int(eta_seconds / 3600)
        minutes = int((eta_seconds % 3600) / 60)
        eta_human = f"{hours}h {minutes}m"
    
    return {"eta_seconds": round(eta_seconds, 2), "eta_human": eta_human}


def run_long_horizon_manager(run_dir: Path) -> dict:
    """Run long-horizon management analysis."""
    # Load run state
    run_state = load_run_state(run_dir)
    
    # Load merged plan
    merged_plan = load_merged_plan(run_dir)
    total_steps = len(merged_plan.get("steps", []))
    
    # Load step logs
    step_logs = load_step_logs(run_dir)
    
    # Calculate progress
    progress = calculate_progress(step_logs, total_steps)
    
    # Load checkpoints
    checkpoints = load_checkpoints(run_dir)
    last_checkpoint = get_last_checkpoint(run_dir)
    
    # Calculate ETA
    eta = calculate_eta(progress, step_logs)
    
    # Determine status
    if progress["failed_steps"] > 0:
        status = "FAILED"
    elif progress["percentage"] >= 100:
        status = "COMPLETED"
    elif progress["percentage"] > 0:
        status = "IN_PROGRESS"
    else:
        status = "NOT_STARTED"
    
    return {
        "timestamp": utc_now(),
        "run_id": run_state.get("run_id", "unknown"),
        "current_phase": run_state.get("current_phase", "unknown"),
        "status": status,
        "progress": progress,
        "checkpoints": checkpoints,
        "last_checkpoint": last_checkpoint,
        "eta": eta,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Long-horizon support for multi-hour tasks.")
    parser.add_argument("--run-dir", help="Path to the run directory")
    parser.add_argument("--run-id", help="Run identifier (resolved under .agentic-runs/)")
    parser.add_argument("--output", help="Output path for progress JSON")
    parser.add_argument("--checkpoint", type=int, help="Create checkpoint at step ID")
    parser.add_argument("--status", action="store_true", help="Show progress status")
    args = parser.parse_args(argv)

    try:
        run_dir = resolve_run_dir(args.run_dir, args.run_id)
    except LongHorizonError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Create checkpoint if requested
    if args.checkpoint is not None:
        checkpoint = create_checkpoint(run_dir, args.checkpoint, "MILESTONE")
        print(f"Created checkpoint: {checkpoint['checkpoint_id']}")
        return 0

    # Run long-horizon manager
    result = run_long_horizon_manager(run_dir)
    
    # Write result
    output_path = Path(args.output) if args.output else run_dir / "long_horizon_status.json"
    write_json(output_path, result)
    
    # Print status
    if args.status or True:  # Always print status
        progress = result["progress"]
        print(f"Run: {result['run_id']}")
        print(f"Phase: {result['current_phase']}")
        print(f"Status: {result['status']}")
        print(f"Progress: {progress['completed_steps']}/{progress['total_steps']} ({progress['percentage']}%)")
        print(f"  Passed: {progress['passed_steps']}")
        print(f"  Failed: {progress['failed_steps']}")
        print(f"  Remaining: {progress['remaining_steps']}")
        
        if result["eta"]["eta_human"] != "0s":
            print(f"ETA: {result['eta']['eta_human']}")
        
        if result["last_checkpoint"]:
            print(f"Last checkpoint: {result['last_checkpoint']['checkpoint_id']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
