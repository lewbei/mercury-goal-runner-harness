#!/usr/bin/env python3
import argparse
import shutil
import os
import json
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description="Copy goal contract into run folder")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument("--input", required=True, help="Path to goal_contract.json")
    args = parser.parse_args()
    run_dir = os.path.join(".agentic-runs", args.run_id)
    if not os.path.isdir(run_dir):
        raise FileNotFoundError(f"Run folder {run_dir} does not exist")
    dest = os.path.join(run_dir, "goal_contract.json")
    shutil.copyfile(args.input, dest)
    # Append trace event
    trace_path = os.path.join(run_dir, "trace.jsonl")
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": "goal_contract_added",
        "file": "goal_contract.json"
    }
    with open(trace_path, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(f"Copied goal contract to {dest}")

if __name__ == "__main__":
    main()
