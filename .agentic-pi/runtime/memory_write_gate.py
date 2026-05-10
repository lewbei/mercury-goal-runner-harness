#!/usr/bin/env python3
"""Gate durable MemPalace card promotion.

This is the only v3.7 component that may write under
.agentic-pi/memory/durable/. It requires certifier-owned final_status.json and
schema-valid advisory memory cards.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = ROOT / ".agentic-pi" / "runtime" / "mempalace_adapter.py"
VALIDATOR_PATH = ROOT / ".agentic-pi" / "validators" / "validate_memory_card.py"

AUTHORITY_LEAK_FIELDS = {
    "final_status",
    "final_status_json",
    "policy_status",
    "certification_status",
    "certified_done",
    "policy_override",
    "can_override_policy",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def final_status_is_certifier_owned(run_dir: Path) -> bool:
    path = Path(run_dir) / "final_status.json"
    if not path.is_file():
        return False
    try:
        status = load_json(path)
    except Exception:
        return False
    return (
        status.get("schema_version") == "final_status_v1"
        and status.get("final_status_authority") == "certifier_only"
        and status.get("status_source") in {"certification.json", "policy_decision.json"}
    )


def reject_authority_leakage(card: dict) -> list[str]:
    errors = []
    for field in sorted(AUTHORITY_LEAK_FIELDS):
        if field in card:
            errors.append(f"card contains authority-leak field: {field}")
    if card.get("can_certify_done") is not False:
        errors.append("memory card cannot certify DONE")
    if card.get("authority_level") != "advisory_only":
        errors.append("memory card authority_level must be advisory_only")
    return errors


def build_decision(run_id: str, decision: str, card_id: str, reason: str, *, target_path: str = "", promoted: bool = False) -> dict:
    return {
        "schema_version": "memory_write_decision_v1",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "card_id": card_id,
        "reason": reason,
        "target_path": target_path,
        "promoted": promoted,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
    }


def promote_card(run_dir: Path, memory_root: Path, card: dict, *, decision_path: Path | None = None) -> dict:
    run_dir = Path(run_dir)
    memory_root = Path(memory_root)
    run_id = run_dir.name
    card_id = card.get("card_id", "")

    if not final_status_is_certifier_owned(run_dir):
        decision = build_decision(run_id, "REJECTED", card_id, "final_status.json missing or not certifier-owned")
        if decision_path:
            write_json(decision_path, decision)
        return decision

    authority_errors = reject_authority_leakage(card)
    if authority_errors:
        decision = build_decision(run_id, "REJECTED", card_id, "; ".join(authority_errors))
        if decision_path:
            write_json(decision_path, decision)
        return decision

    validator = load_module("validate_memory_card", VALIDATOR_PATH)
    errors = validator.validate_memory_card(card)
    if errors:
        decision = build_decision(run_id, "REJECTED", card_id, "; ".join(errors))
        if decision_path:
            write_json(decision_path, decision)
        return decision

    adapter = load_module("mempalace_adapter", ADAPTER_PATH)
    durable_card = adapter.normalize_card(card)
    durable_card["card_status"] = "durable"
    durable_card["promoted_by"] = "memory_write_gate"
    durable_card["promoted_at"] = datetime.now(timezone.utc).isoformat()
    target = adapter.write_durable_card(memory_root, durable_card)
    decision = build_decision(
        run_id,
        "APPROVED",
        card_id,
        "card promoted by memory_write_gate after certifier-owned final_status.json",
        target_path=target.as_posix(),
        promoted=True,
    )
    if decision_path:
        write_json(decision_path, decision)
    return decision


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Promote a valid advisory card into durable MemPalace memory.")
    parser.add_argument("run_dir")
    parser.add_argument("--memory-root", default=str(ROOT / ".agentic-pi" / "memory"))
    parser.add_argument("--card", required=True)
    parser.add_argument("--decision-output", default="")
    args = parser.parse_args(argv)
    card = load_json(Path(args.card))
    decision = promote_card(
        Path(args.run_dir),
        Path(args.memory_root),
        card,
        decision_path=Path(args.decision_output) if args.decision_output else None,
    )
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0 if decision["decision"] == "APPROVED" else 1


if __name__ == "__main__":
    sys.exit(main())
