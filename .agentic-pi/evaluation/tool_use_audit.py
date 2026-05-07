#!/usr/bin/env python3
"""Create a v1.6 tool-use trajectory audit from a Pi session fixture.

This builds on pi_session_audit.py. The output can fail unsafe trajectories,
but it cannot certify DONE.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT / ".agentic-pi" / "runtime"
EVALUATION_DIR = ROOT / ".agentic-pi" / "evaluation"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pi_session_audit = load_module("pi_session_audit_for_tool_use_audit", RUNTIME_DIR / "pi_session_audit.py")
trajectory_metrics = load_module("trajectory_metrics_for_tool_use_audit", EVALUATION_DIR / "trajectory_metrics.py")


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def audit_tool_use(session_path: Path, run_id: str, agent: str = "goal-orchestrator") -> dict:
    events = pi_session_audit.load_events(session_path)
    command_audit = pi_session_audit.audit_session(session_path, run_id, agent)
    metrics = trajectory_metrics.build_metrics(
        events,
        command_audit,
        command_audit["allowed_command"],
    )
    trajectory_status = "PASS" if metrics["trajectory_pass"] else "FAIL"
    violations = list(command_audit.get("violations", []))
    if not metrics["tool_order_correct"]:
        violations.append("tool order incorrect: certifier must run before status reads")
    if metrics["missing_status_read"]:
        violations.append(
            "missing status read: " + ", ".join(metrics["missing_status_files"])
        )
    if metrics["duplicate_certifier_invocations"]:
        violations.append("duplicate certifier invocation in trajectory")
    if metrics["manual_status_write_attempt"]:
        violations.append("manual status write attempt in trajectory")

    if violations:
        trajectory_status = "FAIL"

    return {
        "run_id": run_id,
        "agent": agent,
        "session_path": str(session_path),
        "generated_by": "tool-use-audit-v1.6",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_status": command_audit["audit_status"],
        "trajectory_status": trajectory_status,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "status_values": command_audit.get("status_values", {}),
        "metrics": metrics,
        "violations": violations,
        "policy_checks": command_audit.get("policy_checks", []) + metrics["policy_checks"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Audit trajectory-level tool use.")
    parser.add_argument("session_path")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--agent", default="goal-orchestrator")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    report = audit_tool_use(Path(args.session_path), args.run_id, args.agent)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        write_json(Path(args.output), report)
    print(rendered)
    return 0 if report["trajectory_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
