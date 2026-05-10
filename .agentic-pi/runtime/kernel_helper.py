#!/usr/bin/env python3
"""Kernel helper for pipeline tools.

Small shared module that pipeline tools (plan_router, guarded_worker, etc.)
can import to verify kernel state and write dispatch log entries.

Usage:
    from kernel_helper import verify_run, log_dispatch
"""

import json
import sys
from pathlib import Path
from typing import Optional

_RUNTIME_DIR = Path(__file__).resolve().parent
_RUN_KERNEL_PATH = _RUNTIME_DIR.parent / "run_kernel" / "run_kernel.py"

if str(_RUN_KERNEL_PATH.parent) not in sys.path:
    sys.path.insert(0, str(_RUN_KERNEL_PATH.parent))

_rk = None


def _get_rk():
    global _rk
    if _rk is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("run_kernel", _RUN_KERNEL_PATH)
        _rk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_rk)
    return _rk


def verify_run(run_id: str) -> Path:
    """Verify a run exists in the kernel and return its directory.

    Raises FileNotFoundError if the run doesn't exist.
    """
    rk = _get_rk()
    try:
        state = rk.get_run_state(run_id)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Run '{run_id}' has no run_state.json. "
            f"Use init_run.py to create it via the Run Kernel."
        )
    return rk.get_run_dir(run_id)


def log_dispatch(run_id: str, tool_name: str, status: str = "started",
                 detail: Optional[str] = None):
    """Write a dispatch log entry for a tool's activity."""
    rk = _get_rk()
    run_dir = rk.get_run_dir(run_id)
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

    log_path = run_dir / "dispatch_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_run_dir(run_id: str) -> Path:
    """Get the run directory path from the kernel."""
    rk = _get_rk()
    return rk.get_run_dir(run_id)
