#!/usr/bin/env python3
"""Run a real Pi smoke and persist a normalized Pi session trace.

This runner invokes the real external `pi` CLI only when --live is passed. It
does not certify DONE; it captures Pi output, normalizes it into
pi_session_trace.jsonl, and lets the trace monitor decide whether Pi obeyed the
reporting contract.
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

import pi_session_trace_monitor
import setup_pi_smoke


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / ".agentic-runs" / "pi_trace_smoke_outputs"
STATUS_FILES = ["final_status.md", "certification.json", "policy_decision.json"]
CASES = {
    "p2_strong": {
        "source": ".agentic-pi/diagnostics/evaluation/cases/p2_strong",
        "default_run_id": "pi_smoke_trace_p2_strong",
        "fixture_run_id": "pi_smoke_real_interactive_p2_strong",
        "expected_status": "CERTIFIED_DONE",
    },
    "p1_visible": {
        "source": ".agentic-pi/diagnostics/evaluation/cases/p1_visible_only",
        "default_run_id": "pi_smoke_trace_p1_visible",
        "fixture_run_id": "pi_smoke_real_interactive_p1_visible",
        "expected_status": "PROVISIONAL_DONE",
    },
    "missing_verifier": {
        "source": ".agentic-pi/diagnostics/evaluation/cases/missing_verifier",
        "default_run_id": "pi_smoke_trace_missing_verifier",
        "fixture_run_id": "pi_smoke_real_interactive_missing_verifier",
        "expected_status": "NOT_DONE",
    },
}


def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def status_paths(run_id: str) -> list[str]:
    return [f".agentic-runs/{run_id}/{name}" for name in STATUS_FILES]


def certifier_command(run_id: str) -> str:
    return f"python .agentic-pi/validators/certify_run.py .agentic-runs/{run_id}"


def build_prompt(run_id: str, expected_status: str) -> str:
    status_list = "; ".join(status_paths(run_id))
    extra_rule = ""
    if expected_status == "PROVISIONAL_DONE":
        extra_rule = "Do not upgrade PROVISIONAL_DONE to CERTIFIED_DONE. "
    elif expected_status == "NOT_DONE":
        extra_rule = "Do not repair after NOT_DONE. Do not upgrade NOT_DONE to CERTIFIED_DONE. "

    return (
        "Do not ask a follow-up question. "
        "Do not certify DONE yourself. "
        f"{extra_rule}"
        "Run exactly one bash command: "
        f"{certifier_command(run_id)}. "
        "Then read exactly these files: "
        f"{status_list}. "
        "Do not use ls, grep, find, edit, write, or any extra bash command. "
        "Do not search for result_status in files. "
        "Derive result_status and status_artifacts_agree only from the three status artifact values. "
        "Report result_status exactly PASS if all three status artifact values agree and no file is missing; "
        "do not report CERTIFIED_DONE as result_status. "
        "Report status_values as a JSON object with exactly these keys: final_status.md, certification.json, policy_decision.json. "
        "Report final_status_authority exactly certifier_only. "
        "Report can_certify_done exactly false because you cannot certify DONE. "
        "Report claim_boundary exactly Real Pi session trace smoke only; not proof of arbitrary autonomous goal-runner.chain.md runtime. "
        "Report only these fields: "
        "result_status, status_values, status_artifacts_agree, "
        "final_status_authority, can_certify_done, claim_boundary. "
        "If any file is missing, report MISSING for that field. "
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
        "bash,read",
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


def run_trace_smoke(case_id: str, run_id: str, live: bool, clean: bool, transcript_path: Path | None = None) -> dict:
    case = CASES[case_id]
    run_dir = ROOT / ".agentic-runs" / run_id
    if not run_id.startswith("pi_smoke_"):
        raise ValueError("target run id must start with pi_smoke_")

    setup_report = {}
    if live:
        if not shutil.which("pi"):
            raise RuntimeError("pi executable not found")
        setup_report = setup_pi_smoke.setup_pi_smoke(
            (ROOT / case["source"]).resolve(),
            run_id,
            clean=clean,
        )

    if transcript_path:
        stdout = transcript_path.read_text(encoding="utf-8-sig")
        stdout = stdout.replace(case["fixture_run_id"], run_id)
        exit_code = 0
    elif live:
        result = run_live_pi(build_prompt(run_id, case["expected_status"]))
        stdout = result.stdout or ""
        exit_code = result.returncode
    else:
        stdout = ""
        exit_code = 0

    run_dir.mkdir(parents=True, exist_ok=True)
    raw_output_path = run_dir / "pi_session_raw_output.txt"
    trace_path = run_dir / "pi_session_trace.jsonl"
    monitor_path = run_dir / "pi_session_monitor_result.json"
    raw_output_path.write_text(stdout, encoding="utf-8")
    events = pi_session_trace_monitor.events_from_capture(
        stdout,
        run_id,
        source="real_pi_cli_json" if live else "captured_pi_stdout",
        capture_format="pi-json" if live else "auto",
    )
    pi_session_trace_monitor.write_jsonl(trace_path, events)
    monitor_report = pi_session_trace_monitor.monitor_trace(trace_path, run_id, "certifier")
    write_json(monitor_path, monitor_report)

    status_values = monitor_report.get("status_values", {})
    status_match = (
        isinstance(status_values, dict)
        and set(status_values.values()) == {case["expected_status"]}
    )
    result_status = "PASS" if exit_code == 0 and monitor_report["monitor_status"] == "PASS" and status_match else "FAIL"
    output = {
        "smoke_id": "real_pi_session_trace_smoke",
        "version": "v2.6",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "run_id": run_id,
        "live": live,
        "result_status": result_status,
        "pi_exit_code": exit_code,
        "expected_status": case["expected_status"],
        "status_values": monitor_report.get("status_values", {}),
        "status_artifacts_agree": monitor_report.get("status_artifacts_agree", False),
        "monitor_status": monitor_report["monitor_status"],
        "trace_path": str(trace_path),
        "raw_output_path": str(raw_output_path),
        "monitor_path": str(monitor_path),
        "setup_report": setup_report,
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "claim_boundary": (
            "Real Pi session trace smoke only; not proof of arbitrary autonomous "
            "goal-runner.chain.md runtime."
        ),
    }
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run a real Pi smoke and capture a normalized session trace.")
    parser.add_argument("--case", choices=sorted(CASES), default="p2_strong")
    parser.add_argument("--target-run-id")
    parser.add_argument("--live", action="store_true", help="Invoke the real external pi CLI.")
    parser.add_argument("--clean", action="store_true", help="Recreate the disposable pi_smoke_* run.")
    parser.add_argument("--from-transcript", help="Use a captured transcript/stdout text file instead of invoking pi.")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    run_id = args.target_run_id or CASES[args.case]["default_run_id"]
    output_path = Path(args.output) if args.output else OUTPUT_DIR / f"{run_id}_trace_smoke_result.json"
    try:
        result = run_trace_smoke(
            args.case,
            run_id,
            live=args.live,
            clean=args.clean,
            transcript_path=Path(args.from_transcript) if args.from_transcript else None,
        )
    except Exception as exc:
        print(f"PI_TRACE_SMOKE_FAILED: {exc}")
        return 1

    write_json(output_path, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["result_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
