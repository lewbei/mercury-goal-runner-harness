#!/usr/bin/env python3
"""Select a deterministic domain pack from task_type_decision.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACK_DIR = ROOT / ".agentic-pi" / "domain_packs"


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pack_path_for(task_type: str) -> Path:
    return PACK_DIR / f"{task_type}.json"


def select_domain_pack(run_dir: Path) -> dict:
    task_decision = load_json(run_dir / "task_type_decision.json")
    task_type = task_decision.get("task_type", "unknown")
    path = pack_path_for(task_type)
    if task_type == "unknown" or not path.is_file():
        output = {
            "run_id": task_decision.get("run_id", run_dir.name),
            "task_type": task_type,
            "selection_status": "NEED_USER_DOMAIN",
            "selected_domain_pack": "",
            "reason": "No safe deterministic domain pack selected for this task type.",
            "domain_pack_path": "",
            "final_status_authority": "certifier_only",
            "can_certify_done": False,
        }
        write_json(run_dir / "domain_pack_selection.json", output)
        return output

    pack = load_json(path)
    if task_type not in pack.get("allowed_task_types", []):
        raise ValueError(f"domain pack {path.name} does not allow task type {task_type}")
    output = {
        "run_id": task_decision.get("run_id", run_dir.name),
        "task_type": task_type,
        "selection_status": "SELECTED",
        "selected_domain_pack": pack["domain_pack_id"],
        "reason": "Selected deterministic domain pack from task type.",
        "domain_pack_path": path.relative_to(ROOT).as_posix(),
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }
    write_json(run_dir / "domain_pack_selection.json", output)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Select deterministic domain pack.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        output = select_domain_pack(Path(args.run_dir))
    except Exception as exc:
        print(f"DOMAIN_PACK_SELECTION_FAILED: {exc}")
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
