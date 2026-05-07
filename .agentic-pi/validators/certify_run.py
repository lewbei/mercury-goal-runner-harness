import hashlib
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parents[1] / "runtime"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from validate_schema import validate as validate_schema_instance
from verifier_provenance import create_verifier_artifact
from smell_scanner import safe_report_filename, scan_verifier_artifact
from strength_scorer import safe_strength_report_filename, score_verifier_artifact


PROTECTED_NAMES = {
    "certification.json",
    "final_status.md",
    "trace.jsonl",
}

PROTECTED_PREFIXES = {
    "verifier_artifacts/",
    "verifier_smell_reports/",
    "verifier_strength_reports/",
}

PROVENANCE_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
PROVENANCE_STATUSES = {"NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE"}

STEP_REQUIRED = {
    "run_id": str,
    "step_id": int,
    "status": str,
    "action_taken": str,
    "files_touched": list,
    "commands_run": list,
    "evidence": list,
    "pass_condition_satisfied": bool,
    "remaining_work": list,
}

STEP_STATUSES = {"PASSED", "FAILED_REPAIRABLE", "BLOCKED", "NEED_USER"}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "schemas" / name


def validate_with_schema(instance, schema_name: str, label: str, failed: list):
    try:
        schema = load_json(schema_path(schema_name))
    except Exception as exc:
        failed.append(f"{label} schema load failed: {exc}")
        return
    for error in validate_schema_instance(instance, schema):
        failed.append(f"{label} schema validation failed: {error}")


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"absolute path is not allowed: {raw_path}")

    run_root = run_dir.resolve()
    resolved = (run_root / candidate).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"path escapes run folder: {raw_path}")
    return resolved


