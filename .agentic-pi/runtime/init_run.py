#!/usr/bin/env python3
import os
import argparse
import json
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description="Initialize a new run folder")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    args = parser.parse_args()
    run_id = args.run_id
    base_dir = os.path.join(".agentic-runs", run_id)
    os.makedirs(os.path.join(base_dir, "step_logs"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "artifacts"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "backups"), exist_ok=True)
    # Write run.json
    run_info = {
        "run_id": run_id,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    with open(os.path.join(base_dir, "run.json"), "w") as f:
        json.dump(run_info, f, indent=2)
    # Initialize trace.jsonl
    open(os.path.join(base_dir, "trace.jsonl"), "a").close()
    print(f"Initialized run folder at {base_dir}")

if __name__ == "__main__":
    main()
