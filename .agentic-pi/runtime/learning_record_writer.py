#!/usr/bin/env python3
"""Write append-only advisory learning records."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEMORY_DIR = ROOT / ".agentic-pi" / "memory" / "learning_records"


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json_new(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"learning record already exists: {path}")
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "unknown"


def learning_id(extract: dict) -> str:
    return "L.{run}.{strategy}.{kind}".format(
        run=slug(extract.get("run_id", "")),
        strategy=slug(extract.get("strategy_id", "strategy")),
        kind=slug(extract.get("outcome_kind", "unknown")),
    )


def build_record(extract: dict) -> dict:
    return {
        "learning_id": learning_id(extract),
        "source_run_id": extract.get("run_id", ""),
        "task_type": extract.get("task_type", "unknown"),
        "strategy_id": extract.get("strategy_id", ""),
        "outcome": extract.get("outcome_kind", "unknown"),
        "outcome_status": extract.get("outcome_status", ""),
        "principle": extract.get("principle", ""),
        "do_not_use_when": extract.get("do_not_use_when", []),
        "evidence_files": extract.get("evidence_files", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }


def write_learning_record(run_dir: Path, memory_dir: Path) -> dict:
    extract_path = run_dir / "experience_extract.json"
    extract = load_json(extract_path)
    record = build_record(extract)
    write_json_new(memory_dir / f"{record['learning_id']}.json", record)
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write append-only learning record from experience_extract.json.")
    parser.add_argument("run_dir")
    parser.add_argument("--memory-dir", default=str(DEFAULT_MEMORY_DIR))
    args = parser.parse_args(argv)
    try:
        record = write_learning_record(Path(args.run_dir), Path(args.memory_dir))
    except Exception as exc:
        print(f"LEARNING_RECORD_WRITE_FAILED: {exc}")
        return 1
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
