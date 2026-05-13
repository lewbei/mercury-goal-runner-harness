#!/usr/bin/env python3
"""Run Stage 1 live capture tasks through Mercury via the Pi CLI.

This script creates live capture evidence only. It does not score outputs and it
does not certify DONE. Use a small subset before a full 50-prompt run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage1_multiframe"
DEFAULT_REQUEST_PACK = DEFAULT_DIR / "live_capture_request_pack.json"
DEFAULT_OUTPUT = DEFAULT_DIR / "live_capture_mercury_subset_5.json"
DEFAULT_SYSTEM_PROMPT = (
    "You are responding to a Stage 1 A/B benchmark prompt. "
    "Answer the supplied benchmark task only. "
    "Do not claim certification, final status, or DONE."
)
MODEL_ID = "inception/mercury-2"
PROTECTED_OUTPUT_NAMES = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    if path.name in PROTECTED_OUTPUT_NAMES:
        raise ValueError(f"refusing to write protected status artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def selected_tasks(request_pack: dict[str, Any], prompt_limit: int) -> list[dict[str, Any]]:
    selected_prompt_ids: list[str] = []
    for task in request_pack["tasks"]:
        prompt_id = task["prompt_id"]
        if prompt_id not in selected_prompt_ids:
            selected_prompt_ids.append(prompt_id)
        if len(selected_prompt_ids) == prompt_limit:
            break
    selected = [task for task in request_pack["tasks"] if task["prompt_id"] in selected_prompt_ids]
    mode_order = {"normal_prompt": 0, "multiframe_harness": 1}
    return sorted(selected, key=lambda item: (selected_prompt_ids.index(item["prompt_id"]), mode_order[item["mode"]]))


def call_mercury(instruction: str, *, system_prompt: str, timeout_seconds: int) -> str:
    # Windows .cmd shims can mis-handle literal newlines in argv. Keep the
    # semantic instruction but pass it as one flat CLI argument.
    cli_instruction = " ".join(instruction.split())
    pi_executable = shutil.which("pi") or shutil.which("pi.cmd")
    if not pi_executable:
        raise RuntimeError("Pi CLI executable not found on PATH")
    cmd = [
        pi_executable,
        "--model",
        MODEL_ID,
        "--thinking",
        "off",
        "--mode",
        "text",
        "--no-tools",
        "--no-context-files",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-session",
        "--system-prompt",
        system_prompt,
        "-p",
        cli_instruction,
    ]
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Mercury capture failed with exit code {result.returncode}: {result.stdout}")
    output = result.stdout.strip()
    if not output:
        raise RuntimeError("Mercury capture returned empty output")
    return output


def build_capture(request_pack: dict[str, Any], tasks: list[dict[str, Any]], *, system_prompt: str, timeout_seconds: int, sleep_seconds: float) -> dict[str, Any]:
    captures: list[dict[str, Any]] = []
    system_prompt_hash = sha256_text(system_prompt)
    for index, task in enumerate(tasks, start=1):
        print(f"[{index}/{len(tasks)}] Mercury capture {task['task_id']}", file=sys.stderr, flush=True)
        output_text = call_mercury(task["capture_instruction"], system_prompt=system_prompt, timeout_seconds=timeout_seconds)
        captures.append(
            {
                "prompt_id": task["prompt_id"],
                "mode": task["mode"],
                "provider": "inception",
                "model": "mercury-2",
                "model_version": MODEL_ID,
                "prompt_text": task["prompt_text"],
                "prompt_hash": task["prompt_hash"],
                "system_prompt_hash": system_prompt_hash,
                "output_text": output_text,
                "output_hash": sha256_text(output_text),
                "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "capture_method": "pi_cli_noninteractive_no_tools_no_session",
                "provenance": {
                    "temperature": None,
                    "max_output_tokens": None,
                    "attempt_number": 1,
                    "session_ref": "pi_cli_--no-session",
                    "tool_calls_allowed": False,
                    "tool_call_count": 0,
                    "notes": "Captured with pi CLI using --model inception/mercury-2, --no-tools, --no-session. Pi CLI did not expose temperature, max output tokens, or provider request id.",
                },
            }
        )
        if sleep_seconds and index < len(tasks):
            time.sleep(sleep_seconds)
    return {
        "schema_version": "stage1_live_capture_v1",
        "capture_id": f"stage1_mercury_live_subset_{len(set(task['prompt_id'] for task in tasks))}_prompts_v1",
        "prompt_set_id": request_pack["prompt_set_id"],
        "capture_scope": "subset_fixture_only",
        "authority": {
            "authority_level": "evaluation_capture_only",
            "final_status_authority": "certifier_only",
            "can_certify_done": False,
        },
        "capture_environment": {
            "captured_by": "pi_cli_mercury_runner",
            "capture_tool": "run_mercury_live_capture.py",
            "notes": "Live Mercury subset capture. This is not full Stage 1 settlement evidence and not certification.",
        },
        "captures": captures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Stage 1 Mercury live capture subset via Pi CLI")
    parser.add_argument("--request-pack", default=str(DEFAULT_REQUEST_PACK))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--prompt-limit", type=int, default=5, help="number of prompt pairs to capture")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--system-prompt", default=DEFAULT_SYSTEM_PROMPT)
    args = parser.parse_args(argv)

    if args.prompt_limit < 1 or args.prompt_limit > 50:
        raise SystemExit("--prompt-limit must be between 1 and 50")
    request_pack = load_json(Path(args.request_pack))
    tasks = selected_tasks(request_pack, args.prompt_limit)
    capture = build_capture(
        request_pack,
        tasks,
        system_prompt=args.system_prompt,
        timeout_seconds=args.timeout_seconds,
        sleep_seconds=args.sleep_seconds,
    )
    write_json(Path(args.output), capture)
    print(f"OK: wrote Mercury live capture to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
