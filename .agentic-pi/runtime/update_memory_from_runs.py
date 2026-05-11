#!/usr/bin/env python3
"""Validate/initialize advisory memory after a run.

This command no longer republishes every historical certification check into
flat JSONL memory files. Durable memory promotion is owned by memory_write_gate.py,
and run-local/quarantine memory stays inside each run folder.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".agentic-pi" / "runtime"
VALIDATORS = ROOT / ".agentic-pi" / "validators"
MEMORY_DIR = ROOT / ".agentic-pi" / "memory"


def run(cmd: list[str], label: str) -> bool:
    result = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(f"[{label}] exit={result.returncode}")
    if result.stdout:
        print(result.stdout.strip())
    return result.returncode == 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate advisory memory boundaries without flat-store republishing.")
    parser.add_argument("--run-dir", default="", help="Optional run directory whose memory/ files should be validated")
    args = parser.parse_args(argv)

    ok = run([sys.executable, str(RUNTIME / "mempalace_adapter.py"), "--memory-root", str(MEMORY_DIR), "--init"], "mempalace_init")
    ok &= run([sys.executable, str(RUNTIME / "mempalace_adapter.py"), "--memory-root", str(MEMORY_DIR), "--list-cards"], "mempalace_list_cards")

    if args.run_dir:
        run_dir = Path(args.run_dir)
        ok &= run([sys.executable, str(VALIDATORS / "validate_run_local_memory.py"), str(run_dir)], "validate_run_local_memory")
        ok &= run([sys.executable, str(VALIDATORS / "validate_quarantine_memory.py"), str(run_dir)], "validate_quarantine_memory")

    print("Memory update completed without writing removed flat memory stores.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
