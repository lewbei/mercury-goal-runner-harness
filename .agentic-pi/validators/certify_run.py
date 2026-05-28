import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parents[1] / "runtime"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from certifier_artifact_commands import (
    split_artifact_command,
    validate_artifact_command_allowlist,
    run_artifact_command_test,
)
from certifier_io import load_json, load_local_module, sha256_file, validate_with_schema, write_json
from certifier_paths import (
    PROTECTED_NAMES,
    PROTECTED_PREFIXES,
    find_output,
    non_empty_string_list,
    resolve_run_path,
    run_relative,
)
from verifier_provenance import create_verifier_artifact
from smell_scanner import safe_report_filename, scan_verifier_artifact
from strength_scorer import safe_strength_report_filename, score_verifier_artifact
from policy_engine import decide_run_policy, write_policy_decision
from certifier_gates import (
    apply_formal_verification_gate,
    apply_cryptographic_signature_gate,
    apply_artifact_location_gate,
    apply_audit_report_gate,
    apply_replay_gate,
    apply_drift_report_gate,
    apply_evidence_freeze_gate,
    evaluate_done_criteria,
    apply_memory_authority_gate,
    check_validator_certification,
)


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


def status_after_failures(status: str, provenance_mode: bool, failed: list) -> str:
    """Return the certifier-safe status after all blocking checks are known."""
    if failed:
        return "NOT_DONE" if provenance_mode else "DONE_FAIL"
    return status


