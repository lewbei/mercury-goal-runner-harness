#!/usr/bin/env python3
"""Run or plan the v2.1 controlled Pi chain runtime smoke.

This tool is a smoke runner, not a certifier. It can prepare a disposable
`pi_smoke_*` run, run bounded Pi prompts, and then read certifier-owned status
artifacts directly. Final status still belongs to certify_run.py /
policy_engine.py.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import setup_pi_smoke


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_ID = "pi_smoke_chain_p2_strong"
DEFAULT_OUTPUT = ROOT / ".agentic-runs" / "pi_chain_smoke_outputs" / "pi_chain_runtime_result.json"
STATUS_FILES = ["final_status.md", "certification.json", "policy_decision.json"]
STATUS_RE = re.compile(r"\b(DONE_PASS|DONE_FAIL|NOT_DONE|PROVISIONAL_DONE|CERTIFIED_DONE|BLOCKED|NEED_USER)\b")


def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def print_json(obj: dict):
    rendered = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    sys.stdout.buffer.write(rendered.encode("utf-8", errors="replace"))


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def tail(text: str, max_lines: int = 40) -> str:
    return "\n".join((text or "").splitlines()[-max_lines:])


def certifier_command(run_id: str) -> str:
    return f"python .agentic-pi/validators/certify_run.py .agentic-runs/{run_id}"


def status_paths(run_id: str) -> list[str]:
    return [f".agentic-runs/{run_id}/{name}" for name in STATUS_FILES]


def build_step_definitions(run_id: str) -> list[dict]:
    cert_cmd = certifier_command(run_id)
    status_list = "\n".join(status_paths(run_id))
    return [
        {
            "step_id": "verifier_generator_proposal",
            "agent": "verifier-generator",
            "system_prompt": ".pi/agents/verifier-generator.md",
            "tools": "read,ls",
            "allowed_to_write": False,
            "allowed_bash_command": "",
            "prompt": (
                f"Read .agentic-runs/{run_id}/goal_contract.json and "
                f".agentic-runs/{run_id}/verifier_contract.json. "
                "Propose verifier requirements only. Do not write files. "
                "Do not certify DONE yourself. Final status comes only from certify_run.py."
            ),
        },
        {
            "step_id": "verifier_reviewer_read_only",
            "agent": "verifier-reviewer",
            "system_prompt": ".pi/agents/verifier-reviewer.md",
            "tools": "read,ls",
            "allowed_to_write": False,
            "allowed_bash_command": "",
            "prompt": (
                f"Read .agentic-runs/{run_id}/verifier_artifacts and any existing "
                f".agentic-runs/{run_id}/policy_decision.json. Report verifier authority "
                "only. If a file is missing, say MISSING. Do not write files. "
                "Do not certify DONE yourself. Final status comes only from certify_run.py."
            ),
        },
        {
            "step_id": "goal_orchestrator_certify_and_report",
            "agent": "goal-orchestrator",
            "system_prompt": ".pi/agents/goal-orchestrator.md",
            "tools": "bash,read,ls",
            "allowed_to_write": False,
            "allowed_bash_command": cert_cmd,
            "prompt": (
                "Do not ask a follow-up question. You already have all required file paths. "
                f"First, run exactly one bash command: {cert_cmd}. "
                "Second, read exactly these files:\n"
                f"{status_list}\n"
                "Third, report only the statuses from those files in this format: "
                "final_status.md=<status>; certification.json=<status>; policy_decision.json=<status>. "
                "If any file is missing, say MISSING for that file. "
                "Do not certify DONE yourself. Final status comes only from certify_run.py."
            ),
        },
    ]


def build_pi_command(step: dict) -> list[str]:
    return [
        "cmd",
        "/c",
        "pi",
        "--no-extensions",
        "--no-skills",
        "--tools",
        step["tools"],
        "--append-system-prompt",
        step["system_prompt"],
        "-p",
        step["prompt"],
    ]


def run_pi_step(step: dict) -> dict:
    command = build_pi_command(step)
    result = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "step_id": step["step_id"],
        "agent": step["agent"],
        "tools": step["tools"],
        "system_prompt": step["system_prompt"],
        "pi_command": command,
        "allowed_bash_command": step["allowed_bash_command"],
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
        "stdout_tail": tail(result.stdout),
    }


def read_status_artifacts(run_id: str) -> dict:
    run_dir = ROOT / ".agentic-runs" / run_id
    values = {}
    for name in STATUS_FILES:
        path = run_dir / name
        if not path.exists():
            values[name] = "MISSING"
            continue
        if name.endswith(".json"):
            data = load_json(path)
            values[name] = data.get("status", "MISSING")
        else:
            content = path.read_text(encoding="utf-8-sig").strip()
            match = STATUS_RE.search(content)
            values[name] = match.group(1) if match else "MISSING"
    return values


def status_artifacts_agree(values: dict) -> bool:
    statuses = [value for value in values.values() if value != "MISSING"]
    return len(statuses) == 3 and len(set(statuses)) == 1


def build_result(run_id: str, live: bool, steps: list[dict], setup_report: dict | None = None) -> dict:
    status_values = read_status_artifacts(run_id) if live else {
        "final_status.md": "NOT_RUN",
        "certification.json": "NOT_RUN",
        "policy_decision.json": "NOT_RUN",
    }
    step_passed = all(step.get("passed", False) for step in steps) if live else True
    agrees = status_artifacts_agree(status_values) if live else False
    result_status = "PASS" if live and step_passed and agrees else "FAIL" if live else "PLANNED"
    return {
        "smoke_id": "controlled_pi_chain_runtime",
        "version": "v2.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "live": live,
        "result_status": result_status,
        "step_count": len(steps),
        "steps": steps,
        "setup_report": setup_report or {},
        "status_values": status_values,
        "status_artifacts_agree": agrees,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "claim_boundary": (
            "Controlled Pi chain smoke only; not proof of arbitrary autonomous "
            "goal-runner.chain.md runtime."
        ),
    }


def dry_run_result(run_id: str) -> dict:
    steps = []
    for step in build_step_definitions(run_id):
        steps.append(
            {
                "step_id": step["step_id"],
                "agent": step["agent"],
                "tools": step["tools"],
                "system_prompt": step["system_prompt"],
                "pi_command": build_pi_command(step),
                "allowed_bash_command": step["allowed_bash_command"],
                "exit_code": 0,
                "passed": True,
                "stdout_tail": "DRY_RUN_ONLY",
            }
        )
    return build_result(run_id, live=False, steps=steps)


def run_live(run_id: str, clean: bool) -> dict:
    source = ROOT / ".agentic-pi" / "diagnostics" / "evaluation" / "cases" / "p2_strong"
    setup_report = setup_pi_smoke.setup_pi_smoke(source, run_id, clean=clean)
    steps = [run_pi_step(step) for step in build_step_definitions(run_id)]
    return build_result(run_id, live=True, steps=steps, setup_report=setup_report)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run controlled Pi chain runtime smoke.")
    parser.add_argument("--target-run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--live", action="store_true", help="Actually invoke Pi. Default is dry-run.")
    parser.add_argument("--clean", action="store_true", help="Recreate the disposable pi_smoke_* run.")
    args = parser.parse_args(argv)

    if not args.target_run_id.startswith("pi_smoke_"):
        print("PI_CHAIN_SMOKE_FAILED: target run id must start with pi_smoke_")
        return 2

    if args.live and not shutil.which("pi"):
        print("PI_CHAIN_SMOKE_FAILED: pi executable not found")
        return 2

    result = run_live(args.target_run_id, args.clean) if args.live else dry_run_result(args.target_run_id)
    write_json(Path(args.output), result)
    print_json(result)
    return 0 if result["result_status"] in {"PASS", "PLANNED"} else 1


if __name__ == "__main__":
    sys.exit(main())
