#!/usr/bin/env python3
"""Retrieve advisory experience for the current run."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEMORY_DIR = ROOT / ".agentic-pi" / "memory" / "learning_records"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


strategy_memory = load_module("strategy_memory_for_retriever", ROOT / ".agentic-pi" / "runtime" / "strategy_memory.py")


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def task_type_for_run(run_dir: Path) -> str:
    path = run_dir / "task_type_decision.json"
    if path.is_file():
        return load_json(path).get("task_type", "unknown")
    return "unknown"


def candidate_ids(run_dir: Path) -> set[str]:
    path = run_dir / "strategy_candidates.json"
    if not path.is_file():
        return set()
    candidates = load_json(path).get("candidates", [])
    return {candidate.get("strategy_id", "") for candidate in candidates}


def adjustment_for(record: dict) -> dict:
    outcome = record.get("outcome")
    strategy_id = record.get("strategy_id", "")
    if outcome == "success":
        delta = 1
        reason = f"success memory: {record.get('learning_id', '')}"
    elif outcome == "provisional":
        delta = -1
        reason = f"provisional memory: {record.get('learning_id', '')}"
    elif outcome == "failure":
        delta = -2
        reason = f"failure memory: {record.get('learning_id', '')}"
    else:
        delta = 0
        reason = f"unknown memory: {record.get('learning_id', '')}"
    delta = max(-2, min(1, delta))
    return {
        "strategy_id": strategy_id,
        "score_delta": delta,
        "reason": reason,
        "learning_id": record.get("learning_id", ""),
    }


def retrieve_experience(run_dir: Path, memory_dir: Path) -> dict:
    task_type = task_type_for_run(run_dir)
    ids = candidate_ids(run_dir)
    records = strategy_memory.load_records(memory_dir)
    matched = []
    ignored = []
    adjustments = []
    for record in records:
        same_task = record.get("task_type") == task_type
        same_strategy = record.get("strategy_id", "") in ids
        if same_task and same_strategy:
            matched.append(record.get("learning_id", ""))
            adjustments.append(adjustment_for(record))
        else:
            ignored.append(record.get("learning_id", ""))

    output = {
        "run_id": run_dir.name,
        "generated_by": "experience-retriever-v1.7",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_type": task_type,
        "matched_learning_ids": matched,
        "ignored_learning_ids": ignored,
        "strategy_adjustments": adjustments,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }
    write_json(run_dir / "retrieved_experience.json", output)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Retrieve advisory strategy experience.")
    parser.add_argument("run_dir")
    parser.add_argument("--memory-dir", default=str(DEFAULT_MEMORY_DIR))
    args = parser.parse_args(argv)
    try:
        output = retrieve_experience(Path(args.run_dir), Path(args.memory_dir))
    except Exception as exc:
        print(f"EXPERIENCE_RETRIEVE_FAILED: {exc}")
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
