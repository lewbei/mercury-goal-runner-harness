#!/usr/bin/env python3
"""Run the v0.4 small diagnostic certification evaluation."""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CASES_DIR = Path(__file__).resolve().parent / "cases"
RUN_ROOT = ROOT / ".agentic-runs"
DEFAULT_OUTPUT_DIR = ROOT / "diagnostic_outputs"

MODES = [
    "file_existence",
    "artifact_test",
    "provenance_gate",
    "policy_engine",
]

PROVENANCE_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute path is not allowed: {raw_path}")
    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {raw_path}")
    return resolved


def split_command(cmd: str):
    parts = shlex.split(cmd, posix=(os.name != "nt"))
    if parts and parts[0].lower() in {"python", "python.exe"}:
        parts[0] = sys.executable
    return parts


def rewrite_json_run_id(path: Path, run_id: str):
    if not path.exists():
        return
    obj = load_json(path)
    obj["run_id"] = run_id
    write_json(path, obj)


def copy_case_to_run(case_dir: Path, run_id: str) -> Path:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    run_dir = RUN_ROOT / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    shutil.copytree(case_dir, run_dir)

    rewrite_json_run_id(run_dir / "goal_contract.json", run_id)
    rewrite_json_run_id(run_dir / "verifier_contract.json", run_id)
    for path in sorted((run_dir / "step_logs").glob("*.json")):
        rewrite_json_run_id(path, run_id)
    for path in sorted((run_dir / "verifier_artifacts").glob("*.json")):
        rewrite_json_run_id(path, run_id)

    return run_dir


def target_artifacts_exist(run_dir: Path, targets: list) -> bool:
    for target in targets:
        try:
            if not resolve_run_path(run_dir, target).is_file():
                return False
        except ValueError:
            return False
    return True


def run_artifact_tests(run_dir: Path, tests: list) -> tuple:
    if not tests:
        return False, ["no artifact tests defined"]

    failures = []
    for test in tests:
        test_id = test.get("test_id", "<missing-test-id>")
        if test.get("type") != "command":
            failures.append(f"{test_id}: unsupported test type {test.get('type')!r}")
            continue
        cmd = test.get("cmd")
        if not isinstance(cmd, str) or not cmd.strip():
            failures.append(f"{test_id}: command missing")
            continue
        try:
            result = subprocess.run(
                split_command(cmd),
                cwd=run_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5,
            )
        except Exception as exc:
            failures.append(f"{test_id}: execution error: {exc}")
            continue

        expected_exit = test.get("expect_exit_code", 0)
        if result.returncode != expected_exit:
            failures.append(
                f"{test_id}: exit code {result.returncode} != expected {expected_exit}"
            )
        expected_lines_min = test.get("expect_stdout_lines_min")
        if expected_lines_min is not None:
            line_count = len([line for line in result.stdout.splitlines() if line.strip()])
            if line_count < expected_lines_min:
                failures.append(
                    f"{test_id}: output lines {line_count} < expected {expected_lines_min}"
                )
        for expected in test.get("expect_stdout_contains", []):
            if expected not in result.stdout:
                failures.append(f"{test_id}: missing stdout substring {expected!r}")

    return not failures, failures


def load_verifier_artifacts(run_dir: Path) -> list:
    verifier_dir = run_dir / "verifier_artifacts"
    if not verifier_dir.exists():
        return []
    return [load_json(path) for path in sorted(verifier_dir.glob("*.json"))]


def file_existence_mode(run_dir: Path, case: dict) -> str:
    return "CERTIFIED_DONE" if target_artifacts_exist(run_dir, case["target_artifacts"]) else "NOT_DONE"


def artifact_test_mode(run_dir: Path, case: dict) -> str:
    passed, _ = run_artifact_tests(run_dir, case.get("artifact_tests", []))
    return "CERTIFIED_DONE" if passed else "NOT_DONE"


def provenance_gate_mode(run_dir: Path, case: dict) -> str:
    if not target_artifacts_exist(run_dir, case["target_artifacts"]):
        return "NOT_DONE"

    tests = case.get("artifact_tests", [])
    if tests:
        tests_passed, _ = run_artifact_tests(run_dir, tests)
        if not tests_passed:
            return "NOT_DONE"

    artifacts = load_verifier_artifacts(run_dir)
    if not artifacts:
        return "NOT_DONE"

    target_set = set(case["target_artifacts"])
    for artifact in artifacts:
        level = artifact.get("provenance_level")
        if (
            artifact.get("target_artifact") in target_set
            and artifact.get("authority") == "certifying"
            and artifact.get("same_worker_as_solution") is not True
            and artifact.get("executes_code") is True
            and isinstance(artifact.get("assertion_count"), int)
            and artifact["assertion_count"] > 0
            and PROVENANCE_ORDER.get(level, -1) >= PROVENANCE_ORDER["P2"]
        ):
            return "CERTIFIED_DONE"

    return "PROVISIONAL_DONE"


