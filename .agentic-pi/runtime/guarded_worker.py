#!/usr/bin/env python3
"""Guarded Worker – executes steps from merged_plan.json and logs evidence.

Usage:
    python .agentic-pi/runtime/guarded_worker.py --run-id <run_id>
"""
import argparse
import json
import os
import subprocess
import hashlib
from datetime import datetime, timezone
from pathlib import Path


PROTECTED_WORKER_FILENAMES = {
    "certification.json",
    "final_status.json",
    "final_status.md",
    "policy_decision.json",
    "replay_report.json",
    "evidence_freeze.json",
    "evidence_index.json",
    "evidence_hash_manifest.json",
    "run_state.json",
    "phase_queue.json",
    "trace.jsonl",
    "goal_contract.json",
    "expected_artifacts.json",
    "selected_plan.json",
    "merged_plan.json",
    "plan_graph.json",
    "verifier_contract.json",
    "validator_certification.json",
}

PROTECTED_WORKER_PREFIXES = {
    "verifier_artifacts/",
    "verifier_smell_reports/",
    "verifier_strength_reports/",
}


def enforce_worker_write_scope(relative_path: str) -> None:
    """Reject merged-plan writes to authority/provenance artifacts."""
    normalized = relative_path.replace("\\", "/").strip("/")
    filename = normalized.split("/")[-1]
    if filename in PROTECTED_WORKER_FILENAMES:
        raise RuntimeError(f"guarded_worker refuses authority/provenance write: {relative_path}")
    for prefix in PROTECTED_WORKER_PREFIXES:
        if normalized == prefix.rstrip("/") or normalized.startswith(prefix):
            raise RuntimeError(f"guarded_worker refuses protected directory write: {relative_path}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_run_path(run_dir: Path, raw_path: str) -> Path:
    target_path = Path(raw_path)
    if target_path.is_absolute():
        raise ValueError(f"Refusing absolute path outside run folder: {raw_path}")

    run_root = run_dir.resolve()
    resolved = (run_root / target_path).resolve()
    if resolved != run_root and run_root not in resolved.parents:
        raise ValueError(f"Refusing path escape outside run folder: {raw_path}")
    return resolved


def run_relative(run_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(run_dir.resolve()).as_posix()


def log_trace(run_dir: Path, agent: str, event: str, status: str = "OK", data: dict = None):
    # Use the trace_logger tool to append a JSON line
    cmd = [
        "python",
        ".agentic-pi/runtime/trace_logger.py",
        str(run_dir),
        "--agent", agent,
        "--event", event,
        "--status", status,
        "--data", json.dumps(data or {}),
    ]
    subprocess.run(cmd, check=True)

def main():
    parser = argparse.ArgumentParser(description="Execute merged plan for a run")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument("--skill-context", default=None, help="Path to skill_context.json (QRSPI skills)")
    args = parser.parse_args()
    run_dir = Path(".agentic-runs") / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # ── Read QRSPI skill context if provided ───────────────────────────
    active_skills = []
    if args.skill_context:
        ctx_path = Path(args.skill_context)
        if ctx_path.is_file():
            ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
            active_skills = ctx.get("skill_names", [])
            print(f"  QRSPI skills active: {', '.join(active_skills)}")

    # ── Apply path-grounding skill: validate against expected_artifacts ─
    expected_artifacts = None
    ea_path = run_dir / "expected_artifacts.json"
    if ea_path.is_file() and "path-grounding" in active_skills:
        expected_artifacts = json.loads(ea_path.read_text(encoding="utf-8"))
        print(f"  path-grounding: loaded {len(expected_artifacts.get('artifacts', []))} expected artifacts")

    # ── Apply artifact-contract skill: enforce allowed/forbidden writers ─
    writer_role = "Engineer"
    if "artifact-contract" in active_skills:
        print(f"  artifact-contract: enforcing write scope for role={writer_role}")

    merged_plan_path = run_dir / "merged_plan.json"
    if not merged_plan_path.is_file():
        raise FileNotFoundError(f"merged_plan.json not found at {merged_plan_path}")
    with merged_plan_path.open() as f:
        plan = json.load(f)
    steps = plan.get("steps", [])
    if not steps:
        raise RuntimeError("No steps in merged_plan.json")

    step_logs_dir = run_dir / "step_logs"
    step_logs_dir.mkdir(parents=True, exist_ok=True)
    for idx, step in enumerate(steps, start=1):
        action = step.get("action")
        if action != "create_file":
            raise RuntimeError(
                f"Unsupported merged_plan action at step {idx}: {action!r}. "
                "Guarded Worker strict mode only supports action='create_file' "
                "and will not create generated substitute artifacts."
            )

        # Handle create_file action
        if action == "create_file":
            raw_target_path = step.get("path")
            if not isinstance(raw_target_path, str) or not raw_target_path.strip():
                raise RuntimeError(f"merged_plan step {idx} create_file action requires a non-empty path")
            full_path = resolve_run_path(run_dir, raw_target_path)

            # ── path-grounding: validate against expected_artifacts ────
            relative_path = run_relative(run_dir, full_path)
            enforce_worker_write_scope(relative_path)
            if expected_artifacts:
                expected_paths = [a.get("expected_path", "") for a in expected_artifacts.get("artifacts", [])]
                if expected_paths and relative_path not in expected_paths:
                    raise RuntimeError(
                        f"path-grounding failed: {relative_path} not in expected_artifacts ({expected_paths})"
                    )
                print(f"  path-grounding OK: {relative_path} matches expected artifact")

            full_path.parent.mkdir(parents=True, exist_ok=True)
            content = step.get("content", "")
            full_path.write_text(content, encoding="utf-8")
            files_touched = [relative_path]
            evidence = [f"Created file {files_touched[0]}"]
            action_taken = "create_file"
            command_desc = f"write {files_touched[0]}"

        step_result = {
            "run_id": args.run_id,
            "step_id": idx,
            "status": "PASSED",
            "action_taken": action_taken,
            "files_touched": files_touched,
            "commands_run": [command_desc],
            "evidence": evidence,
            "pass_condition_satisfied": True,
            "remaining_work": []
        }
        # Write step result JSON
        step_file = step_logs_dir / f"{idx}.json"
        step_file.write_text(json.dumps(step_result, indent=2, ensure_ascii=False), encoding="utf-8")

        # Log trace event
        log_trace(run_dir, agent="guarded_worker", event="step_executed", data={"step_id": idx, "status": "PASSED"})

    # All steps done – log final trace
    log_trace(run_dir, agent="guarded_worker", event="run_completed")
    print(f"Guarded Worker completed {len(steps)} steps for run {args.run_id}")

if __name__ == "__main__":
    main()
