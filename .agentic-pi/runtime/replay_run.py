#!/usr/bin/env python3
"""Replay a completed run and summarize its contents.

Usage:
    python .agentic-pi/runtime/replay_run.py --run-id <run_id>
"""
import argparse
import json
import os
from pathlib import Path


def load_json(path):
    if not path.is_file():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Replay a run and summarize its state")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    args = parser.parse_args()
    run_dir = Path(".agentic-runs") / args.run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run folder {run_dir} does not exist")
    print(f"--- Replay of run {args.run_id} ---")
    # Goal contract
    contract = load_json(run_dir / "goal_contract.json")
    if contract:
        print("Goal Contract:")
        print(json.dumps(contract, indent=2))
    else:
        print("No goal_contract.json found.")
    # Step logs
    step_logs_dir = run_dir / "step_logs"
    if step_logs_dir.is_dir():
        step_files = sorted(step_logs_dir.glob("*.json"))
        print(f"Step logs ({len(step_files)}):")
        for f in step_files:
            print(f"  - {f.name}")
    else:
        print("No step_logs directory.")
    # Trace
    trace_path = run_dir / "trace.jsonl"
    if trace_path.is_file():
        with open(trace_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        print(f"Trace events: {len(lines)}")
    else:
        print("No trace.jsonl found.")
    # Certification
    cert = load_json(run_dir / "certification.json")
    if cert:
        print("Certification:")
        print(json.dumps(cert, indent=2))
    else:
        print("No certification.json found.")
    print("--- End of replay ---")

if __name__ == "__main__":
    main()