def run_policy_engine_mode(run_dir: Path) -> str:
    result = subprocess.run(
        [sys.executable, ".agentic-pi/validators/certify_run.py", str(run_dir)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=15,
    )
    cert_path = run_dir / "certification.json"
    if not cert_path.exists():
        raise RuntimeError(
            "policy engine mode did not produce certification.json: "
            f"exit={result.returncode}, output={result.stdout}"
        )
    return load_json(cert_path)["status"]


def evaluate_case(case_dir: Path, run_prefix: str) -> dict:
    case = load_json(case_dir / "case.json")
    run_id = f"{run_prefix}_{case['case_id']}"
    run_dir = copy_case_to_run(case_dir, run_id)

    statuses = {
        "file_existence": file_existence_mode(run_dir, case),
        "artifact_test": artifact_test_mode(run_dir, case),
        "provenance_gate": provenance_gate_mode(run_dir, case),
        "policy_engine": run_policy_engine_mode(run_dir),
    }

    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "expected_certified": case["expected_certified"],
        "expected_policy_status": case["expected_policy_status"],
        "statuses": statuses,
        "run_id": run_id,
    }


def mode_metrics(rows: list, mode: str) -> dict:
    total = len(rows)
    certified = [row for row in rows if row["statuses"][mode] == "CERTIFIED_DONE"]
    expected_certified = [row for row in rows if row["expected_certified"]]
    false_certified = [
        row
        for row in rows
        if row["statuses"][mode] == "CERTIFIED_DONE" and not row["expected_certified"]
    ]
    false_blocked = [
        row
        for row in rows
        if row["expected_certified"] and row["statuses"][mode] != "CERTIFIED_DONE"
    ]
    status_matches = [
        row
        for row in rows
        if (row["statuses"][mode] == "CERTIFIED_DONE") == row["expected_certified"]
    ]

    precision = None
    if certified:
        precision = (len(certified) - len(false_certified)) / len(certified)

    expected_negative = total - len(expected_certified)
    false_certified_rate = (
        len(false_certified) / expected_negative if expected_negative else 0.0
    )
    false_block_rate = (
        len(false_blocked) / len(expected_certified) if expected_certified else 0.0
    )

    return {
        "false_certified_done_rate": false_certified_rate,
        "certified_done_precision": precision,
        "provisional_done_rate": len(
            [row for row in rows if row["statuses"][mode] == "PROVISIONAL_DONE"]
        )
        / total,
        "not_done_rate": len([row for row in rows if row["statuses"][mode] == "NOT_DONE"])
        / total,
        "false_block_rate": false_block_rate,
        "status_match_rate": len(status_matches) / total,
        "certified_done_count": len(certified),
        "false_certified_done_count": len(false_certified),
        "false_block_count": len(false_blocked),
    }


def build_report(metrics: dict) -> str:
    lines = [
        "# v0.4 Diagnostic Evaluation Report",
        "",
        f"Generated on {metrics['generated_at']}",
        f"Total cases: {metrics['total_cases']}",
        "",
        "## Case Matrix",
        "",
        "| Case | Expected | File Exists | Artifact Test | Provenance Gate | Policy Engine |",
        "|---|---|---|---|---|---|",
    ]
    for row in metrics["cases"]:
        expected = "certified" if row["expected_certified"] else "not certified"
        statuses = row["statuses"]
        lines.append(
            "| {case} | {expected} | {file_existence} | {artifact_test} | "
            "{provenance_gate} | {policy_engine} |".format(
                case=row["case_id"],
                expected=expected,
                file_existence=statuses["file_existence"],
                artifact_test=statuses["artifact_test"],
                provenance_gate=statuses["provenance_gate"],
                policy_engine=statuses["policy_engine"],
            )
        )

    lines.extend([
        "",
        "## Metrics",
        "",
        "| Mode | False CERTIFIED_DONE Rate | Precision | Provisional Rate | NOT_DONE Rate | False Block Rate | Status Match Rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for mode in MODES:
        data = metrics["modes"][mode]
        precision = data["certified_done_precision"]
        precision_text = "n/a" if precision is None else f"{precision:.3f}"
        lines.append(
            "| {mode} | {false_rate:.3f} | {precision} | {prov:.3f} | {not_done:.3f} | {false_block:.3f} | {match:.3f} |".format(
                mode=mode,
                false_rate=data["false_certified_done_rate"],
                precision=precision_text,
                prov=data["provisional_done_rate"],
                not_done=data["not_done_rate"],
                false_block=data["false_block_rate"],
                match=data["status_match_rate"],
            )
        )

    lines.extend([
        "",
        "## Claim Boundary",
        "",
        "This is a small deterministic diagnostic evaluation. It does not claim broad benchmark validity, oracle quality, Pi integration, or real Mercury planner quality.",
    ])
    return "\n".join(lines) + "\n"


def run_evaluation(output_dir: Path, run_prefix: str) -> dict:
    case_dirs = sorted(path for path in CASES_DIR.iterdir() if path.is_dir())
    rows = [evaluate_case(case_dir, run_prefix) for case_dir in case_dirs]
    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(rows),
        "modes": {mode: mode_metrics(rows, mode) for mode in MODES},
        "cases": rows,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "diagnostic_metrics.json", metrics)
    (output_dir / "diagnostic_report.md").write_text(build_report(metrics), encoding="utf-8")
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Run v0.4 diagnostic evaluation")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--run-prefix", default="diagnostic_eval")
    args = parser.parse_args()

    metrics = run_evaluation(Path(args.output_dir), args.run_prefix)
    print(
        "Diagnostic evaluation complete. "
        f"Policy false CERTIFIED_DONE rate = "
        f"{metrics['modes']['policy_engine']['false_certified_done_rate']:.3f}"
    )
    print(f"Wrote {Path(args.output_dir) / 'diagnostic_metrics.json'}")
    print(f"Wrote {Path(args.output_dir) / 'diagnostic_report.md'}")


if __name__ == "__main__":
    main()