def build_final_status_data(
    run_id: str,
    status: str,
    provenance_mode: bool,
    passed: list,
    failed: list,
) -> dict:
    total = len(passed) + len(failed)
    confidence = len(passed) / total if total > 0 else 0.0
    return {
        "schema_version": "final_status_v1",
        "run_id": run_id,
        "status": status,
        "status_source": "policy_decision.json" if provenance_mode and not failed else "certification.json",
        "final_status_authority": "certifier_only",
        "can_certify_done": False,
        "policy_decision_path": "policy_decision.json" if provenance_mode else "",
        "certification_path": "certification.json",
        "confidence_score": round(confidence, 4),
        "checks_passed": len(passed),
        "checks_failed": len(failed),
        "checks_total": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


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

        expected_action = expected_step.get("action")
        if not isinstance(expected_action, str) or not expected_action.strip():
            failed.append(f"merged plan step {expected_idx} action is missing")
            continue
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
        return {}

    report_dir = run_dir / "verifier_strength_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    reports_by_artifact_id = {}

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
            reports_by_artifact_id[artifact_id] = report
            passed.append(
                f"verifier strength score recorded: {artifact_id}={report['strength_level']}"
            )
        except Exception as exc:
            failed.append(f"verifier strength scoring failed for {artifact_id}: {exc}")

    return reports_by_artifact_id


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




def run_policy_engine(run_dir: Path, failed: list, passed: list) -> str:
    decision = decide_run_policy(run_dir, hard_failures=list(failed))
    decision_path = write_policy_decision(run_dir, decision)
    written_decision = load_json(decision_path)

    schema_failures = []
    validate_with_schema(
        written_decision,
        "policy_decision.schema.json",
        "policy_decision.json",
        schema_failures,
    )
    if schema_failures:
        failed.extend(schema_failures)
        return "NOT_DONE"

    passed.append("policy_decision.json validates")
    passed.append(f"policy engine status: {written_decision['status']}")

    if written_decision["status"] == "NOT_DONE" and not failed:
        reason = written_decision["reason"]
        if "No verifier artifacts found" in reason:
            failed.append(f"policy decision: verifier_artifacts missing: {reason}")
        else:
            failed.append(f"policy decision: {reason}")

    return written_decision["status"]



def main():
    if len(sys.argv) < 2:
        print("Usage: python certify_run.py <run_dir> [--skill-context <path>]")
        sys.exit(2)

    run_dir = Path(sys.argv[1])
    passed = []
    failed = []
    artifact_hashes = {}
    output_paths = {}

    # ── QRSPI skill context (auto-detect or explicit) ──────────────────
    active_skills = []
    if "--skill-context" in sys.argv:
        idx = sys.argv.index("--skill-context")
        if idx + 1 < len(sys.argv):
            ctx_path = Path(sys.argv[idx + 1])
            if ctx_path.is_file():
                ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
                active_skills = ctx.get("skill_names", [])
                print(f"certify_run: QRSPI skills active: {', '.join(active_skills)}")
    elif (run_dir / "skill_context.json").exists():
        ctx = json.loads((run_dir / "skill_context.json").read_text(encoding="utf-8"))
        active_skills = ctx.get("skill_names", [])
        if active_skills:
            print(f"certify_run: QRSPI skills auto-detected: {', '.join(active_skills)}")

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
                                # Check if file is a script (has __main__) or pure module
                                file_text = output_path.read_text(encoding="utf-8")
                                has_main = "if __name__" in file_text or "print(" in file_text

                                if has_main:
                                    # Skip CLI tools that need args (argparse or sys.argv)
                                    if "argparse" in file_text or "sys.argv" in file_text:
                                        passed.append(
                                            f"Python script {output} is a CLI tool (requires args)"
                                        )
                                    else:
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
                                else:
                                    # Pure module — just verify it imports cleanly
                                    try:
                                        import importlib.util
                                        spec = importlib.util.spec_from_file_location(
                                            output_path.stem, str(output_path))
                                        mod = importlib.util.module_from_spec(spec)
                                        spec.loader.exec_module(mod)
                                        passed.append(
                                            f"Python module {output} imports cleanly"
                                        )
                                    except Exception as import_exc:
                                        failed.append(
                                            f"Python module {output} import failed: {import_exc}"
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

    check_validator_certification(run_dir, failed, passed, provenance_mode)

    if provenance_mode:
        if verifier_contract:
            check_contract_target_artifacts(run_dir, verifier_contract, passed, failed)
            verifier_artifacts = load_verifier_artifacts(run_dir, passed, failed)
            smell_reports = record_verifier_smell_reports(run_dir, verifier_artifacts, passed, failed)
            record_verifier_strength_reports(run_dir, verifier_artifacts, smell_reports, passed, failed)
            status = run_policy_engine(run_dir, failed, passed)
        else:
            failed.append("verifier_contract.json required for provenance mode but did not load")
            status = "NOT_DONE"
    else:
        status = "DONE_PASS" if not failed else "DONE_FAIL"

    status = apply_artifact_location_gate(run_dir, provenance_mode, failed, passed, status)
    status = apply_replay_gate(run_dir, provenance_mode, failed, passed, status)
    status = apply_audit_report_gate(run_dir, provenance_mode, failed, passed, status)
    status = apply_drift_report_gate(run_dir, provenance_mode, failed, passed, status)
    status = apply_evidence_freeze_gate(run_dir, provenance_mode, failed, passed, status)
    status = apply_memory_authority_gate(run_dir, provenance_mode, failed, passed, status)
    status = apply_formal_verification_gate(run_dir, provenance_mode, failed, passed, status)
    status = apply_cryptographic_signature_gate(run_dir, provenance_mode, failed, passed, status)

    status = status_after_failures(status, provenance_mode, failed)
    certification = {
        "run_id": run_id,
        "status": status,
        "passed_checks": passed,
        "failed_checks": failed,
        "artifact_hashes": artifact_hashes,
        "audit_chain_valid": not failed,
        "generated_by": "agentic-pi-certifier-v0.3.6",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    cert_path = run_dir / "certification.json"
    final_status_path = run_dir / "final_status.json"
    write_json(cert_path, certification)
    write_json(
        final_status_path,
        build_final_status_data(run_id, status, provenance_mode, passed, failed),
    )

    validator_path = Path(__file__).resolve().parents[1] / "validators" / "validate_final_status.py"
    validator = load_local_module("validate_final_status", validator_path)
    validator.validate(final_status_path, run_dir, passed, failed)

    status = status_after_failures(status, provenance_mode, failed)
    certification["status"] = status
    certification["passed_checks"] = passed
    certification["failed_checks"] = failed
    certification["audit_chain_valid"] = not failed
    certification["timestamp"] = datetime.now(timezone.utc).isoformat()
    write_json(cert_path, certification)
    write_json(
        final_status_path,
        build_final_status_data(run_id, status, provenance_mode, passed, failed),
    )

    renderer_path = Path(__file__).resolve().parents[1] / "runtime" / "final_status_renderer.py"
    renderer = load_local_module("final_status_renderer", renderer_path)
    renderer.render_final_status_md(final_status_path, run_dir / "final_status.md", certification)

    print(status)
    print(f"Wrote {cert_path}")
    print(f"Wrote {final_status_path}")

    if failed or status == "NOT_DONE":
        for item in failed:
            print(f"FAILED_CHECK: {item}")
        sys.exit(1)


if __name__ == "__main__":
    main()
