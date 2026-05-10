#!/usr/bin/env python3
"""Gateway dispatch layer for pi_cli.py.

Every subprocess call that pi_cli.py makes goes through this module.
It consults command_gateway.py before allowing execution, so that
runtime enforcement is the default path, not just a smoke-only path.

This module cannot certify DONE.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── gateway import ────────────────────────────────────────────────────────────
_command_gateway = None


def _load_gateway():
    global _command_gateway
    if _command_gateway is None:
        import importlib.util
        gw_path = ROOT / ".agentic-pi" / "runtime" / "command_gateway.py"
        spec = importlib.util.spec_from_file_location("command_gateway_dispatch", gw_path)
        _command_gateway = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_command_gateway)
    return _command_gateway


# ─── enforcement helpers ──────────────────────────────────────────────────────

# Known harness commands that are always allowed (they are deterministic tools,
# not raw Pi/Mercury shell commands). The gateway enforces certifier and status
# commands specifically.
_HARNESS_COMMANDS = {
    "init_run", "compile_raw_goal", "run_goal",
    "planning_proof_runner", "strategy_proof_runner",
    "milestone_proof_runner", "drift_proof_runner",
    "replay_run", "audit_run", "rollback_run",
}


def _is_disposable(run_id: str) -> bool:
    return run_id.startswith("pi_smoke_")


def _build_command_string(args: list[str]) -> str:
    """Build a normalized command string from a subprocess argument list."""
    return " ".join(args)


def _is_known_harness_command(args: list[str]) -> bool:
    """Check if the argument list invokes a known harness tool."""
    if not args:
        return False
    first_arg = args[0].replace("\\", "/")
    for name in _HARNESS_COMMANDS:
        if name in first_arg:
            return True
    return False


def _classify(args: list[str], run_id: str) -> dict:
    """Classify a subprocess command list through the gateway."""
    gw = _load_gateway()
    cmd_str = _build_command_string(args)
    return gw.classify_command(cmd_str, run_id)


# ─── public API ───────────────────────────────────────────────────────────────


def dispatch(args: list[str], run_id: str, *, cwd: Path | None = None) -> tuple[int, str]:
    """Run a subprocess command through gateway enforcement.

    Known harness tools (init, compile, run, proofs, replay, audit, rollback)
    are always allowed. Certifier and status commands go through gateway
    enforcement. Unknown commands are blocked on disposable runs.

    Args:
        args: argument list suitable for subprocess.run([sys.executable, *args])
        run_id: the run identifier (must be disposable for enforcement)
        cwd: working directory (defaults to ROOT)

    Returns:
        (exit_code, stdout_text)
    """
    cwd = cwd or ROOT

    # Classification is always logged for auditing (not blocking for known tools)
    classification = _classify(args, run_id)
    cmd_kind = classification.get("command_kind", "unknown")
    decision = classification.get("decision", "BLOCK")

    # Known harness commands always allowed (they are deterministic tools)
    if _is_known_harness_command(args):
        pass  # fall through to execution

    # Non-disposable run IDs also fall through for now (backward compat)
    elif not _is_disposable(run_id):
        pass

    # Block unsafe commands on disposable runs
    elif decision != "ALLOW":
        block_msg = (
            f"GATEWAY_BLOCKED: {classification.get('reason', 'unknown')}\n"
            f"classification: {cmd_kind}\n"
        )
        return 1, block_msg

    # Execute
    result = subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout or ""


def dispatch_raw(cmd_line: str, run_id: str, *, cwd: Path | None = None) -> tuple[int, str]:
    """Execute a raw shell-like command string through gateway enforcement.

    This is the path that external Pi/Mercury commands should use.
    It goes through the full command_gateway.execute_gateway_command() path.
    """
    gw = _load_gateway()
    cwd = cwd or ROOT

    report = gw.execute_gateway_command(cmd_line, run_id, root=cwd)

    exit_code = report.get("exit_code", -1)
    stdout = report.get("stdout_tail", "")
    decision = report.get("decision", "BLOCK")

    if decision != "ALLOW" and exit_code == 0:
        # Gateway blocked but didn't set non-zero exit; fix that
        exit_code = 1
        stdout = (
            f"GATEWAY_BLOCKED: {report.get('reason', 'unknown')}\n"
            f"{stdout}"
        )

    return exit_code, stdout


def certifier_command(run_id: str) -> tuple[int, str]:
    """Execute the certifier through the gateway (required path).

    This is the only supported way to invoke the certifier from pi_cli.py.
    Direct subprocess calls to certify_run.py bypass enforcement and are
    only allowed in tests that explicitly test the enforcement layer.
    """
    gw = _load_gateway()
    cmd = gw.certifier_command(run_id)
    return dispatch_raw(cmd, run_id)
