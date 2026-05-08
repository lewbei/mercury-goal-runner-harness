#!/usr/bin/env python3
"""Run a controlled real Pi/Mercury agentic autonomy probe.

The probe is disposable and intentionally starts from a missing target artifact
so Mercury must attempt a bounded repair loop before final certification.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import agentic_autonomy_monitor
import pi_session_trace_monitor
import setup_pi_smoke


ROOT = Path(__file__).resolve().parents[2]
VERSION = "v2.8"
DEFAULT_RUN_ID = "pi_smoke_agentic_autonomy_001"
SOURCE_CASE = ROOT / ".agentic-pi" / "diagnostics" / "evaluation" / "cases" / "p2_strong"
OUTPUT_ROOT = ROOT / ".agentic-runs" / "agentic_autonomy_outputs"
TARGET_ARTIFACT = "artifacts/output.txt"


def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def setup_probe_run(run_id: str, clean: bool) -> dict:
    report = setup_pi_smoke.setup_pi_smoke(SOURCE_CASE, run_id, clean=clean)
    target = ROOT / ".agentic-runs" / run_id / TARGET_ARTIFACT
    if target.exists():
        target.unlink()
    report["removed_target_artifact_for_repair_probe"] = TARGET_ARTIFACT
    report["expected_initial_certifier_status"] = "NOT_DONE"
    report["expected_final_status_after_repair"] = "CERTIFIED_DONE"
    return report


def certifier_command(run_id: str) -> str:
    return f"python .agentic-pi/validators/certify_run.py .agentic-runs/{run_id}"


def build_prompt(run_id: str) -> str:
    return (
        "Do not ask a follow-up question. "
        "You are Mercury inside Pi. "
        "Do not certify DONE yourself. "
        "Use .pi/chains/goal-runner.chain.md as the chain contract. "
        f"Work only inside disposable run .agentic-runs/{run_id}/ except for reading repo docs and memory. "
        "Read .pi/chains/goal-runner.chain.md. "
        "Read .agentic-pi/memory/user_constraints.jsonl as advisory memory only. "
        "Plan at least three steps in your own reasoning before acting. "
        f"First run the certifier command: {certifier_command(run_id)}. "
        "It should fail because artifacts/output.txt is missing. "
        f"Repair by creating .agentic-runs/{run_id}/artifacts/output.txt with exactly this text: correct behavior. "
        "Do not edit final_status.md, certification.json, policy_decision.json, or verifier_artifacts manually. "
        "After the repair, run the same certifier command one final time. "
        f"Then read .agentic-runs/{run_id}/final_status.md, .agentic-runs/{run_id}/certification.json, and .agentic-runs/{run_id}/policy_decision.json. "
        "Report a JSON object only with keys: result_status, status_values, status_artifacts_agree, final_status_authority, can_certify_done, repair_attempted, claim_boundary. "
        "Set result_status to PASS only if the three status artifacts agree and no status file is missing. "
        "Set final_status_authority to certifier_only. "
        "Set can_certify_done to false. "
        f"Set claim_boundary exactly to: {agentic_autonomy_monitor.EXPECTED_CLAIM_BOUNDARY} "
        "Use exact status_values keys: final_status.md, certification.json, policy_decision.json. "
        "Final status comes only from certify_run.py and policy_engine.py."
    )


def build_pi_command(prompt: str) -> list[str]:
    return [
        "cmd",
        "/c",
        "pi",
        "--no-extensions",
        "--no-skills",
        "--tools",
        "bash,read,ls",
        "--mode",
        "json",
        "--append-system-prompt",
        ".pi/agents/goal-orchestrator.md",
        "-p",
        prompt,
    ]


def run_live_pi(prompt: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        build_pi_command(prompt),
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_probe(run_id: str, live: bool, clean: bool, transcript_path: Path | None = None) -> dict:
    if not run_id.startswith("pi_smoke_"):
        raise ValueError("target run id must start with pi_smoke_")

    run_dir = ROOT / ".agentic-runs" / run_id
    setup_report = setup_probe_run(run_id, clean=clean)

    if transcript_path:
        stdout = transcript_path.read_text(encoding="utf-8-sig")
        exit_code = 0
    elif live:
        if not shutil.which("pi"):
            raise RuntimeError("pi executable not found")
        result = run_live_pi(build_prompt(run_id))
        stdout = result.stdout or ""
        exit_code = result.returncode
    else:
        stdout = ""
        exit_code = 0

    raw_output_path = run_dir / "agentic_autonomy_raw_output.jsonl"
    trace_path = run_dir / "agentic_autonomy_trace.jsonl"
    monitor_path = run_dir / "agentic_autonomy_monitor_result.json"

    raw_output_path.write_text(stdout, encoding="utf-8")
    events = pi_session_trace_monitor.events_from_capture(
        stdout,
        run_id,
        source="agentic_autonomy_pi_json" if live else "agentic_autonomy_fixture",
        capture_format="pi-json" if live else "auto",
    )
    pi_session_trace_monitor.write_jsonl(trace_path, events)
    monitor_report = agentic_autonomy_monitor.monitor_agentic_trace(trace_path, run_id, ROOT)
    write_json(monitor_path, monitor_report)

    output = {
        "probe_id": "real_pi_agentic_autonomy_probe",
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "live": live,
        "result_status": "PASS" if exit_code == 0 and monitor_report["monitor_status"] == "PASS" else "FAIL",
        "pi_exit_code": exit_code,
        "setup_report": setup_report,
        "monitor_status": monitor_report["monitor_status"],
        "status_values": monitor_report["status_values"],
        "status_artifacts_agree": monitor_report["status_artifacts_agree"],
        "bash_command_count": monitor_report["bash_command_count"],
        "certifier_call_count": monitor_report["certifier_call_count"],
        "repair_command_count": monitor_report["repair_command_count"],
        "read_only_repo_command_count": monitor_report["read_only_repo_command_count"],
        "read_only_repo_tool_call_count": monitor_report["read_only_repo_tool_call_count"],
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "trace_path": str(trace_path),
        "raw_output_path": str(raw_output_path),
        "monitor_path": str(monitor_path),
        "claim_boundary": agentic_autonomy_monitor.EXPECTED_CLAIM_BOUNDARY,
    }
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the real Pi agentic autonomy probe.")
    parser.add_argument("--target-run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--live", action="store_true", help="Invoke the real external pi CLI.")
    parser.add_argument("--clean", action="store_true", help="Recreate the disposable probe run.")
    parser.add_argument("--from-transcript")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    output_path = Path(args.output) if args.output else OUTPUT_ROOT / f"{args.target_run_id}_result.json"
    try:
        result = run_probe(
            args.target_run_id,
            live=args.live,
            clean=args.clean,
            transcript_path=Path(args.from_transcript) if args.from_transcript else None,
        )
    except Exception as exc:
        print(f"AGENTIC_AUTONOMY_PROBE_FAILED: {exc}")
        return 1

    write_json(output_path, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["result_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
