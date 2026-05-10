#!/usr/bin/env python3
"""Initialize a new run folder using the Run Kernel.

This is the entry point for creating runs. It delegates to
run_kernel.create_run() so the kernel owns run_state.json.
"""

import argparse
import sys
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parent
RUN_KERNEL_PATH = RUNTIME_DIR.parent / "run_kernel" / "run_kernel.py"

if str(RUN_KERNEL_PATH.parent) not in sys.path:
    sys.path.insert(0, str(RUN_KERNEL_PATH.parent))


def main():
    parser = argparse.ArgumentParser(description="Initialize a new run folder via the Run Kernel")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument("--goal-contract", help="Path to goal contract file (optional)")
    args = parser.parse_args()

    # Import and delegate to the Run Kernel
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_kernel", RUN_KERNEL_PATH)
    rk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rk)

    try:
        run_dir = rk.create_run(args.run_id, goal_contract_path=args.goal_contract)
        print(f"Run '{args.run_id}' initialized via Run Kernel at {run_dir}")
        print(f"Initial state: {rk.get_run_state(args.run_id)['current_phase']}")
    except FileExistsError:
        print(f"Run '{args.run_id}' already exists. Resume or use a different run-id.")
        sys.exit(1)


if __name__ == "__main__":
    main()
