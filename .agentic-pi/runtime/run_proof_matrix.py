#!/usr/bin/env python3
"""Run the v2.0 integrated proof matrix.

The proof matrix is a reporting and verification runner. It does not certify
DONE and does not replace certify_run.py or policy_engine.py.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX = ROOT / ".agentic-pi" / "proof_matrix" / "proof_matrix.json"
DEFAULT_OUTPUT = ROOT / ".agentic-runs" / "proof_matrix_outputs" / "proof_matrix_result.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize_command(command: list[str]) -> list[str]:
    if command and command[0].lower() in {"python", "python.exe"}:
        return [sys.executable, *command[1:]]
    return command


def display_command(command: list[str]) -> list[str]:
    if command and command[0].lower() in {"python", "python.exe"}:
        return ["python", *command[1:]]
    return command


def run_entry(entry: dict) -> dict:
    result = subprocess.run(
        normalize_command(entry["command"]),
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output = result.stdout or ""
    tail = "\n".join(output.splitlines()[-20:])
    return {
        "claim_id": entry["claim_id"],
        "command": display_command(entry["command"]),
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
        "stdout_tail": tail,
    }


def run_matrix(matrix_path: Path, mode: str, output_path: Path) -> dict:
    matrix = load_json(matrix_path)
    entries = [
        entry for entry in matrix["entries"]
        if mode == "full" or entry["mode"] == "quick"
    ]
    results = [run_entry(entry) for entry in entries]
    passed_count = len([row for row in results if row["passed"]])
    proof_result = {
        "proof_matrix_id": matrix["proof_matrix_id"],
        "version": matrix["version"],
        "mode": mode,
        "all_passed": passed_count == len(results),
        "entry_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "entries": results,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }
    write_json(output_path, proof_result)
    return proof_result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run integrated proof matrix without certifying DONE.")
    parser.add_argument("--mode", choices=["quick", "full"], default="quick")
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    try:
        result = run_matrix(Path(args.matrix), args.mode, Path(args.output))
    except Exception as exc:
        print(f"PROOF_MATRIX_FAILED: {exc}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
