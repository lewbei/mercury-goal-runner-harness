#!/usr/bin/env python3
"""Vertical smoke test for VS.001: Run kernel controls actual flow.

This test proves that the Run Kernel is the authority for run state.
It tests the integration layer directly: the same code paths that
init_run.py and run_goal.py use.

The test:
1. Creates a run via run_kernel.create_run() — same call init_run.py uses
2. Verifies run_state.json is the authority
3. Transitions state via run_kernel.transition_to() — same call run_goal.py uses
4. Verifies dispatch_log.jsonl records the events
5. Verifies the kernel state is queryable after simulated pipeline steps

No subprocess calls — the integration is tested at the Python API level,
which is the same code both init_run.py and run_goal.py import.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_KERNEL_PATH = ROOT / ".agentic-pi" / "run_kernel" / "run_kernel.py"

if str(RUN_KERNEL_PATH.parent) not in sys.path:
    sys.path.insert(0, str(RUN_KERNEL_PATH.parent))


def load_module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestVerticalSmokeKernelControlsFlow(unittest.TestCase):
    """VS.001: init_run -> kernel -> run_goal -> kernel state verified."""

    def setUp(self):
        self.rk = load_module("run_kernel", RUN_KERNEL_PATH)

        # Redirect runs to temp directory
        self.tmp = Path(tempfile.mkdtemp())
        self.old_runs_dir = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp

        self.run_id = "vs001_smoke"

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs_dir
        import shutil
        shutil.rmtree(self.tmp)

    @property
    def run_dir(self):
        return self.tmp / self.run_id

    # ── Test 1: Kernel creates run with correct initial state ─────────────

    def test_kernel_creates_run(self):
        """run_kernel.create_run() creates run_state.json with phase NEW."""
        self.rk.create_run(self.run_id)

        self.assertTrue((self.run_dir / "run_state.json").exists(),
                        "run_state.json must exist")
        self.assertTrue((self.run_dir / "phase_queue.json").exists(),
                        "phase_queue.json must exist")
        self.assertTrue((self.run_dir / "run_manifest.json").exists(),
                        "run_manifest.json must exist")
        self.assertTrue((self.run_dir / "dispatch_log.jsonl").exists(),
                        "dispatch_log.jsonl must exist")

        state = self.rk.get_run_state(self.run_id)
        self.assertEqual(state["current_phase"], "NEW",
                         "Initial phase must be NEW")
        self.assertEqual(state["overall_status"], "IN_PROGRESS")
        self.assertEqual(state["schema_version"], "run_state_v1")

    # ── Test 2: Kernel creates subdirectories ────────────────────────────

    def test_kernel_creates_subdirs(self):
        """create_run creates work_packets, work_results, validation_results."""
        self.rk.create_run(self.run_id)

        self.assertTrue((self.run_dir / "work_packets").is_dir())
        self.assertTrue((self.run_dir / "work_results").is_dir())
        self.assertTrue((self.run_dir / "validation_results").is_dir())

    # ── Test 3: Kernel transitions state ──────────────────────────────────

    def test_kernel_transitions_state(self):
        """transition_to moves from NEW to INTAKE."""
        self.rk.create_run(self.run_id)
        self.rk.transition_to(self.run_id, "INTAKE")

        state = self.rk.get_run_state(self.run_id)
        self.assertEqual(state["current_phase"], "INTAKE")
        self.assertEqual(state["previous_phase"], "NEW")

    # ── Test 4: Phase history records transitions ─────────────────────────

    def test_phase_history_recorded(self):
        """Each transition is recorded in phase_history."""
        self.rk.create_run(self.run_id)
        self.rk.transition_to(self.run_id, "INTAKE")
        self.rk.transition_to(self.run_id, "QUESTIONING")

        state = self.rk.get_run_state(self.run_id)
        history = [h["phase"] for h in state["phase_history"]]
        self.assertEqual(history, ["NEW", "INTAKE", "QUESTIONING"])

    # ── Test 5: Dispatch log records events ───────────────────────────────

    def test_dispatch_log_records_events(self):
        """dispatch_log.jsonl contains run_created and phase_transition events."""
        self.rk.create_run(self.run_id)
        self.rk.transition_to(self.run_id, "INTAKE")

        log = self.rk.get_dispatch_log(self.run_id)
        events = [e["event"] for e in log]

        self.assertIn("run_created", events)
        self.assertIn("phase_transition", events)

        trans = [e for e in log if e["event"] == "phase_transition"]
        self.assertEqual(trans[0]["from_phase"], "NEW")
        self.assertEqual(trans[0]["to_phase"], "INTAKE")

    # ── Test 6: Kernel state is the authority ─────────────────────────────

    def test_kernel_state_is_authority(self):
        """run_state.json is the authority — not state.json or run.json."""
        self.rk.create_run(self.run_id)

        # The old state.json and run.json should not be the authority
        run_state = self.rk.get_run_state(self.run_id)
        self.assertIn("current_phase", run_state,
                      "run_state.json must have current_phase")
        self.assertEqual(run_state["current_phase"], "NEW")

        # Verify the kernel version is recorded
        self.assertEqual(run_state["kernel_version"],
                         "rpg_harness_v5_kernel_v1")

    # ── Test 7: Phase queue exists and has QRSPI phases ───────────────────

    def test_phase_queue_has_qrspi_phases(self):
        """phase_queue.json contains INTAKE through MEMORY_CONSOLIDATING."""
        self.rk.create_run(self.run_id)
        pq = self.rk.get_phase_queue(self.run_id)

        phases = [p["phase"] for p in pq["phases"]]
        self.assertIn("INTAKE", phases)
        self.assertIn("IMPLEMENTING", phases)
        self.assertIn("CERTIFYING", phases)
        self.assertIn("MEMORY_CONSOLIDATING", phases)
        self.assertEqual(pq["run_id"], self.run_id)

    # ── Test 8: Transition validation blocks illegal moves ────────────────

    def test_illegal_transition_blocked(self):
        """transition_to raises RuntimeError for illegal transitions."""
        self.rk.create_run(self.run_id)

        with self.assertRaises(RuntimeError):
            self.rk.transition_to(self.run_id, "CERTIFYING")

        # State should remain unchanged
        state = self.rk.get_run_state(self.run_id)
        self.assertEqual(state["current_phase"], "NEW")

    # ── Test 9: Simulated run_goal integration ────────────────────────────

    def test_simulated_goal_pipeline(self):
        """Simulates what run_goal.py does: create run, transition, verify."""
        # Step 1: Create run (replaces old init_run.py behavior)
        self.rk.create_run(self.run_id)

        # Step 2: Write goal contract (simulates goal setup)
        contract = {
            "run_id": self.run_id,
            "goal_id": "vs001_simulated",
            "goal_type": "generic",
            "description": "Simulated goal for vertical slice test",
        }
        (self.run_dir / "goal_contract.json").write_text(
            json.dumps(contract), encoding="utf-8"
        )

        # Step 3: Transition to INTAKE (what run_goal.py does first)
        self.rk.transition_to(self.run_id, "INTAKE")

        # Verify kernel state
        state = self.rk.get_run_state(self.run_id)
        self.assertEqual(state["current_phase"], "INTAKE")
        self.assertEqual(state["previous_phase"], "NEW")

        # Verify dispatch log
        log = self.rk.get_dispatch_log(self.run_id)
        self.assertEqual(len(log), 2)  # run_created + phase_transition
        self.assertEqual(log[0]["event"], "run_created")
        self.assertEqual(log[1]["event"], "phase_transition")


if __name__ == "__main__":
    unittest.main()
