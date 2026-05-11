#!/usr/bin/env python3
"""Capture subagent learnings as advisory run-local/quarantine memory.

This script does not write directly to durable memory. Durable promotion is owned
by memory_write_gate.py after certifier-owned final_status.json exists.

Usage:
    python .agentic-pi/runtime/run_subagent_memory.py <run_dir> <agent_name>
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".agentic-pi" / "runtime"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def gather_context(run_dir: Path) -> list[dict]:
    context_pack: list[dict] = []
    plan_path = run_dir / "thinking_plan.md"
    if plan_path.is_file():
        context_pack.append(
            {
                "card_id": f"plan-{run_dir.name}",
                "content": plan_path.read_text(encoding="utf-8")[:500],
                "source": "thinking_plan.md",
                "evidence_ref": "thinking_plan.md",
            }
        )

    step_dir = run_dir / "step_logs"
    if step_dir.is_dir():
        for step_log_path in sorted(step_dir.glob("*.json")):
            try:
                log = load_json(step_log_path)
            except Exception as exc:
                context_pack.append(
                    {
                        "card_id": f"step-{run_dir.name}-{step_log_path.stem}-invalid",
                        "content": f"Unreadable step log {step_log_path.name}: {exc}",
                        "source": "step_log_parse_error",
                        "evidence_ref": f"step_logs/{step_log_path.name}",
                    }
                )
                continue
            evidence = log.get("evidence", [])
            if isinstance(evidence, list) and evidence:
                content = str(evidence[0])
            else:
                content = f"Step {log.get('step_id', step_log_path.stem)} has no evidence entry"
            context_pack.append(
                {
                    "card_id": f"step-{run_dir.name}-{step_log_path.stem}",
                    "content": content,
                    "source": "step_log",
                    "evidence_ref": f"step_logs/{step_log_path.name}",
                }
            )
    return context_pack


def outcome_status(run_dir: Path) -> str:
    final_status_path = run_dir / "final_status.json"
    if final_status_path.is_file():
        try:
            return str(load_json(final_status_path).get("status", "UNKNOWN"))
        except Exception:
            return "UNKNOWN"
    certification_path = run_dir / "certification.json"
    if certification_path.is_file():
        try:
            return str(load_json(certification_path).get("status", "UNKNOWN"))
        except Exception:
            return "UNKNOWN"
    return "UNKNOWN"


def classify_reflection(context_pack: list[dict], outcome: str) -> tuple[list[dict], list[dict]]:
    helpful = []
    harmful = []
    if outcome in {"CERTIFIED_DONE", "DONE_PASS"}:
        helpful = [{"card_id": row["card_id"], "reason": f"Contributed to {outcome}"} for row in context_pack]
    elif outcome in {"NOT_DONE", "DONE_FAIL"}:
        harmful = [{"card_id": row["card_id"], "reason": f"Did not prevent {outcome}"} for row in context_pack]
    return helpful, harmful


def write_advisory_memory(run_dir: Path, agent_name: str, context_pack: list[dict], outcome: str) -> int:
    memory_clerk = load_module("run_memory_clerk", RUNTIME / "run_memory_clerk.py")
    quarantine_writer = load_module("quarantine_memory_writer", RUNTIME / "quarantine_memory_writer.py")

    written = 0
    for row in context_pack:
        principle = f"Subagent {agent_name} in {run_dir.name}: {row['content'][:200]}"
        details = {"agent": agent_name, "outcome": outcome, "source": row["source"]}
        memory_clerk.append_run_memory(
            run_dir,
            "memory_usage",
            principle,
            target_file=row["evidence_ref"],
            details=details,
        )
        quarantine_writer.write_quarantine_candidate(
            run_dir,
            run_dir.name,
            principle,
            candidate_type="subagent_learning_candidate",
            evidence_refs=[row["evidence_ref"]],
        )
        written += 1
    return written


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Usage: python run_subagent_memory.py <run_dir> [agent_name]")
        return 2

    run_dir = Path(argv[0])
    agent_name = argv[1] if len(argv) > 1 else "unknown-agent"
    if not run_dir.is_dir():
        print(f"Error: run directory not found: {run_dir}")
        return 1

    run_id = run_dir.name
    print(f"=== Subagent Memory Capture: {agent_name} on {run_id} ===")
    context_pack = gather_context(run_dir)
    if not context_pack:
        print("  No subagent context found; no memory candidate written")
        return 0

    outcome = outcome_status(run_dir)
    helpful, harmful = classify_reflection(context_pack, outcome)
    reflection = {
        "schema_version": "reflection_report_v1",
        "run_id": run_id,
        "agent_name": agent_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "outcome_status": outcome,
        "helpful": helpful,
        "harmful": harmful,
        "neutral": [] if helpful or harmful else [{"card_id": row["card_id"], "reason": "Outcome not final"} for row in context_pack],
        "authority_level": "advisory_only",
        "can_certify_done": False,
    }
    write_json(run_dir / "memory" / "ace_reflection.json", reflection)

    written = write_advisory_memory(run_dir, agent_name, context_pack, outcome)
    print(f"  Context entries: {len(context_pack)}")
    print(f"  Reflection: {len(helpful)} helpful, {len(harmful)} harmful")
    print(f"  Quarantine learning candidates: {written}")
    print("  Durable memory promotion: not performed here; use memory_write_gate.py after certifier lock")
    print(f"=== Memory capture complete for {agent_name} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