def run_relative(run_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(run_dir.resolve()).as_posix()


def output_candidates(run_dir: Path, output: str):
    yield resolve_run_path(run_dir, output)


def find_output(run_dir: Path, output: str):
    for candidate in output_candidates(run_dir, output):
        if candidate.exists():
            return candidate
    return None


def non_empty_string_list(value):
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def validate_step_shape(step, log_name, run_id, failed):
    for key, expected_type in STEP_REQUIRED.items():
        if key not in step:
            failed.append(f"{log_name} missing required field: {key}")
            continue
        if not isinstance(step[key], expected_type):
            failed.append(
                f"{log_name} field {key} has wrong type: expected {expected_type.__name__}"
            )

    if step.get("run_id") != run_id:
        failed.append(f"{log_name} run_id does not match run folder")

    if step.get("status") not in STEP_STATUSES:
        failed.append(f"{log_name} has invalid status: {step.get('status')!r}")

    if step.get("status") != "PASSED":
        failed.append(f"{log_name} status is not PASSED: {step.get('status')}")

    if step.get("pass_condition_satisfied") is not True:
        failed.append(f"{log_name} pass_condition_satisfied is not true")

    if not isinstance(step.get("action_taken"), str) or not step.get("action_taken", "").strip():
        failed.append(f"{log_name} action_taken is empty")

    if not non_empty_string_list(step.get("files_touched")):
        failed.append(f"{log_name} files_touched must contain at least one path")

    if not non_empty_string_list(step.get("commands_run")):
        failed.append(f"{log_name} commands_run must contain at least one command")

    if not non_empty_string_list(step.get("evidence")):
        failed.append(f"{log_name} evidence must contain at least one item")

    if step.get("remaining_work"):
        failed.append(f"{log_name} still reports remaining_work")


def validate_touched_files(run_dir, step, log_name, failed, touched_rel_paths):
    touched = step.get("files_touched", [])
    if not isinstance(touched, list):
        return

    for raw_path in touched:
        if not isinstance(raw_path, str):
            continue
        try:
            touched_path = resolve_run_path(run_dir, raw_path)
        except ValueError as exc:
            failed.append(f"{log_name} touched path invalid: {exc}")
            continue

        rel_path = run_relative(run_dir, touched_path)
        touched_rel_paths.add(rel_path)

        if Path(rel_path).name in PROTECTED_NAMES:
            failed.append(f"{log_name} reports Worker touched protected file: {rel_path}")
        if any(rel_path == prefix.rstrip("/") or rel_path.startswith(prefix) for prefix in PROTECTED_PREFIXES):
            failed.append(f"{log_name} reports Worker touched protected provenance path: {rel_path}")
        if not touched_path.exists():
            failed.append(f"{log_name} touched file missing: {rel_path}")


def load_merged_steps(run_dir: Path, failed):
    merged_path = run_dir / "merged_plan.json"
    if not merged_path.exists():
        return []
    try:
        merged = load_json(merged_path)
    except Exception as exc:
        failed.append(f"merged_plan.json parse failed: {exc}")
        return []
    steps = merged.get("steps", [])
    if not isinstance(steps, list):
        failed.append("merged_plan.json steps is not a list")
        return []
    return steps


def validate_against_merged_plan(run_dir, logs, step_by_id, merged_steps, failed):
    if not merged_steps:
        return

    if len(logs) != len(merged_steps):
        failed.append(
            f"step log count {len(logs)} does not match merged plan step count {len(merged_steps)}"
        )

    for expected_idx, expected_step in enumerate(merged_steps, start=1):
        actual = step_by_id.get(expected_idx)
        if actual is None:
            failed.append(f"missing step log for merged plan step {expected_idx}")
            continue

        expected_action = expected_step.get("action", "placeholder")
        if actual.get("action_taken") != expected_action:
            failed.append(
                f"step {expected_idx} action mismatch: expected {expected_action}, got {actual.get('action_taken')}"
            )

        if expected_action == "create_file":
            expected_raw_path = expected_step.get("path")
            if not isinstance(expected_raw_path, str) or not expected_raw_path.strip():
                failed.append(f"merged plan step {expected_idx} create_file path is empty")
                continue
            try:
                expected_path = resolve_run_path(run_dir, expected_raw_path)
            except ValueError as exc:
                failed.append(f"merged plan step {expected_idx} path invalid: {exc}")
                continue

            expected_rel = run_relative(run_dir, expected_path)
            actual_touched = set()
            for raw_path in actual.get("files_touched", []):
                try:
                    actual_touched.add(run_relative(run_dir, resolve_run_path(run_dir, raw_path)))
                except ValueError:
                    continue
            if expected_rel not in actual_touched:
                failed.append(
                    f"step {expected_idx} touched files do not include merged plan path: {expected_rel}"
                )


def run_python_output(path: Path, cwd: Path):
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=5,
    )


def split_artifact_command(cmd: str):
    return shlex.split(cmd, posix=(os.name != "nt"))


