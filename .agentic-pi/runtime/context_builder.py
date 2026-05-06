#!/usr/bin/env python3
"""Context Builder – creates a lightweight context packet for the Guarded Worker.

The context includes:
- Goal Contract (full)
- Current step (if any)
- Allowed tools (hard‑coded list)
- Forbidden paths (protected files)
- Last two step logs (if available)
- Done criteria from the contract

The output is written as JSON to <run_dir>/context.json.
"""
import argparse
import json
from pathlib import Path

ALLOWED_TOOLS = ["read", "ls", "grep", "find", "bash"]
FORBIDDEN_PATHS = [
    ".agentic-pi/state.json",
    "trace.jsonl",
    "certification.json",
    "final_status.md"
]


def load_json(path: Path):
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Build context for a run")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    args = parser.parse_args()
    run_dir = Path(".agentic-runs") / args.run_id
    contract_path = run_dir / "goal_contract.json"
    if not contract_path.is_file():
        raise FileNotFoundError(f"Goal contract not found at {contract_path}")
    contract = load_json(contract_path)

    # Load last two step logs if they exist
    step_logs_dir = run_dir / "step_logs"
    recent_steps = []
    if step_logs_dir.is_dir():
        logs = sorted(step_logs_dir.glob("*.json"))
        for log_path in logs[-2:]:
            try:
                recent_steps.append(load_json(log_path))
            except Exception:
                continue

    context = {
        "run_id": args.run_id,
        "goal_contract": contract,
        "allowed_tools": ALLOWED_TOOLS,
        "forbidden_paths": FORBIDDEN_PATHS,
        "recent_steps": recent_steps,
        "done_criteria": contract.get("done_criteria", []),
    }
    out_path = run_dir / "context.json"
    out_path.write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Context written to {out_path}")

if __name__ == "__main__":
    main()
