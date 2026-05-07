#!/usr/bin/env python3
"""Stable command surface for the Verifier-Provenance Goal Runner Harness.

This CLI is intentionally thin. It dispatches to deterministic harness tools and
does not certify DONE itself.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / ".agentic-runs"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def require_run_id(run_id: str) -> str:
    if not RUN_ID_RE.match(run_id):
        raise SystemExit(f"Invalid run_id: {run_id!r}")
    return run_id


def run_dir_for(run_id: str) -> Path:
    return RUN_ROOT / require_run_id(run_id)


def run_cmd(args: list[str]) -> int:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    print(result.stdout, end="")
    return result.returncode


def require_existing_run(run_id: str) -> Path:
    run_dir = run_dir_for(run_id)
    if not run_dir.is_dir():
        raise SystemExit(f"Run folder missing: {run_dir}")
    return run_dir


def goal_init(args) -> int:
    require_run_id(args.run_id)
    return run_cmd([".agentic-pi/runtime/init_run.py", "--run-id", args.run_id])


def goal_compile(args) -> int:
    require_run_id(args.run_id)
    return run_cmd(
        [
            ".agentic-pi/runtime/compile_raw_goal.py",
            "--run-id",
            args.run_id,
            "--goal",
            args.goal,
            "--mode",
            args.mode,
        ]
    )


def goal_run(args) -> int:
    require_existing_run(args.run_id)
    command = args.command or f"Run prepared goal {args.run_id}"
    cmd = [
        ".agentic-pi/runtime/run_goal.py",
        command,
        "--run-id",
        args.run_id,
    ]
    if args.skip_memory_update:
        cmd.append("--skip-memory-update")
    return run_cmd(cmd)


def goal_plan_proof(args) -> int:
    require_existing_run(args.run_id)
    return run_cmd([".agentic-pi/runtime/planning_proof_runner.py", args.run_id])


def goal_strategy_proof(args) -> int:
    require_existing_run(args.run_id)
    return run_cmd([".agentic-pi/runtime/strategy_proof_runner.py", args.run_id])


def goal_certify(args) -> int:
    run_dir = require_existing_run(args.run_id)
    return run_cmd([".agentic-pi/validators/certify_run.py", str(run_dir)])


def goal_status(args) -> int:
    run_dir = require_existing_run(args.run_id)
    paths = [
        run_dir / "final_status.md",
        run_dir / "certification.json",
    ]
    policy_path = run_dir / "policy_decision.json"
    provenance_mode = (run_dir / "verifier_contract.json").is_file()
    if provenance_mode or policy_path.is_file():
        paths.append(policy_path)
    missing = False
    for path in paths:
        print(f"## {path.relative_to(ROOT).as_posix()}")
        if path.is_file():
            print(path.read_text(encoding="utf-8-sig").rstrip())
        else:
            print("MISSING")
            missing = True
        print()
    if not provenance_mode and not policy_path.is_file():
        print(f"## {policy_path.relative_to(ROOT).as_posix()}")
        print("SKIPPED_LEGACY")
        print()
    return 1 if missing and args.fail_on_missing else 0


def goal_replay(args) -> int:
    run_dir = require_existing_run(args.run_id)
    return run_cmd([".agentic-pi/runtime/replay_run.py", str(run_dir)])


def goal_audit(args) -> int:
    run_dir = require_existing_run(args.run_id)
    return run_cmd([".agentic-pi/runtime/audit_run.py", str(run_dir)])


def goal_rollback(args) -> int:
    run_dir = require_existing_run(args.run_id)
    cmd = [
        ".agentic-pi/runtime/rollback_run.py",
        str(run_dir),
        "--file",
        args.file,
    ]
    if args.apply:
        cmd.append("--apply")
    return run_cmd(cmd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verifier-Provenance Goal Runner CLI. Final status comes only from "
            "certify_run.py / policy_engine.py."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_init = subparsers.add_parser("goal-init", help="Initialize a run folder")
    p_init.add_argument("run_id")
    p_init.set_defaults(func=goal_init)

    p_compile = subparsers.add_parser("goal-compile", help="Compile a deterministic raw goal")
    p_compile.add_argument("run_id")
    p_compile.add_argument("--goal", required=True)
    p_compile.add_argument(
        "--mode",
        choices=["legacy", "p2", "missing_verifier", "planning_p2"],
        default="legacy",
    )
    p_compile.set_defaults(func=goal_compile)

    p_run = subparsers.add_parser("goal-run", help="Run the prepared-run harness path")
    p_run.add_argument("run_id")
    p_run.add_argument("--command", help="Human goal text for run_goal.py")
    p_run.add_argument("--skip-memory-update", action="store_true")
    p_run.set_defaults(func=goal_run)

    p_plan_proof = subparsers.add_parser(
        "goal-plan-proof",
        help="Run the deterministic planning proof path",
    )
    p_plan_proof.add_argument("run_id")
    p_plan_proof.set_defaults(func=goal_plan_proof)

    p_strategy_proof = subparsers.add_parser(
        "goal-strategy-proof",
        help="Run the deterministic strategy proof path",
    )
    p_strategy_proof.add_argument("run_id")
    p_strategy_proof.set_defaults(func=goal_strategy_proof)

    p_certify = subparsers.add_parser("goal-certify", help="Run certify_run.py")
    p_certify.add_argument("run_id")
    p_certify.set_defaults(func=goal_certify)

    p_status = subparsers.add_parser("goal-status", help="Read status artifacts")
    p_status.add_argument("run_id")
    p_status.add_argument("--fail-on-missing", action="store_true")
    p_status.set_defaults(func=goal_status)

    p_replay = subparsers.add_parser("goal-replay", help="Replay run-folder evidence")
    p_replay.add_argument("run_id")
    p_replay.set_defaults(func=goal_replay)

    p_audit = subparsers.add_parser("goal-audit", help="Audit run-folder evidence")
    p_audit.add_argument("run_id")
    p_audit.set_defaults(func=goal_audit)

    p_rollback = subparsers.add_parser("goal-rollback", help="Dry-run or apply run-folder rollback")
    p_rollback.add_argument("run_id")
    p_rollback.add_argument("--file", required=True, help="Run-relative file to roll back")
    p_rollback.add_argument("--apply", action="store_true", help="Apply rollback; default is dry-run")
    p_rollback.set_defaults(func=goal_rollback)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
