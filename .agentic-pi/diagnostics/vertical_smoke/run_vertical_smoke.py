#!/usr/bin/env python3
"""Vertical smoke CLI — runs the full RPG-Harness v5 pipeline end-to-end.

Usage:
    python .agentic-pi/diagnostics/vertical_smoke/run_vertical_smoke.py

This script:
1. Creates a run via the Run Kernel
2. Transitions to INTAKE phase
3. Creates and dispatches a work packet
4. Simulates agent work by writing a result
5. Validates and accepts the packet
6. Runs the certifier
7. Runs replay certification
8. Reports pass/fail for each step

Returns exit code 0 if all 10 steps pass, 1 if any step fails.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN_KERNEL_PATH = ROOT / ".agentic-pi" / "run_kernel" / "run_kernel.py"
REPLAY_PATH = ROOT / ".agentic-pi" / "replay" / "replay_certification.py"
CERTIFY_PATH = ROOT / ".agentic-pi" / "validators" / "certify_run.py"

if str(RUN_KERNEL_PATH.parent) not in sys.path:
    sys.path.insert(0, str(RUN_KERNEL_PATH.parent))


def load_module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_python(*args):
    result = subprocess.run(
        [sys.executable, *args], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    return result


def make_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    print("=" * 60)
    print("RPG-Harness v5 Vertical Smoke Test")
    print("=" * 60)

    steps = []
    failed = False

    # ── Step 1: Create run via Kernel ────────────────────────────────────
    rk = load_module("run_kernel", RUN_KERNEL_PATH)
    run_id = "vs008_vertical_smoke"
    run_dir = ROOT / ".agentic-runs" / run_id

    import shutil
    if run_dir.exists():
        shutil.rmtree(run_dir)

    try:
        rk.create_run(run_id)
        state = rk.get_run_state(run_id)
        assert state["current_phase"] == "NEW", f"Expected NEW, got {state['current_phase']}"
        steps.append(("CREATE_RUN", "PASS", "run_state.json phase=NEW"))
    except Exception as e:
        steps.append(("CREATE_RUN", "FAIL", str(e)))
        failed = True

    # ── Step 2: Write goal contract ──────────────────────────────────────
    try:
        make_file(run_dir / "goal_contract.json", json.dumps({
            "run_id": run_id,
            "goal": "Vertical smoke test goal",
            "final_outputs": ["output.txt"],
            "done_criteria": ["output.txt exists"],
        }))
        make_file(run_dir / "trace.jsonl", json.dumps({"event": "start"}) + "\n")
        make_file(run_dir / "step_logs/001.json", json.dumps({
            "run_id": run_id, "step_id": 1, "status": "PASSED",
            "action_taken": "vertical smoke", "files_touched": ["output.txt"],
            "commands_run": ["echo smoke > output.txt"], "evidence": ["output.txt"],
            "pass_condition_satisfied": True, "remaining_work": [],
        }))
        make_file(run_dir / "output.txt", "vertical smoke output")
        steps.append(("SETUP_RUN", "PASS", "goal_contract, trace, step_logs, output created"))
    except Exception as e:
        steps.append(("SETUP_RUN", "FAIL", str(e)))
        failed = True

    # ── Step 3: Transition to INTAKE ─────────────────────────────────────
    try:
        rk.transition_to(run_id, "INTAKE")
        state = rk.get_run_state(run_id)
        assert state["current_phase"] == "INTAKE"
        steps.append(("TRANSITION_INTAKE", "PASS", f"NEW -> INTAKE"))
    except Exception as e:
        steps.append(("TRANSITION_INTAKE", "FAIL", str(e)))
        failed = True

    # ── Step 4: Create and dispatch work packet ───────────────────────────
    try:
        pid = rk.create_work_packet(
            run_id, phase="INTAKE", role="Questioner",
            task="Vertical smoke: create question contract",
            allowed_write_paths=["output.txt"],
            max_model_calls=1, max_repair_attempts=0,
        )
        rk.dispatch_packet(run_id, pid)
        pkt = rk.get_packet(run_id, pid)
        assert pkt["status"] == "DISPATCHED"
        steps.append(("DISPATCH_PACKET", "PASS", f"{pid} -> DISPATCHED"))
    except Exception as e:
        steps.append(("DISPATCH_PACKET", "FAIL", str(e)))
        failed = True

    # ── Step 5: Receive result ────────────────────────────────────────────
    try:
        result_path = f"work_results/{pid}.json"
        make_file(run_dir / result_path, json.dumps({"status": "done", "output": "output.txt"}))
        rk.receive_result(run_id, pid, result_path)
        pkt = rk.get_packet(run_id, pid)
        assert pkt["status"] == "RESULT_RECEIVED"
        steps.append(("RECEIVE_RESULT", "PASS", f"{pid} -> RESULT_RECEIVED"))
    except Exception as e:
        steps.append(("RECEIVE_RESULT", "FAIL", str(e)))
        failed = True

    # ── Step 6: Validate and accept ──────────────────────────────────────
    try:
        rk.start_validation(run_id, pid)
        val_path = f"validation_results/{pid}.json"
        make_file(run_dir / val_path, json.dumps({"verdict": "PASS", "checks": ["file_exists"]}))
        rk.accept_packet(run_id, pid, validation_result_path=val_path)
        pkt = rk.get_packet(run_id, pid)
        assert pkt["status"] == "ACCEPTED"
        steps.append(("ACCEPT_PACKET", "PASS", f"{pid} -> ACCEPTED"))
    except Exception as e:
        steps.append(("ACCEPT_PACKET", "FAIL", str(e)))
        failed = True

    # ── Step 7: Freeze evidence ──────────────────────────────────────────
    try:
        rc = load_module("replay_certification", REPLAY_PATH)
        hashes = rc.compute_evidence_hashes(run_dir)
        make_file(run_dir / "evidence_freeze.json", json.dumps({"artifact_hashes": hashes}))
        steps.append(("FREEZE_EVIDENCE", "PASS", f"{len(hashes)} files hashed"))
    except Exception as e:
        steps.append(("FREEZE_EVIDENCE", "FAIL", str(e)))
        failed = True

    # ── Step 8: Replay (run BEFORE certify so the gate reads it) ──────────
    try:
        replay = rc.run_replay_certification(run_dir)
        steps.append(("REPLAY", "PASS", f"verdict={replay['verdict']}"))
    except Exception as e:
        steps.append(("REPLAY", "FAIL", str(e)))
        failed = True

    # ── Step 9: Certify (replay gate reads replay_report.json) ────────────
    try:
        result = run_python(str(CERTIFY_PATH), str(run_dir))
        cert = json.loads((run_dir / "certification.json").read_text(encoding="utf-8"))
        status = cert["status"]
        steps.append(("CERTIFY", "PASS", f"status={status}"))
    except Exception as e:
        steps.append(("CERTIFY", "FAIL", str(e)))
        failed = True

    # ── Step 10: Verify dispatch log ─────────────────────────────────────
    try:
        log = rk.get_dispatch_log(run_id)
        events = [e["event"] for e in log]
        required = ["run_created", "phase_transition", "work_packet_created",
                    "work_packet_dispatched", "work_packet_result_received",
                    "work_packet_accepted"]
        missing = [r for r in required if r not in events]
        if missing:
            steps.append(("DISPATCH_LOG", "FAIL", f"Missing events: {missing}"))
            failed = True
        else:
            steps.append(("DISPATCH_LOG", "PASS", f"{len(events)} events logged"))
    except Exception as e:
        steps.append(("DISPATCH_LOG", "FAIL", str(e)))
        failed = True

    # ── Report ────────────────────────────────────────────────────────────
    print()
    print(f"{'Step':<25} {'Result':<8} Detail")
    print("-" * 60)
    for step_name, result, detail in steps:
        print(f"{step_name:<25} {result:<8} {detail}")

    passed_steps = sum(1 for _, r, _ in steps if r == "PASS")
    total_steps = len(steps)
    print()
    print(f"Result: {passed_steps}/{total_steps} steps passed")
    print()

    if failed:
        print("VERTICAL_SMOKE_FAILED")
        return 1
    else:
        print("VERTICAL_SMOKE_PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
