import argparse
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CASES_DIR = Path(__file__).resolve().parent / "cases"
HOST_RUNNER = ROOT / ".agentic-pi" / "runtime" / "host_task_runner.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_report(path: Path, metrics):
    lines = [
        "# Host Integration Diagnostic Report",
        "",
        "| Task | Expected Result | Actual Result | Observed Status | Violations |",
        "|---|---|---|---|---|",
    ]
    for row in metrics["cases"]:
        violations = "; ".join(row["violations"]) if row["violations"] else "none"
        lines.append(
            f"| {row['task_id']} | {row['expected_result']} | {row['status']} | "
            f"{row['observed_status'] or 'MISSING'} | {violations} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_evaluation(output_dir: Path):
    runner = load_module("host_task_runner_for_evaluation", HOST_RUNNER)
    rows = []
    false_certified_done = 0
    expected_failures_caught = 0

    for task_path in sorted(CASES_DIR.glob("*/host_task.json")):
        task = json.loads(task_path.read_text(encoding="utf-8-sig"))
        result = runner.evaluate_task(task_path)
        row = {
            **result,
            "expected_result": task["expected_result"],
        }
        rows.append(row)
        if result["observed_status"] == "CERTIFIED_DONE" and task["expected_status"] != "CERTIFIED_DONE":
            false_certified_done += 1
        if task["expected_result"] == "FAIL" and result["status"] == "FAIL":
            expected_failures_caught += 1

    mismatches = [
        row for row in rows
        if row["status"] != row["expected_result"]
    ]
    metrics = {
        "total_cases": len(rows),
        "status_match": not mismatches,
        "false_certified_done_count": false_certified_done,
        "expected_failures_caught": expected_failures_caught,
        "cases": rows,
    }

    write_json(output_dir / "host_integration_metrics.json", metrics)
    write_report(output_dir / "host_integration_report.md", metrics)
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run host integration diagnostics.")
    parser.add_argument("--output-dir", default="diagnostic_outputs/host_integration")
    args = parser.parse_args(argv)

    metrics = run_evaluation(ROOT / args.output_dir)
    print(
        "Host integration evaluation complete. "
        f"Status match = {metrics['status_match']}. "
        f"False CERTIFIED_DONE count = {metrics['false_certified_done_count']}"
    )
    return 0 if metrics["status_match"] and metrics["false_certified_done_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
