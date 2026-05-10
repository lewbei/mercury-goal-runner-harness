#!/usr/bin/env python3
"""Compile a raw goal into deterministic run-folder contracts.

This is a proof slice, not a general natural-language compiler. It supports
small explicit harness goals so the raw-goal path can be tested without letting
Pi or Mercury certify DONE.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / ".agentic-runs"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def require_run_id(run_id: str) -> str:
    if not RUN_ID_RE.match(run_id):
        raise ValueError(f"Invalid run_id: {run_id!r}")
    return run_id


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_trace(run_dir: Path, event: str, data: dict) -> None:
    trace_path = run_dir / "trace.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "data": data,
    }
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def goal_contract(run_id: str, raw_goal: str, complexity_level: str = "SIMPLE") -> dict:
    return {
        "run_id": run_id,
        "raw_user_prompt": raw_goal,
        "intent": "Create a README file from a raw user goal.",
        "cleaned_goal": "Create README.md explaining the harness.",
        "final_outputs": ["README.md"],
        "explicit_constraints": ["Keep it minimal.", "Write only inside the run folder."],
        "inferred_constraints": ["Use deterministic prepared-run execution."],
        "forbidden_actions": ["Do not modify protected files.", "Do not certify DONE in the compiler."],
        "ambiguities": [],
        "risk_level": "LOW",
        "complexity_level": complexity_level,
        "done_criteria": [
            "README.md exists.",
            "README.md contains the word 'harness'.",
        ],
        "failure_criteria": [
            "README.md missing.",
            "README.md does not mention 'harness'.",
        ],
        "ask_user_conditions": [],
        "max_steps": 5,
        "execution_prompt": "Create README.md for the harness. Do not touch protected files.",
    }


def verifier_contract(run_id: str, raw_goal: str) -> dict:
    return {
        "run_id": run_id,
        "target_goal": raw_goal,
        "target_artifacts": ["README.md"],
        "required_verifier_level": "P2",
        "allow_self_generated_only": False,
        "required_behaviors": [
            "README.md exists",
            "README.md contains the word harness",
        ],
        "forbidden_verifier_patterns": [
            "same worker self-test",
            "file existence only",
            "exit code only",
        ],
        "minimum_strength_level": "certifying",
        "certifying_authority_levels": ["P2", "P3"],
        "provisional_authority_levels": ["P0", "P1"],
    }


def verifier_artifact(run_id: str) -> dict:
    return {
        "artifact_id": "V.RAW_GOAL_P2",
        "run_id": run_id,
        "target_artifact": "README.md",
        "kind": "command_test",
        "source": "independent_verifier_agent",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_at_phase": "pre_solution",
        "author_agent": "deterministic-raw-goal-compiler",
        "author_model": "deterministic-local-fixture",
        "provenance_level": "P2",
        "depends_on_solution": False,
        "same_worker_as_solution": False,
        "executes_code": True,
        "assertion_count": 2,
        "mock_ratio_percent": 0,
        "smell_flags": [],
        "authority": "certifying",
        "solution_exists_at_creation": False,
    }


def compile_raw_goal(run_id: str, raw_goal: str, mode: str) -> Path:
    require_run_id(run_id)
    run_dir = RUN_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "step_logs").mkdir(exist_ok=True)
    (run_dir / "artifacts").mkdir(exist_ok=True)
    (run_dir / "backups").mkdir(exist_ok=True)

    write_json(
        run_dir / "run.json",
        {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "compile_raw_goal.py",
        },
    )
    complexity_level = "HARD" if mode == "planning_p2" else "SIMPLE"
    write_json(run_dir / "goal_contract.json", goal_contract(run_id, raw_goal, complexity_level))

    if mode in {"p2", "missing_verifier", "planning_p2"}:
        write_json(run_dir / "verifier_contract.json", verifier_contract(run_id, raw_goal))
    if mode in {"p2", "planning_p2"}:
        write_json(run_dir / "verifier_artifacts" / "V.RAW_GOAL_P2.json", verifier_artifact(run_id))

    append_trace(
        run_dir,
        "raw_goal_compiled",
        {
            "run_id": run_id,
            "mode": mode,
            "raw_goal": raw_goal,
        },
    )
    return run_dir


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Compile a deterministic raw goal into a run folder.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument(
        "--mode",
        choices=["legacy", "p2", "missing_verifier", "planning_p2"],
        default="legacy",
        help="raw-goal proof fixture mode",
    )
    args = parser.parse_args(argv)

    # Initialize run via the Run Kernel so run_state.json exists.
    # This is NOT best-effort: goal-run requires run_state.json, so
    # we fail early with a clear message if kernel init fails.
    try:
        import importlib.util
        from pathlib import Path as _Path
        _rk_path = _Path(__file__).resolve().parents[2] / ".agentic-pi" / "run_kernel" / "run_kernel.py"
        _spec = importlib.util.spec_from_file_location("run_kernel_compile", _rk_path)
        _rk = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_rk)
        _rk.create_run(args.run_id, goal_contract_path=args.goal)
    except FileExistsError:
        pass  # run already exists, continue
    except Exception as exc:
        print(f"ERROR: Run Kernel initialization failed: {exc}", file=sys.stderr)
        print("goal-run will not work without run_state.json. Use 'pi_cli.py goal-init' first.", file=sys.stderr)
        sys.exit(1)

    run_dir = compile_raw_goal(args.run_id, args.goal, args.mode)
    print(f"Compiled raw goal into {run_dir}")
    print(f"mode={args.mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
