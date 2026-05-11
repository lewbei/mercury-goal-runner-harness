#!/usr/bin/env python3
import argparse
import importlib.util
import os
import json
from datetime import datetime, timezone
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parent
PROVENANCE_PATH = RUNTIME_DIR / "prompt_provenance.py"

def _record_prompt_provenance(run_dir: str) -> None:
    spec = importlib.util.spec_from_file_location("prompt_provenance", PROVENANCE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.record_prompt_provenance(
        Path(run_dir),
        source_agent="write_goal_contract.py",
        source_model="deterministic-local",
        source_phase="goal_contract_write",
    )


def main():
    parser = argparse.ArgumentParser(description="Copy goal contract into run folder")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument("--input", required=True, help="Path to goal_contract.json")
    args = parser.parse_args()
    run_dir = os.path.join(".agentic-runs", args.run_id)
    if not os.path.isdir(run_dir):
        raise FileNotFoundError(f"Run folder {run_dir} does not exist")
    dest = os.path.join(run_dir, "goal_contract.json")
    with open(args.input, encoding="utf-8-sig") as f:
        contract = json.load(f)
    contract["run_id"] = args.run_id
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(contract, f, indent=2, ensure_ascii=False)
        f.write("\n")
    # Append trace event
    trace_path = os.path.join(run_dir, "trace.jsonl")
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "goal_contract_added",
        "file": "goal_contract.json"
    }
    with open(trace_path, "a") as f:
        f.write(json.dumps(event) + "\n")
    _record_prompt_provenance(run_dir)
    print(f"Copied goal contract to {dest}")
    print(f"Prompt provenance written to {os.path.join(run_dir, 'prompt_provenance', 'prompt_compiler.prompt.json')}")

if __name__ == "__main__":
    main()
