#!/usr/bin/env python3
"""Update memory files based on past runs.

Scans all run directories under .agentic-runs, extracts failed and successful
checks from certification.json, and appends JSON lines to the appropriate memory
files.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent  # project root
RUNS_DIR = BASE_DIR / ".agentic-runs"
MEMORY_DIR = BASE_DIR / ".agentic-pi" / "memory"

FAILURE_FILE = MEMORY_DIR / "failure_patterns.jsonl"
SUCCESS_FILE = MEMORY_DIR / "successful_patterns.jsonl"


def append_jsonl(path: Path, obj: dict):
    """Append a JSON object as a single line to a .jsonl file."""
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    # Ensure files exist
    for f in (FAILURE_FILE, SUCCESS_FILE):
        f.touch(exist_ok=True)

    for run_dir in RUNS_DIR.iterdir():
        if not run_dir.is_dir():
            continue
        cert_path = run_dir / "certification.json"
        if not cert_path.is_file():
            continue
        try:
            cert = json.loads(cert_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Failed to read {cert_path}: {e}")
            continue
        # Record failures
        for fail in cert.get("failed_checks", []):
            entry = {
                "run_id": cert.get("run_id"),
                "failure": fail,
                "timestamp": cert.get("timestamp")
            }
            append_jsonl(FAILURE_FILE, entry)
        # Record successes (passed checks)
        for passed in cert.get("passed_checks", []):
            entry = {
                "run_id": cert.get("run_id"),
                "passed": passed,
                "timestamp": cert.get("timestamp")
            }
            append_jsonl(SUCCESS_FILE, entry)
    print(f"Memory updated. Failures written to {FAILURE_FILE}, successes to {SUCCESS_FILE}.")

if __name__ == "__main__":
    main()
