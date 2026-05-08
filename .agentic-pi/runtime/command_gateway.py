#!/usr/bin/env python3
"""Command gateway for Pi/Mercury runtime enforcement.

This module narrows the executable surface. It intentionally avoids shell
execution for certifier commands by dispatching through sys.executable and an
argument list. The gateway cannot certify DONE.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERSION = "v3.2"

PROTECTED_RE = re.compile(
    r"(final_status\.md|certification\.json|policy_decision\.json|"
    r"verifier_artifacts|verifier_smell_reports|verifier_strength_reports)",
    re.IGNORECASE,
)
WRITE_RE = re.compile(
    r"(>|>>|\bset-content\b|\bout-file\b|\badd-content\b|\bnew-item\b|"
    r"\bcopy\b|\bcopy-item\b|\bmove\b|\bmove-item\b|\bpython\s+-c\b|"
    r"\bopen\s*\(|\.write\s*\()",
    re.IGNORECASE,
)
DELETE_RE = re.compile(r"\b(rm|del|erase|remove-item|rmdir|rd)\b", re.IGNORECASE)
READ_RE = re.compile(r"^\s*(type|cat|get-content|gc)\s+", re.IGNORECASE)
LIST_RE = re.compile(r"^\s*(dir|ls|get-childitem|gci)\s+", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_command(command: str) -> str:
    return " ".join(command.replace("\\", "/").strip().split())


def certifier_command(run_id: str) -> str:
    return f"python .agentic-pi/validators/certify_run.py .agentic-runs/{run_id}"


def is_disposable_run_id(run_id: str) -> bool:
    return run_id.startswith("pi_smoke_")


def command_mentions_run(command: str, run_id: str) -> bool:
    return f".agentic-runs/{run_id}" in normalize_command(command)


def command_has_path_escape(command: str) -> bool:
    normalized = normalize_command(command).lower()
    return (
        "../" in normalized
        or "..\\" in command.lower()
        or re.search(r"(^|\s)([a-z]:/|/)", normalized) is not None
    )


def is_exact_certifier_command(command: str, run_id: str) -> bool:
    return normalize_command(command) == certifier_command(run_id)


def status_read_path_allowed(command: str, run_id: str) -> bool:
    normalized = normalize_command(command).lower()
    if not (READ_RE.search(normalized) or LIST_RE.search(normalized)):
        return False
    if command_has_path_escape(command):
        return False
    allowed_prefix = f".agentic-runs/{run_id}"
    if allowed_prefix not in normalized:
        return False
    return not WRITE_RE.search(normalized) and not DELETE_RE.search(normalized)


def classify_command(command: str, run_id: str, prior_commands: list[str] | None = None) -> dict:
    prior_commands = prior_commands or []
    normalized = normalize_command(command)
    violations = []
    decision = "BLOCK"
    command_kind = "blocked"
    reason = "command is outside the enforced runtime surface"

    if not is_disposable_run_id(run_id):
        violations.append("run id is not disposable pi_smoke_*")
    if command_has_path_escape(command):
        violations.append("path escape or absolute path observed")

    if is_exact_certifier_command(command, run_id):
        if certifier_command(run_id) in [normalize_command(item) for item in prior_commands]:
            violations.append("duplicate certifier invocation")
        elif violations:
            pass
        else:
            decision = "ALLOW"
            command_kind = "certifier"
            reason = "exact deterministic certifier command"
    elif status_read_path_allowed(command, run_id):
        if violations:
            pass
        else:
            decision = "ALLOW"
            command_kind = "status_read"
            reason = "read/list inside disposable run"
    elif PROTECTED_RE.search(command) and WRITE_RE.search(command):
        violations.append("manual protected status or verifier write command")
    elif DELETE_RE.search(command):
        violations.append("deletion command is not allowed by runtime enforcement")
    elif WRITE_RE.search(command) and not command_mentions_run(command, run_id):
        violations.append("source-tree or external write command")
    elif WRITE_RE.search(command):
        violations.append("unapproved write command")

    if violations:
        reason = "; ".join(violations)

    return {
        "gateway_id": "command_gateway",
        "version": VERSION,
        "generated_at": utc_now(),
        "run_id": run_id,
        "command": command,
        "normalized_command": normalized,
        "decision": decision,
        "command_kind": command_kind,
        "reason": reason,
        "violations": violations,
    }


def execute_gateway_command(command: str, run_id: str, root: Path | None = None, prior_commands: list[str] | None = None) -> dict:
    root = root or ROOT
    report = classify_command(command, run_id, prior_commands=prior_commands)
    report.update({
        "executed": False,
        "exit_code": -1,
        "stdout_tail": "",
    })
    if report["decision"] != "ALLOW":
        return report

    if report["command_kind"] == "certifier":
        result = subprocess.run(
            [
                sys.executable,
                ".agentic-pi/validators/certify_run.py",
                f".agentic-runs/{run_id}",
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout or ""
        report.update({
            "executed": True,
            "exit_code": result.returncode,
            "stdout_tail": "\n".join(output.splitlines()[-20:]),
        })
        return report

    if report["command_kind"] == "status_read":
        report.update({
            "executed": True,
            "exit_code": 0,
            "stdout_tail": "STATUS_READ_ALLOWED",
        })
        return report

    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Classify or execute a command through the runtime gateway.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    if args.execute:
        result = execute_gateway_command(args.command, args.run_id)
    else:
        result = classify_command(args.command, args.run_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["decision"] == "ALLOW" else 1


if __name__ == "__main__":
    sys.exit(main())