def run_artifact_command_test(run_dir: Path, test: dict, passed: list, failed: list):
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

    try:
        result = subprocess.run(
            cmd_parts,
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


def run_plan_graph_validation(run_dir: Path, passed: list, failed: list):
    graph_path = run_dir / "plan_graph.json"
    if not graph_path.exists():
        return

    validator_path = Path(__file__).with_name("validate_plan_graph.py")
    try:
        result = subprocess.run(
            [sys.executable, str(validator_path), str(run_dir)],
            cwd=Path(__file__).resolve().parents[2],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        failed.append(f"PlanGraph validation execution error: {exc}")
        return

    if result.returncode == 0:
        passed.append("PlanGraph validation passed")
        return

    failed.append("PlanGraph validation failed")
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("- "):
            failed.append(f"PlanGraph: {line[2:]}")


def load_verifier_contract(run_dir: Path, passed: list, failed: list):
    contract_path = run_dir / "verifier_contract.json"
    if not contract_path.exists():
        return None

    passed.append("verifier_contract.json exists")
    try:
        contract = load_json(contract_path)
    except Exception as exc:
        failed.append(f"verifier_contract.json parse failed: {exc}")
        return None

    passed.append("verifier_contract.json parses as JSON")
    validate_with_schema(contract, "verifier_contract.schema.json", "verifier_contract.json", failed)
    return contract


def artifact_test_assertion_count(test: dict) -> int:
    count = 0
    if "expect_exit_code" in test:
        count += 1
    if isinstance(test.get("expect_stdout_contains"), list):
        count += len(test["expect_stdout_contains"])
    if "expect_stdout_lines_min" in test:
        count += 1
    if "expect_file_exists" in test:
        count += 1
    return count


def safe_verifier_id(raw_id: str) -> str:
    token = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in raw_id)
    return token or "UNNAMED"


def log_artifact_test_verifier(run_dir: Path, test: dict, target_artifact: str, passed: list, failed: list):
    test_id = str(test.get("test_id") or "UNNAMED")
    artifact_id = f"V.ARTIFACT_TEST.{safe_verifier_id(test_id)}"
    try:
        create_verifier_artifact(
            run_dir=run_dir,
            artifact_id=artifact_id,
            target_artifact=target_artifact,
            kind="command_test",
            source="existing_repo_test",
            created_at_phase="external_preexisting",
            author_agent="goal-contract",
            author_model="user-or-benchmark-visible-contract",
            depends_on_solution=False,
            same_worker_as_solution=False,
            executes_code=True,
            assertion_count=artifact_test_assertion_count(test),
            mock_ratio_percent=0,
            solution_exists_at_creation=False,
        )
        passed.append(f"verifier artifact logged for artifact_test {test_id}")
    except Exception as exc:
        failed.append(f"artifact_test {test_id} verifier provenance log failed: {exc}")


def load_verifier_artifacts(run_dir: Path, passed: list, failed: list):
    verifier_dir = run_dir / "verifier_artifacts"
    if not verifier_dir.exists():
        return []

    artifacts = []
    for artifact_path in sorted(verifier_dir.glob("*.json")):
        try:
            artifact = load_json(artifact_path)
        except Exception as exc:
            failed.append(f"{artifact_path.name} verifier artifact parse failed: {exc}")
            continue
        validate_with_schema(
            artifact,
            "verifier_artifact.schema.json",
            f"verifier_artifacts/{artifact_path.name}",
            failed,
        )
        artifacts.append(artifact)

    if artifacts:
        passed.append(f"verifier_artifacts contain {len(artifacts)} artifact(s)")
    return artifacts


def record_verifier_smell_reports(run_dir: Path, artifacts: list, passed: list, failed: list):
    if not artifacts:
        return {}

    report_dir = run_dir / "verifier_smell_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    reports_by_artifact_id = {}

    for artifact in artifacts:
        artifact_id = str(artifact.get("artifact_id") or "UNKNOWN")
        try:
            report = scan_verifier_artifact(artifact)
            validate_with_schema(
                report,
                "verifier_smell_report.schema.json",
                f"verifier_smell_reports/{safe_report_filename(artifact_id)}",
                failed,
            )
            write_json(report_dir / safe_report_filename(artifact_id), report)
            reports_by_artifact_id[artifact_id] = report
            passed.append(f"verifier smell scan recorded: {artifact_id}")
        except Exception as exc:
            failed.append(f"verifier smell scan failed for {artifact_id}: {exc}")

    return reports_by_artifact_id


def record_verifier_strength_reports(
    run_dir: Path,
    artifacts: list,
    smell_reports_by_artifact_id: dict,
    passed: list,
    failed: list,
):
    if not artifacts:
        return

    report_dir = run_dir / "verifier_strength_reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    for artifact in artifacts:
        artifact_id = str(artifact.get("artifact_id") or "UNKNOWN")
        try:
            report = score_verifier_artifact(
                artifact,
                smell_reports_by_artifact_id.get(artifact_id),
            )
            validate_with_schema(
                report,
                "verifier_strength_report.schema.json",
                f"verifier_strength_reports/{safe_strength_report_filename(artifact_id)}",
                failed,
            )
            write_json(report_dir / safe_strength_report_filename(artifact_id), report)
            passed.append(
                f"verifier strength score recorded: {artifact_id}={report['strength_level']}"
            )
        except Exception as exc:
            failed.append(f"verifier strength scoring failed for {artifact_id}: {exc}")


def check_contract_target_artifacts(run_dir: Path, contract: dict, passed: list, failed: list):
    target_artifacts = contract.get("target_artifacts", [])
    for target in target_artifacts:
        try:
            target_path = find_output(run_dir, target)
        except ValueError as exc:
            failed.append(f"verifier target artifact path invalid: {exc}")
            continue
        if target_path and target_path.is_file():
            passed.append(f"verifier target artifact exists: {target}")
        else:
            failed.append(f"verifier target artifact missing: {target}")


def artifact_is_certifying_for_contract(artifact: dict, contract: dict) -> bool:
    level = artifact.get("provenance_level")
    target = artifact.get("target_artifact")
    required_level = contract.get("required_verifier_level", "P2")
    certifying_levels = set(contract.get("certifying_authority_levels", ["P2", "P3"]))

    if target not in set(contract.get("target_artifacts", [])):
        return False
    if artifact.get("authority") != "certifying":
        return False
    if artifact.get("same_worker_as_solution") is True:
        return False
    if artifact.get("executes_code") is not True:
        return False
    if not isinstance(artifact.get("assertion_count"), int) or artifact["assertion_count"] <= 0:
        return False
    if level not in certifying_levels:
        return False
    return PROVENANCE_ORDER.get(level, -1) >= PROVENANCE_ORDER.get(required_level, 99)


def decide_provenance_status(contract: dict, artifacts: list, failed: list, passed: list) -> str:
    if failed:
        return "NOT_DONE"
    if not artifacts:
        failed.append("verifier_artifacts missing for verifier_contract")
        return "NOT_DONE"

    if any(artifact_is_certifying_for_contract(artifact, contract) for artifact in artifacts):
        passed.append("certifying verifier provenance satisfied")
        return "CERTIFIED_DONE"

    levels = sorted({artifact.get("provenance_level") for artifact in artifacts})
    passed.append(f"verifier provenance is insufficient for CERTIFIED_DONE: {levels}")
    return "PROVISIONAL_DONE"


def evaluate_done_criteria(
    run_dir,
    done_criteria,
    final_outputs,
    output_paths,
    passed,
    failed,
    artifact_tests_present=False,
):
    first_output_path = next((path for path in output_paths.values() if path and path.is_file()), None)

    for crit in done_criteria:
        crit_lower = crit.lower()

        if "contains the word" in crit_lower:
            filename_part = crit.split("contains")[0].strip().rstrip(".")
            word = None
            if "'" in crit:
                parts = crit.split("'")
                if len(parts) >= 3:
                    word = parts[1]

            file_path = find_output(run_dir, filename_part)
            if not file_path or not file_path.is_file():
                failed.append(f"Done criterion failed: {crit} (file not found)")
                continue

            content = file_path.read_text(encoding="utf-8")
            if word and word in content:
                passed.append(f"Done criterion satisfied: {crit}")
            else:
                failed.append(f"Done criterion failed: {crit} (word '{word}' not found)")

        if "three bullet" in crit_lower:
            if not first_output_path:
                failed.append(f"Done criterion failed: {crit} (file not found)")
                continue
            content = first_output_path.read_text(encoding="utf-8")
            bullet_count = sum(1 for line in content.splitlines() if line.strip().startswith("- "))
            if bullet_count >= 3:
                passed.append(f"Done criterion satisfied: {crit}")
            else:
                failed.append(f"Done criterion failed: {crit} ({bullet_count} bullets found)")

        if (
            "run" in crit_lower
            or "execute" in crit_lower
            or "prints at least two lines" in crit_lower
        ):
            if artifact_tests_present:
                passed.append(f"Done criterion delegated to artifact_tests: {crit}")
                continue
            for output in final_outputs:
                if not output.endswith(".py"):
                    continue
                output_path = output_paths.get(output)
                if not output_path or not output_path.is_file():
                    failed.append(f"Done criterion failed: {crit} ({output} missing)")
                    continue
                try:
                    result = run_python_output(output_path, cwd=run_dir)
                except Exception as exc:
                    failed.append(f"Done criterion execution error for {output}: {exc}")
                    continue
                line_count = len([line for line in result.stdout.splitlines() if line.strip()])
                if result.returncode == 0 and line_count >= 2:
                    passed.append(f"Done criterion satisfied by running {output}")
                else:
                    failed.append(
                        f"Done criterion failed: {output} exit={result.returncode}, lines={line_count}"
                    )


def main():
    if len(sys.argv) != 2:
        print("Usage: python certify_run.py <run_dir>")
        sys.exit(2)

    run_dir = Path(sys.argv[1])
    passed = []
    failed = []
    artifact_hashes = {}
    output_paths = {}

    if not run_dir.exists():
        print("RUN_DIR_MISSING")
        sys.exit(1)

    run_id = run_dir.name
    goal_path = run_dir / "goal_contract.json"
    verifier_contract_path = run_dir / "verifier_contract.json"
    trace_path = run_dir / "trace.jsonl"
    step_dir = run_dir / "step_logs"
    provenance_mode = verifier_contract_path.exists()
    verifier_contract = load_verifier_contract(run_dir, passed, failed) if provenance_mode else None

    if goal_path.exists():
        passed.append("goal_contract.json exists")
        try:
            goal = load_json(goal_path)
            passed.append("goal_contract.json parses as JSON")
        except Exception as exc:
            goal = None
            failed.append(f"goal_contract.json parse failed: {exc}")
    else:
        goal = None
        failed.append("goal_contract.json missing")

    if trace_path.exists():
        passed.append("trace.jsonl exists")
        try:
            for line_no, line in enumerate(trace_path.read_text(encoding="utf-8").splitlines(), start=1):
                if line.strip():
                    json.loads(line)
            passed.append("trace.jsonl lines parse as JSON")
        except Exception as exc:
            failed.append(f"trace.jsonl invalid at line {line_no}: {exc}")
    else:
        failed.append("trace.jsonl missing")

    if step_dir.exists():
        logs = sorted(step_dir.glob("*.json"))
        if logs:
            passed.append("step_logs contain at least one step result")
        else:
            failed.append("step_logs exists but contains no .json files")
    else:
        logs = []
        failed.append("step_logs directory missing")

    step_by_id = {}
    for log in logs:
        try:
            step = load_json(log)
        except Exception as exc:
            failed.append(f"{log.name} parse failed: {exc}")
            continue

        validate_step_shape(step, log.name, run_id, failed)
        touched_rel_paths = set()
        validate_touched_files(run_dir, step, log.name, failed, touched_rel_paths)
        if touched_rel_paths and non_empty_string_list(step.get("evidence")):
            passed.append(f"{log.name} evidence maps to touched files")

        step_id = step.get("step_id")
        if isinstance(step_id, int):
            if step_id in step_by_id:
                failed.append(f"duplicate step_id in logs: {step_id}")
            step_by_id[step_id] = step

    merged_steps = load_merged_steps(run_dir, failed)
    validate_against_merged_plan(run_dir, logs, step_by_id, merged_steps, failed)
    run_plan_graph_validation(run_dir, passed, failed)

    if goal:
        final_outputs = goal.get("final_outputs", [])
        done_criteria = goal.get("done_criteria", [])
        # Process artifact tests if any
        artifact_tests = goal.get("artifact_tests", [])
        artifact_tests_present = bool(artifact_tests)
        if artifact_tests:
            passed.append("artifact_tests present")
            for test in artifact_tests:
                test_id = test.get("test_id")
                test_type = test.get("type")
                if test_type == "command":
                    test_passed = run_artifact_command_test(run_dir, test, passed, failed)
                    if test_passed and provenance_mode and final_outputs:
                        target_artifact = (
                            verifier_contract.get("target_artifacts", final_outputs)[0]
                            if verifier_contract
                            else final_outputs[0]
                        )
                        log_artifact_test_verifier(run_dir, test, target_artifact, passed, failed)
                else:
                    failed.append(f"artifact_test {test_id} unknown type {test_type}")

        if done_criteria:
            passed.append("done_criteria is non-empty")
        else:
            failed.append("done_criteria is empty")

        if final_outputs:
            passed.append("final_outputs is non-empty")
            for output in final_outputs:
                try:
                    output_path = find_output(run_dir, output)
                except ValueError as exc:
                    failed.append(f"final output path invalid: {exc}")
                    output_paths[output] = None
                    continue

                output_paths[output] = output_path
                if output_path:
                    passed.append(f"final output exists: {output}")
                    if output_path.is_file():
                        artifact_hashes[output] = sha256_file(output_path)
                        if output_path.suffix == ".py" and not artifact_tests_present:
                            try:
                                result = run_python_output(output_path, cwd=run_dir)
                                line_count = len(
                                    [line for line in result.stdout.splitlines() if line.strip()]
                                )
                                if result.returncode == 0 and line_count >= 2:
                                    passed.append(
                                        f"Python script {output} produced >=2 lines of output"
                                    )
                                else:
                                    failed.append(
                                        f"Python script {output} exit={result.returncode}, lines={line_count}"
                                    )
                            except Exception as exc:
                                failed.append(f"Running Python script {output} failed: {exc}")
                else:
                    failed.append(f"final output missing: {output}")
        else:
            final_outputs = []
            failed.append("final_outputs is empty")
        evaluate_done_criteria(
            run_dir,
            done_criteria,
            final_outputs,
            output_paths,
            passed,
            failed,
            artifact_tests_present=artifact_tests_present,
        )

    if provenance_mode:
        if verifier_contract:
            check_contract_target_artifacts(run_dir, verifier_contract, passed, failed)
            verifier_artifacts = load_verifier_artifacts(run_dir, passed, failed)
            smell_reports = record_verifier_smell_reports(run_dir, verifier_artifacts, passed, failed)
            record_verifier_strength_reports(run_dir, verifier_artifacts, smell_reports, passed, failed)
            status = decide_provenance_status(verifier_contract, verifier_artifacts, failed, passed)
        else:
            failed.append("verifier_contract.json required for provenance mode but did not load")
            status = "NOT_DONE"
    else:
        status = "DONE_PASS" if not failed else "DONE_FAIL"

    certification = {
        "run_id": run_id,
        "status": status,
        "passed_checks": passed,
        "failed_checks": failed,
        "artifact_hashes": artifact_hashes,
        "audit_chain_valid": not failed,
        "generated_by": "agentic-pi-certifier-v0.3.2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    cert_path = run_dir / "certification.json"
    final_status_path = run_dir / "final_status.md"

    write_json(cert_path, certification)

    report = []
    report.append(f"# Final Status: {status}")
    report.append("")
    report.append(f"Run ID: `{run_id}`")
    report.append("")
    report.append("## Passed checks")
    for item in passed:
        report.append(f"- {item}")
    report.append("")
    report.append("## Failed checks")
    if failed:
        for item in failed:
            report.append(f"- {item}")
    else:
        report.append("- none")
    report.append("")
    report.append("## Artifact hashes")
    if artifact_hashes:
        for key, value in artifact_hashes.items():
            report.append(f"- `{key}`: `{value}`")
    else:
        report.append("- none")

    final_status_path.write_text("\n".join(report), encoding="utf-8")

    print(status)
    print(f"Wrote {cert_path}")
    print(f"Wrote {final_status_path}")

    if failed or status == "NOT_DONE":
        for item in failed:
            print(f"FAILED_CHECK: {item}")
        sys.exit(1)


if __name__ == "__main__":
    main()
