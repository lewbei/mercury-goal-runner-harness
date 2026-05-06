#!/usr/bin/env python3
"""Run a benchmark suite of goal contracts.

The script iterates over all JSON files in .agentic-pi/benchmark/goals/, creates a run for each, executes the full pipeline, and collects metrics.

Metrics collected per goal:
- run_id
- goal_file
- final_status (DONE_PASS / DONE_FAIL / BLOCKED / NEED_USER / MAX_STEPS_REACHED)
- step_count
- passed (bool)
- execution_time_seconds

All metrics are written to `benchmark_metrics.json` and a human‑readable markdown report `benchmark_report.md`.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent  # project root
RUNS_DIR = BASE_DIR / ".agentic-runs"
GOAL_DIR = BASE_DIR / ".agentic-pi" / "benchmark" / "goals"
# Benchmark outputs are now written to a dedicated folder to avoid polluting the repo root.
BENCHMARK_OUTPUT_DIR = BASE_DIR / "benchmark_outputs"
BENCHMARK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
METRICS_PATH = BENCHMARK_OUTPUT_DIR / "benchmark_metrics.json"
REPORT_PATH = BENCHMARK_OUTPUT_DIR / "benchmark_report.md"


def expected_status_for(goal_name: str, contract: dict) -> str:
    if contract.get("complexity_level", "").upper() == "RISKY":
        return "DONE_FAIL"
    if goal_name == "impossible_goal":
        return "DONE_FAIL"
    return "DONE_PASS"


def run_cmd(cmd, cwd=None):
    """Run a command, raise on failure, return stdout."""
    result = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command {' '.join(cmd)} failed (code {result.returncode}):\n{result.stdout}")
    return result.stdout


def load_status(run_dir: Path) -> str:
    """Read final_status.md and extract the status line (first line after '# Final Status:')."""
    status_file = run_dir / "final_status.md"
    if not status_file.is_file():
        return "UNKNOWN"
    with status_file.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("# Final Status:"):
                return line.split(":", 1)[1].strip()
    return "UNKNOWN"


def count_steps(run_dir: Path) -> int:
    """Count JSON step logs in step_logs/."""
    step_dir = run_dir / "step_logs"
    if not step_dir.is_dir():
        return 0
    return len(list(step_dir.glob("*.json")))


def main():
    parser = argparse.ArgumentParser(description="Run benchmark suite")
    parser.add_argument(
        "--run-dir",
        default=str(RUNS_DIR),
        help="Base directory for runs. Only the default .agentic-runs path is supported.",
    )
    args = parser.parse_args()
    base_runs_dir = Path(args.run_dir)
    if base_runs_dir.resolve() != RUNS_DIR.resolve():
        raise ValueError(
            "Custom --run-dir is not supported because the runtime writes to .agentic-runs. "
            "Use the default path for benchmark source-of-truth runs."
        )
    base_runs_dir.mkdir(parents=True, exist_ok=True)

    metrics = []
    start_suite = time.time()
    for goal_path in sorted(GOAL_DIR.glob("*.json")):
        goal_name = goal_path.stem
        # Load contract to get its run_id (we will override with unique one)
        with goal_path.open(encoding="utf-8-sig") as f:
            contract = json.load(f)
        # Unique run identifier
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        run_id = f"benchmark_{goal_name}_{timestamp}"
        print(f"\n=== Running benchmark for {goal_name} as {run_id} ===")
        # 1. init run
        run_cmd(["python", ".agentic-pi/runtime/init_run.py", "--run-id", run_id], cwd=BASE_DIR)
        # 2. write contract (copy)
        run_cmd(["python", ".agentic-pi/runtime/write_goal_contract.py", "--run-id", run_id, "--input", str(goal_path)], cwd=BASE_DIR)
        run_dir = base_runs_dir / run_id
        # If the goal is HARD, create a sample CSV for the script to consume.
        if contract.get("complexity_level", "").upper() == "HARD":
            csv_path = run_dir / "data.csv"
            csv_path.write_text("col1,col2\n1,2\n3,4\n", encoding="utf-8")
        # 3. execute full pipeline
        raw_execution_error = None
        try:
            run_cmd(
                [
                    "python",
                    ".agentic-pi/runtime/run_goal.py",
                    "Run benchmark",
                    "--run-id",
                    run_id,
                    "--skip-memory-update",
                ],
                cwd=BASE_DIR,
            )
        except Exception as e:
            raw_execution_error = str(e)
        # 4. collect metrics
        status = load_status(run_dir)
        steps = count_steps(run_dir)
        expected_status = expected_status_for(goal_name, contract)
        status_match = status == expected_status
        false_pass = status == "DONE_PASS" and expected_status != "DONE_PASS"
        execution_error = None if status_match else raw_execution_error
        if execution_error:
            print(f"Run failed unexpectedly for {run_id}: {execution_error}")
        metrics.append({
            "run_id": run_id,
            "goal_file": str(goal_path),
            "final_status": status,
            "actual_status": status,
            "expected_status": expected_status,
            "step_count": steps,
            "status_match": status_match,
            "false_pass": false_pass,
            "passed": status_match,
            "execution_error": execution_error,
        })

    # Write metrics JSON
    METRICS_PATH.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    # Write markdown report
    total = len(metrics)
    passed_cnt = sum(1 for m in metrics if m["passed"])
    report_content = f"""# Benchmark Report
Generated on {datetime.now(timezone.utc).isoformat()}
Total runs: {total}
Passed: {passed_cnt} / {total}

| Run ID | Goal File | Actual Status | Expected Status | Steps | Status Match | False PASS |
|---|---|---|---|---|---|---|
"""
    for m in metrics:
        report_content += f"| {m['run_id']} | {Path(m['goal_file']).name} | {m['actual_status']} | {m['expected_status']} | {m['step_count']} | {m['status_match']} | {m['false_pass']} |\n"
    REPORT_PATH.write_text(report_content, encoding="utf-8")
    print(f"\nBenchmark complete. Metrics written to {METRICS_PATH}, report to {REPORT_PATH}")

if __name__ == "__main__":
    main()
