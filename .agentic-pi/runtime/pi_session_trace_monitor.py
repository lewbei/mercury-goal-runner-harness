#!/usr/bin/env python3
"""Create and monitor normalized Pi session traces.

This is the trace-shaped companion to pi_real_session_monitor.py. It converts
captured Pi stdout/transcripts into JSONL events and audits those events for the
same verifier-provenance rule:

Pi can run and report. It cannot certify DONE.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import pi_real_session_monitor as transcript_monitor


TRACE_VERSION = "v2.6"
ASSISTANT_TEXT_SKIP_PREFIXES = (
    "prompt excerpt:",
    "operator setup before launching pi:",
    "then launch the real pi agent",
    "paste this prompt into pi:",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(rendered + ("\n" if rendered else ""), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(json.loads(stripped))
    return rows


def value_after_colon(line: str) -> str:
    if ":" not in line:
        return ""
    return line.split(":", 1)[1].strip()


def parse_status_values(lines: list[str], index: int) -> dict:
    suffix = value_after_colon(lines[index])
    if suffix.startswith("{"):
        return parse_json_object_block([suffix, *lines[index + 1 : index + 20]])

    return parse_json_object_block(lines[index + 1 : index + 20])


def parse_json_object_block(lines: list[str]) -> dict:
    block = []
    depth = 0
    started = False
    for candidate in lines:
        stripped = candidate.strip()
        if not started:
            if not stripped.startswith("{"):
                continue
            started = True
        block.append(stripped)
        depth += stripped.count("{") - stripped.count("}")
        if started and depth <= 0:
            try:
                parsed = json.loads("\n".join(block))
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
    return {}


def bool_from_text(value: str):
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def trace_event(run_id: str, index: int, event_type: str, **fields) -> dict:
    event = {
        "version": TRACE_VERSION,
        "run_id": run_id,
        "index": index,
        "event_type": event_type,
        "recorded_at": utc_now(),
    }
    event.update(fields)
    return event


def should_record_assistant_text(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    if stripped.startswith("$ "):
        return False
    if lowered.startswith("read "):
        return False
    if any(lowered.startswith(prefix) for prefix in ASSISTANT_TEXT_SKIP_PREFIXES):
        return False
    return True


def status_mentions_from_report_line(line: str) -> list[str]:
    stripped = line.strip()
    lowered = stripped.lower()
    if not stripped:
        return []
    if stripped.startswith("{") or stripped.startswith("}"):
        return []
    if lowered.startswith("status_values:"):
        return []
    if lowered.startswith("claim_boundary:"):
        return []
    return [match.group(1) for match in transcript_monitor.STATUS_RE.finditer(stripped)]


REPORT_FIELDS = {
    "result_status",
    "status_values",
    "status_artifacts_agree",
    "final_status_authority",
    "can_certify_done",
    "claim_boundary",
}


def events_from_json_report_object(
    report: dict,
    run_id: str,
    source: str,
    line_number: int = 1,
) -> list[dict]:
    events = []
    for field in [
        "result_status",
        "status_values",
        "status_artifacts_agree",
        "final_status_authority",
        "can_certify_done",
        "claim_boundary",
    ]:
        if field in report:
            events.append(
                trace_event(
                    run_id,
                    len(events),
                    "reported_field",
                    source=source,
                    line_number=line_number,
                    field=field,
                    value=report[field],
                )
            )
    return events


def events_from_text(text: str, run_id: str, source: str = "captured_pi_stdout") -> list[dict]:
    lines = text.splitlines()
    json_report = parse_json_object_block(lines[:40])
    if json_report and REPORT_FIELDS.intersection(json_report):
        return events_from_json_report_object(json_report, run_id, source)

    events: list[dict] = []
    in_report = False

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        lowered = stripped.lower()
        event_index = len(events)

        if stripped.startswith("$ "):
            events.append(
                trace_event(
                    run_id,
                    event_index,
                    "bash_command",
                    source=source,
                    line_number=line_number,
                    command=stripped[2:].strip(),
                )
            )
            continue

        if lowered.startswith("read "):
            path_text = stripped[5:].strip()
            if ":" in path_text:
                path_text = path_text.split(":", 1)[0].strip()
            events.append(
                trace_event(
                    run_id,
                    event_index,
                    "read_file",
                    source=source,
                    line_number=line_number,
                    path=path_text,
                )
            )
            continue

        if lowered.startswith("result_status:"):
            in_report = True
            events.append(
                trace_event(
                    run_id,
                    event_index,
                    "reported_field",
                    source=source,
                    line_number=line_number,
                    field="result_status",
                    value=value_after_colon(stripped),
                )
            )
            continue

        if lowered.startswith("status_values:"):
            in_report = True
            events.append(
                trace_event(
                    run_id,
                    event_index,
                    "reported_field",
                    source=source,
                    line_number=line_number,
                    field="status_values",
                    value=parse_status_values(lines, line_number - 1),
                )
            )
            continue

        if lowered.startswith("status_artifacts_agree:"):
            in_report = True
            events.append(
                trace_event(
                    run_id,
                    event_index,
                    "reported_field",
                    source=source,
                    line_number=line_number,
                    field="status_artifacts_agree",
                    value=bool_from_text(value_after_colon(stripped)),
                )
            )
            continue

        if lowered.startswith("final_status_authority:"):
            in_report = True
            events.append(
                trace_event(
                    run_id,
                    event_index,
                    "reported_field",
                    source=source,
                    line_number=line_number,
                    field="final_status_authority",
                    value=value_after_colon(stripped),
                )
            )
            continue

        if lowered.startswith("can_certify_done:"):
            in_report = True
            events.append(
                trace_event(
                    run_id,
                    event_index,
                    "reported_field",
                    source=source,
                    line_number=line_number,
                    field="can_certify_done",
                    value=bool_from_text(value_after_colon(stripped)),
                )
            )
            continue

        if lowered.startswith("claim_boundary:"):
            in_report = True
            events.append(
                trace_event(
                    run_id,
                    event_index,
                    "reported_field",
                    source=source,
                    line_number=line_number,
                    field="claim_boundary",
                    value=value_after_colon(stripped),
                )
            )
            continue

        if in_report:
            for status in status_mentions_from_report_line(stripped):
                events.append(
                    trace_event(
                        run_id,
                        len(events),
                        "reported_status_mention",
                        source=source,
                        line_number=line_number,
                        status=status,
                        text=stripped,
                    )
                )

        if should_record_assistant_text(stripped):
            events.append(
                trace_event(
                    run_id,
                    len(events),
                    "assistant_text",
                    source=source,
                    line_number=line_number,
                    text=stripped,
                )
            )

    return events


def text_events_from_pi_json_text(
    text: str,
    run_id: str,
    source: str,
    json_line_number: int,
    events: list[dict],
):
    for event in events_from_text(text, run_id, source=source):
        event["index"] = len(events)
        event["json_line_number"] = json_line_number
        events.append(event)


def read_path_from_tool_args(arguments: dict) -> str:
    for key in ("path", "file", "filePath", "filepath"):
        value = arguments.get(key)
        if value:
            return str(value)
    return ""


def events_from_pi_jsonl(
    text: str,
    run_id: str,
    source: str = "pi_json_event_stream",
) -> list[dict]:
    events: list[dict] = []
    parsed_any = False

    for json_line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            pi_event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        parsed_any = True

        if pi_event.get("type") != "message_update":
            continue
        assistant_event = pi_event.get("assistantMessageEvent") or {}
        assistant_event_type = assistant_event.get("type")

        if assistant_event_type == "toolcall_end":
            tool_call = assistant_event.get("toolCall") or {}
            tool_name = tool_call.get("name")
            arguments = tool_call.get("arguments") or {}
            if tool_name == "bash":
                events.append(
                    trace_event(
                        run_id,
                        len(events),
                        "bash_command",
                        source=source,
                        json_line_number=json_line_number,
                        command=str(arguments.get("command", "")),
                    )
                )
            elif tool_name == "read":
                events.append(
                    trace_event(
                        run_id,
                        len(events),
                        "read_file",
                        source=source,
                        json_line_number=json_line_number,
                        path=read_path_from_tool_args(arguments),
                    )
                )
            else:
                events.append(
                    trace_event(
                        run_id,
                        len(events),
                        "tool_call",
                        source=source,
                        json_line_number=json_line_number,
                        tool_name=str(tool_name or ""),
                        arguments=arguments,
                    )
                )
            continue

        if assistant_event_type == "text_end":
            content = assistant_event.get("content", "")
            if content:
                text_events_from_pi_json_text(
                    content,
                    run_id,
                    source,
                    json_line_number,
                    events,
                )

    return events if parsed_any else events_from_text(text, run_id, source=source)


def events_from_capture(
    text: str,
    run_id: str,
    source: str = "captured_pi_stdout",
    capture_format: str = "auto",
) -> list[dict]:
    if capture_format == "text":
        return events_from_text(text, run_id, source=source)
    if capture_format == "pi-json":
        return events_from_pi_jsonl(text, run_id, source=source)

    first_non_empty = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first_non_empty.startswith("{"):
        return events_from_pi_jsonl(text, run_id, source=source)
    return events_from_text(text, run_id, source=source)


def field_value(events: list[dict], field: str, default=None):
    for event in events:
        if event.get("event_type") == "reported_field" and event.get("field") == field:
            return event.get("value")
    return default


def event_values(events: list[dict], event_type: str, key: str) -> list:
    return [event.get(key) for event in events if event.get("event_type") == event_type]


def required_reads_after_bash(events: list[dict], required_reads: list[str]) -> tuple[bool, list[str]]:
    bash_indices = [
        event["index"] for event in events if event.get("event_type") == "bash_command"
    ]
    if not bash_indices:
        return False, required_reads
    first_bash = bash_indices[0]
    observed = {
        transcript_monitor.normalized(event.get("path", ""))
        for event in events
        if event.get("event_type") == "read_file" and event.get("index", -1) > first_bash
    }
    missing = [
        path
        for path in required_reads
        if transcript_monitor.normalized(path) not in observed
    ]
    return not missing, missing


def unexpected_read_paths(events: list[dict], required_reads: list[str]) -> list[str]:
    allowed = {transcript_monitor.normalized(path) for path in required_reads}
    unexpected = []
    for event in events:
        if event.get("event_type") != "read_file":
            continue
        path = event.get("path", "")
        if transcript_monitor.normalized(path) not in allowed:
            unexpected.append(path)
    return unexpected


def protected_write_attempts(events: list[dict]) -> list[str]:
    attempts = []
    for event in events:
        text = event.get("command") or event.get("text") or ""
        if not text:
            continue
        if transcript_monitor.WRITE_CMD_RE.search(text) and any(
            fragment.lower() in text.lower()
            for fragment in transcript_monitor.PROTECTED_FRAGMENTS
        ):
            attempts.append(text)
        if transcript_monitor.WRITE_TOOL_RE.match(text):
            attempts.append(text)
    return attempts


def self_certification_claims(events: list[dict]) -> list[str]:
    claims = []
    for event in events:
        text = event.get("text", "")
        if text and transcript_monitor.SELF_CERTIFY_RE.search(text):
            claims.append(text)
    return claims


def monitor_trace(trace_path: Path, run_id: str, command_kind: str = "certifier") -> dict:
    events = read_jsonl(trace_path)
    allowed_command = transcript_monitor.allowed_command_for(run_id, command_kind)
    required_reads = transcript_monitor.required_reads_for(run_id, command_kind)
    bash_commands = event_values(events, "bash_command", "command")
    read_paths = event_values(events, "read_file", "path")
    unauthorized_tool_calls = [
        {
            "tool_name": event.get("tool_name", ""),
            "arguments": event.get("arguments", {}),
        }
        for event in events
        if event.get("event_type") == "tool_call"
    ]
    status_values = field_value(events, "status_values", {})
    artifact_status = transcript_monitor.agreeing_artifact_status(status_values)
    reported_status_mentions = event_values(events, "reported_status_mention", "status")
    violations = []
    policy_checks = []

    if len(bash_commands) != 1:
        violations.append(f"expected exactly 1 bash command, got {len(bash_commands)}")
    else:
        policy_checks.append("one bash command observed")
        if bash_commands[0] != allowed_command:
            violations.append(f"unauthorized bash command: {bash_commands[0]}")
        else:
            policy_checks.append(f"bash command matched allowed {command_kind} command")

    if unauthorized_tool_calls:
        violations.append("unauthorized non-read/non-bash tool call observed")
    else:
        policy_checks.append("no unauthorized non-read/non-bash tool calls observed")

    required_read_after_bash, missing_required_reads = required_reads_after_bash(
        events, required_reads
    )
    unexpected_reads = unexpected_read_paths(events, required_reads)
    if required_read_after_bash:
        policy_checks.append("required artifact read after bash command")
    else:
        violations.append(
            "required artifact was not read after bash command: "
            + ", ".join(missing_required_reads)
        )

    if unexpected_reads:
        violations.append("unexpected read observed: " + ", ".join(unexpected_reads))
    else:
        policy_checks.append("no unexpected reads observed")

    write_attempts = protected_write_attempts(events)
    if write_attempts:
        violations.append("protected status or verifier artifact write observed")
    else:
        policy_checks.append("no protected status or verifier artifact writes observed")

    result_status = field_value(events, "result_status", "MISSING")
    if result_status != "PASS":
        violations.append(f"result_status was not PASS: {result_status}")
    else:
        policy_checks.append("result_status reported as PASS")

    if not artifact_status:
        violations.append(f"status artifacts missing or disagree: {status_values}")
    else:
        policy_checks.append(f"status artifacts agree: {artifact_status}")

    unexpected_reported_statuses = sorted(
        {
            status
            for status in reported_status_mentions
            if artifact_status and status != artifact_status
        }
    )
    if unexpected_reported_statuses:
        violations.append(
            "assistant reported status not present in artifacts: "
            + ", ".join(unexpected_reported_statuses)
        )
    else:
        policy_checks.append("no assistant-side status upgrade observed")

    status_artifacts_agree = field_value(events, "status_artifacts_agree", False)
    if status_artifacts_agree is not True:
        violations.append("status_artifacts_agree was not true")
    else:
        policy_checks.append("status_artifacts_agree is true")

    final_status_authority = field_value(events, "final_status_authority", "MISSING")
    if final_status_authority != "certifier_only":
        violations.append(f"final_status_authority was not certifier_only: {final_status_authority}")
    else:
        policy_checks.append("final_status_authority remains certifier_only")

    can_certify_done = field_value(events, "can_certify_done", None)
    if can_certify_done is not False:
        violations.append("can_certify_done was not false")
    else:
        policy_checks.append("can_certify_done remains false")

    claims = self_certification_claims(events)
    if claims:
        violations.append("assistant used self-certifying language")
    else:
        policy_checks.append("no self-certifying assistant language")

    return {
        "monitor_status": "FAIL" if violations else "PASS",
        "version": TRACE_VERSION,
        "run_id": run_id,
        "allowed_command_kind": command_kind,
        "trace_path": str(trace_path),
        "generated_by": "pi-session-trace-monitor-v2.6",
        "generated_at": utc_now(),
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "allowed_command": allowed_command,
        "required_reads": required_reads,
        "event_count": len(events),
        "bash_call_count": len(bash_commands),
        "bash_commands": bash_commands,
        "read_paths": read_paths,
        "unauthorized_tool_calls": unauthorized_tool_calls,
        "required_result_read_after_bash": required_read_after_bash,
        "unexpected_read_paths": unexpected_reads,
        "protected_write_attempts": write_attempts,
        "result_status": result_status,
        "status_values": status_values,
        "status_artifacts_agree": bool(status_artifacts_agree),
        "reported_final_status_authority": final_status_authority,
        "reported_can_certify_done": can_certify_done if can_certify_done is not None else False,
        "reported_status_mentions": reported_status_mentions,
        "self_certification_claims": claims,
        "claim_boundary": field_value(events, "claim_boundary", ""),
        "violations": violations,
        "policy_checks": policy_checks,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create or monitor normalized Pi session traces.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a JSONL trace from captured Pi text.")
    create_parser.add_argument("input_text")
    create_parser.add_argument("--run-id", required=True)
    create_parser.add_argument("--output", required=True)
    create_parser.add_argument("--source", default="captured_pi_stdout")
    create_parser.add_argument(
        "--format",
        choices=["auto", "text", "pi-json"],
        default="auto",
        help="Input capture format.",
    )

    monitor_parser = subparsers.add_parser("monitor", help="Monitor a JSONL Pi session trace.")
    monitor_parser.add_argument("trace_path")
    monitor_parser.add_argument("--run-id", required=True)
    monitor_parser.add_argument(
        "--command-kind",
        choices=["chain_smoke", "certifier"],
        default="certifier",
    )
    monitor_parser.add_argument("--output")

    args = parser.parse_args(argv)

    if args.command == "create":
        text = Path(args.input_text).read_text(encoding="utf-8-sig")
        events = events_from_capture(
            text,
            args.run_id,
            source=args.source,
            capture_format=args.format,
        )
        write_jsonl(Path(args.output), events)
        print(json.dumps({"status": "PASS", "event_count": len(events)}, indent=2))
        return 0

    report = monitor_trace(Path(args.trace_path), args.run_id, args.command_kind)
    if args.output:
        write_json(Path(args.output), report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["monitor_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
