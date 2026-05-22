"""Artifact command-test helpers for the certifier runner.

This module owns only the narrow command-test surface used by certifier-owned
artifact tests. It does not create verifier artifacts, invoke policy, run gates,
or write result artifacts.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from certifier_paths import PROTECTED_NAMES, PROTECTED_PREFIXES, find_output, resolve_run_path, run_relative


ALLOWED_ARTIFACT_COMMAND_EXECUTABLES = {"python", "python3"}
FORBIDDEN_ARTIFACT_COMMAND_CHARS = set("\n\r;&|<>`$")
FORBIDDEN_ARTIFACT_COMMAND_TOKENS = {"&&", "||", ";", "|", ">", ">>", "<", "2>", "&"}


def split_artifact_command(cmd: str) -> list[str]:
    return shlex.split(cmd, posix=(os.name != "nt"))


def validate_artifact_command_allowlist(run_dir: Path, cmd: str, cmd_parts: list[str]) -> tuple[bool, list[str], list[str]]:
    """Validate and normalize an artifact-test command before execution.

    Artifact tests are certifier-owned checks, but their command strings come
    from goal_contract.json. Keep the command surface deliberately narrow:
    run-local Python scripts only, no shell operators, no Python -c/-m, no path
    escapes, no protected status-artifact references. The returned command uses
    this interpreter instead of trusting PATH.
    """
    reasons: list[str] = []
    if any(ch in cmd for ch in FORBIDDEN_ARTIFACT_COMMAND_CHARS):
        reasons.append("contains shell metacharacter or newline")
    if any(part in FORBIDDEN_ARTIFACT_COMMAND_TOKENS for part in cmd_parts):
        reasons.append("contains shell operator token")
    if len(cmd_parts) < 2:
        reasons.append("expected 'python <run-relative-script.py> [args...]'")
        return False, [], reasons

    executable = cmd_parts[0]
    if Path(executable).name != executable:
        reasons.append("python executable must be a bare allowlisted name")
    if executable.lower() not in ALLOWED_ARTIFACT_COMMAND_EXECUTABLES:
        reasons.append(f"executable {executable!r} is not allowlisted")

    script_arg = cmd_parts[1]
    if script_arg.startswith("-"):
        reasons.append("python options such as -c or -m are not allowed")
    if Path(script_arg).suffix != ".py":
        reasons.append("artifact command script must be a .py file")
    try:
        script_path = resolve_run_path(run_dir, script_arg)
        script_rel = run_relative(run_dir, script_path)
        if not script_path.is_file():
            reasons.append(f"script does not exist: {script_arg}")
        if Path(script_rel).name in PROTECTED_NAMES or any(script_rel.startswith(prefix) for prefix in PROTECTED_PREFIXES):
            reasons.append(f"script path is protected: {script_arg}")
    except ValueError as exc:
        reasons.append(str(exc))

    for raw_arg in cmd_parts[2:]:
        if not isinstance(raw_arg, str) or not raw_arg:
            reasons.append("empty command argument is not allowed")
            continue
        if any(ch in raw_arg for ch in FORBIDDEN_ARTIFACT_COMMAND_CHARS):
            reasons.append(f"argument contains shell metacharacter: {raw_arg!r}")
        if raw_arg in FORBIDDEN_ARTIFACT_COMMAND_TOKENS:
            reasons.append(f"argument is shell operator token: {raw_arg!r}")
        if Path(raw_arg).is_absolute():
            reasons.append(f"absolute argument path is not allowed: {raw_arg}")
        if ".." in Path(raw_arg).parts:
            reasons.append(f"argument path escape is not allowed: {raw_arg}")
        if Path(raw_arg).name in PROTECTED_NAMES:
            reasons.append(f"argument references protected status artifact: {raw_arg}")

    if reasons:
        return False, [], reasons
    return True, [sys.executable, *cmd_parts[1:]], []


def run_artifact_command_test(run_dir: Path, test: dict[str, Any], passed: list, failed: list) -> bool:
    test_id = test.get("test_id", "<missing-test-id>")
    cmd = test.get("cmd")
    if not isinstance(cmd, str) or not cmd.strip():
        failed.append(f"artifact_test {test_id} missing command")
        return False

    expect_exit = test.get("expect_exit_code", 0)
    expect_contains = test.get("expect_stdout_contains", [])
    expect_lines_min = test.get("expect_stdout_lines_min")
    expect_file = test.get("expect_file_exists")
    local_failed = []

    try:
        cmd_parts = split_artifact_command(cmd)
    except ValueError as exc:
        failed.append(f"artifact_test {test_id} command parse error: {exc}")
        return False

    if not cmd_parts:
        failed.append(f"artifact_test {test_id} missing command")
        return False

    allowed, allowed_parts, allowlist_errors = validate_artifact_command_allowlist(run_dir, cmd, cmd_parts)
    if not allowed:
        failed.append(
            f"artifact_test {test_id} command rejected by allowlist: "
            + "; ".join(allowlist_errors)
        )
        return False

    try:
        result = subprocess.run(
            allowed_parts,
            cwd=run_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        failed.append(f"artifact_test {test_id} execution error: {exc}")
        return False

    if not isinstance(expect_exit, int):
        local_failed.append(f"expected exit code is not an integer: {expect_exit!r}")
    elif result.returncode != expect_exit:
        local_failed.append(f"exit code {result.returncode} != expected {expect_exit}")

    line_count = len([line for line in result.stdout.splitlines() if line.strip()])
    if expect_lines_min is not None:
        if not isinstance(expect_lines_min, int):
            local_failed.append(f"stdout minimum line count is not an integer: {expect_lines_min!r}")
        elif line_count < expect_lines_min:
            local_failed.append(f"output lines {line_count} < expected {expect_lines_min}")

    if not isinstance(expect_contains, list):
        local_failed.append("expect_stdout_contains must be a list")
    else:
        for substr in expect_contains:
            if not isinstance(substr, str):
                local_failed.append(f"expected stdout substring is not a string: {substr!r}")
            elif substr not in result.stdout:
                local_failed.append(f"missing expected substring {substr!r}")

    if expect_file:
        if not isinstance(expect_file, str):
            local_failed.append(f"expect_file_exists is not a string: {expect_file!r}")
        else:
            file_path = find_output(run_dir, expect_file)
            if not file_path or not file_path.is_file():
                local_failed.append(f"expected file {expect_file} missing")

    if local_failed:
        for item in local_failed:
            failed.append(f"artifact_test {test_id} {item}")
        return False

    passed.append(f"artifact_test {test_id} passed")
    return True
