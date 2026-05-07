#!/usr/bin/env python3
"""Gate strategy candidates against local capabilities and authority boundaries."""
import argparse
import json
import sys
from pathlib import Path


FORBIDDEN_STATUS_VALUES = {"DONE_PASS", "DONE_FAIL", "NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE"}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def capability_allowed(capability: dict, task_type: str) -> bool:
    allowed = capability.get("allowed_for_task_types", [])
    return "*" in allowed or task_type in allowed


def gate_candidate(candidate: dict, capabilities_by_id: dict) -> tuple[bool, list[str]]:
    reasons = []
    task_type = candidate.get("task_type", "unknown")
    for capability_id in candidate.get("required_capabilities", []):
        capability = capabilities_by_id.get(capability_id)
        if not capability:
            reasons.append(f"missing capability: {capability_id}")
            continue
        if not capability_allowed(capability, task_type):
            reasons.append(f"capability {capability_id} not allowed for {task_type}")
        if capability.get("writes_status_artifacts") and not capability.get("certifier_owned"):
            reasons.append(f"capability {capability_id} writes status artifacts outside certifier ownership")

    if candidate.get("attempts_status_write") is True:
        reasons.append("strategy attempts manual status artifact write")
    if candidate.get("attempts_verifier_forgery") is True:
        reasons.append("strategy attempts verifier artifact forgery")
    if candidate.get("status_authority") not in {None, "", "none"}:
        reasons.append("strategy claims final status authority")
    for value in candidate.values():
        if isinstance(value, str) and value in FORBIDDEN_STATUS_VALUES:
            reasons.append(f"strategy contains forbidden final status value: {value}")

    return not reasons, reasons


def gate_run(run_dir: Path) -> dict:
    inventory = load_json(run_dir / "capability_inventory.json")
    candidate_doc = load_json(run_dir / "strategy_candidates.json")
    capabilities_by_id = {
        capability["capability_id"]: capability
        for capability in inventory.get("capabilities", [])
    }

    applicable = []
    blocked = []
    for candidate in candidate_doc.get("candidates", []):
        is_applicable, reasons = gate_candidate(candidate, capabilities_by_id)
        if is_applicable:
            applicable.append(candidate)
        else:
            blocked.append({
                "strategy_id": candidate.get("strategy_id", ""),
                "block_reasons": reasons,
            })

    output = {
        "run_id": candidate_doc.get("run_id", ""),
        "task_type": candidate_doc.get("task_type", "unknown"),
        "applicable_strategies": applicable,
        "blocked_strategies": blocked,
    }
    write_json(run_dir / "strategy_applicability.json", output)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gate deterministic strategy candidates.")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    try:
        output = gate_run(Path(args.run_dir))
    except Exception as exc:
        print(f"STRATEGY_APPLICABILITY_FAILED: {exc}")
        return 1
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
