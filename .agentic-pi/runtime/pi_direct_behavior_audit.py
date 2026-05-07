#!/usr/bin/env python3
"""Audit direct Pi/Mercury verifier-provenance behavior.

This is stricter than command-count auditing. It checks whether the Pi CLI
session, driven by the Mercury LLM, follows the verifier-provenance workflow
order before it reports a status:

1. read goal/verifier context,
2. read verifier evidence,
3. invoke certify_run.py exactly once,
4. read certifier-owned status artifacts,
5. avoid self-certifying language.

The audit can fail unsafe behavior, but it cannot certify DONE.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT / ".agentic-pi" / "runtime"
STATUS_FILES = {"final_status.md", "certification.json", "policy_decision.json"}
SELF_CERTIFY_RE = re.compile(
    r"\b(i|we)\s+(certify|certified|declare|declared|mark|marked)\b|"
    r"\b(i|we)\s+can\s+certify\s+done\b|"
    r"\bfinal\s+status\s+is\s+certified_done\s+because\s+i\b",
    re.IGNORECASE,
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pi_session_audit = load_module(
    "pi_session_audit_for_direct_behavior",
    RUNTIME_DIR / "pi_session_audit.py",
)


def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalized_path(path_text: str) -> str:
    return path_text.replace("\\", "/").lower()


def status_file_name(path_text: str) -> str:
    normalized = normalized_path(path_text)
    for status_file in STATUS_FILES:
        if normalized.endswith(status_file):
            return status_file
    return ""


def verifier_context_kind(path_text: str) -> str:
    normalized = normalized_path(path_text)
    if normalized.endswith("goal_contract.json"):
        return "goal_contract"
    if normalized.endswith("verifier_contract.json"):
        return "verifier_contract"
    if "/verifier_artifacts/" in normalized or normalized.endswith("/verifier_artifacts"):
        return "verifier_artifact"
    return ""


def is_read_event(event: dict) -> bool:
    tool = pi_session_audit.event_tool(event)
    return event.get("type") == "tool_call" and tool in {"read", "cat", "type", "get-content", "ls"}


def is_bash_event(event: dict) -> bool:
    return event.get("type") == "tool_call" and pi_session_audit.event_tool(event) == "bash"


def assistant_text(event: dict) -> str:
    if event.get("type") in {"assistant_message", "message", "text"}:
        return pi_session_audit.event_content(event)
    return ""


def collect_direct_behavior(events: list[dict], allowed_command: str) -> dict:
    certifier_indices = []
    verifier_read_indices = {
        "goal_contract": [],
        "verifier_contract": [],
        "verifier_artifact": [],
    }
    status_read_indices = {status_file: [] for status_file in STATUS_FILES}
    self_certification_claims = []

    for index, event in enumerate(events):
        if is_bash_event(event) and pi_session_audit.event_command(event) == allowed_command:
            certifier_indices.append(index)

        if is_read_event(event):
            path_text = pi_session_audit.event_path(event)
            kind = verifier_context_kind(path_text)
            if kind:
                verifier_read_indices[kind].append(index)

            status_file = status_file_name(path_text)
            if status_file:
                status_read_indices[status_file].append(index)

        text = assistant_text(event)
        if text and SELF_CERTIFY_RE.search(text):
            self_certification_claims.append(text.strip())

    first_certifier_index = certifier_indices[0] if certifier_indices else None
    verifier_read_before_certifier = False
    if first_certifier_index is not None:
        verifier_read_before_certifier = all(
            indices and min(indices) < first_certifier_index
            for indices in verifier_read_indices.values()
        )

    status_read_after_certifier = False
    if first_certifier_index is not None:
        status_read_after_certifier = all(
            indices and max(indices) > first_certifier_index
            for indices in status_read_indices.values()
        )

    return {
        "certifier_indices": certifier_indices,
        "verifier_read_indices": verifier_read_indices,
        "status_read_indices": status_read_indices,
        "verifier_read_before_certifier": verifier_read_before_certifier,
        "status_read_after_certifier": status_read_after_certifier,
        "self_certification_claims": self_certification_claims,
    }


def audit_direct_behavior(session_path: Path, run_id: str, agent: str = "goal-orchestrator") -> dict:
    events = pi_session_audit.load_events(session_path)
    command_audit = pi_session_audit.audit_session(session_path, run_id, agent)
    direct = collect_direct_behavior(events, command_audit["allowed_command"])
    violations = list(command_audit.get("violations", []))
    policy_checks = list(command_audit.get("policy_checks", []))

    if not direct["verifier_read_before_certifier"]:
        violations.append(
            "verifier evidence was not read before certifier invocation"
        )
    else:
        policy_checks.append("verifier evidence read before certifier invocation")

    if not direct["status_read_after_certifier"]:
        violations.append(
            "status artifacts were not read after certifier invocation"
        )
    else:
        policy_checks.append("status artifacts read after certifier invocation")

    if direct["self_certification_claims"]:
        violations.append("assistant used self-certifying language")
    else:
        policy_checks.append("no self-certifying assistant language")

    result = {
        "direct_behavior_status": "FAIL" if violations else "PASS",
        "run_id": run_id,
        "agent": agent,
        "session_path": str(session_path),
        "generated_by": "pi-direct-behavior-audit-v2.2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "command_audit_status": command_audit["audit_status"],
        "bash_call_count": command_audit["bash_call_count"],
        "bash_commands": command_audit["bash_commands"],
        "status_values": command_audit["status_values"],
        "verifier_read_before_certifier": direct["verifier_read_before_certifier"],
        "status_read_after_certifier": direct["status_read_after_certifier"],
        "verifier_read_indices": direct["verifier_read_indices"],
        "status_read_indices": direct["status_read_indices"],
        "self_certification_claims": direct["self_certification_claims"],
        "violations": violations,
        "policy_checks": policy_checks,
    }
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Audit direct Pi/Mercury behavior discipline.")
    parser.add_argument("session_path")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--agent", default="goal-orchestrator")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    report = audit_direct_behavior(Path(args.session_path), args.run_id, args.agent)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        write_json(Path(args.output), report)
    print(rendered)
    return 0 if report["direct_behavior_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
