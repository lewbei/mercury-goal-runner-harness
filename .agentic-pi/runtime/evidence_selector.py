#!/usr/bin/env python3
"""Evidence Selector – runs artifact tests and reports which artifacts have verified evidence.

Usage:
    python .agentic-pi/runtime/evidence_selector.py <run_id>
"""
import json
import sys
import subprocess
from pathlib import Path


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def run_test(cmd, cwd):
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )
        return result
    except Exception as exc:
        return exc


def main():
    if len(sys.argv) != 2:
        print("Usage: evidence_selector.py <run_id>")
        sys.exit(2)
    run_id = sys.argv[1]
    run_dir = Path(".agentic-runs") / run_id
    goal_path = run_dir / "goal_contract.json"
    registry_path = run_dir / "artifact_registry.json"
    if not goal_path.is_file() or not registry_path.is_file():
        print("Missing goal_contract.json or artifact_registry.json")
        sys.exit(1)
    goal = load_json(goal_path)
    registry = load_json(registry_path)
    artifact_tests = goal.get("artifact_tests", [])
    report = {"artifacts": []}
    for art in registry:
        art_id = art.get("artifact_id")
        path = art.get("path")
        # Find a matching test (by test_id if it matches artifact_id, otherwise by path)
        test = None
        for t in artifact_tests:
            if t.get("test_id") == art_id or t.get("cmd", "").find(path) != -1:
                test = t
                break
        if test is None:
            report["artifacts"].append({
                "artifact_id": art_id,
                "path": path,
                "evidence_obtained": False,
                "test_id": None,
                "test_result": "no test defined"
            })
            continue
        cmd = test.get("cmd")
        result = run_test(cmd, run_dir)
        if isinstance(result, Exception):
            report["artifacts"].append({
                "artifact_id": art_id,
                "path": path,
                "evidence_obtained": False,
                "test_id": test.get("test_id"),
                "test_result": f"execution error: {result}"
            })
            continue
        # Evaluate expectations
        expect_exit = test.get("expect_exit_code", 0)
        expect_contains = test.get("expect_stdout_contains", [])
        passed = (result.returncode == expect_exit) and all(sub in result.stdout for sub in expect_contains)
        report["artifacts"].append({
            "artifact_id": art_id,
            "path": path,
            "evidence_obtained": passed,
            "test_id": test.get("test_id"),
            "test_result": "passed" if passed else "failed"
        })
    out_path = run_dir / "evidence_report.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote evidence_report.json with {len(report['artifacts'])} entries")

if __name__ == "__main__":
    main()
