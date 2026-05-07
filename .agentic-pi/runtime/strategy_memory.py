#!/usr/bin/env python3
"""Index advisory strategy learning records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_records(memory_dir: Path) -> list[dict]:
    if not memory_dir.is_dir():
        return []
    records = []
    for path in sorted(memory_dir.glob("*.json")):
        try:
            records.append(load_json(path))
        except Exception:
            continue
    return records


def build_index(records: list[dict]) -> dict:
    by_task_type = {}
    for record in records:
        by_task_type.setdefault(record.get("task_type", "unknown"), []).append(record)
    return {
        "generated_by": "strategy-memory-v1.7",
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "record_count": len(records),
        "task_types": sorted(by_task_type),
        "records": records,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Index advisory strategy memory records.")
    parser.add_argument("memory_dir")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    index = build_index(load_records(Path(args.memory_dir)))
    if args.output:
        write_json(Path(args.output), index)
    print(json.dumps(index, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
