#!/usr/bin/env python3
"""Tests for the horizontal supervisor loop.

Tests:
- get_ready_packets returns all PENDING packets with met dependencies
- supervise_phase dispatches multiple packets, waits for results
- supervise_run walks the phase queue vertically
- dispatch_all dispatches every packet it receives
- determine_phase_outcome computes correct pass/fail
"""

import json
import unittest
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_supervisor():
    import importlib.util
    path = ROOT / ".agentic-pi" / "runtime" / "supervisor_loop.py"
    spec = importlib.util.spec_from_file_location("supervisor_loop", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_kernel():
    import importlib.util
    path = ROOT / ".agentic-pi" / "run_kernel" / "run_kernel.py"
    spec = importlib.util.spec_from_file_location("run_kernel", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SupervisorLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sl = load_supervisor()
        cls.rk = load_kernel()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.old_runs = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp
        # Patch the supervisor's kernel path to use our temp
        self.sl._load_kernel = lambda: self.rk

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs
        import shutil
        shutil.rmtree(self.tmp)

    def _create_packets_in_phase(self, run_id: str, phase: str, count: int) -> list[str]:
        """Create N work packets in a phase and return their IDs."""
        pids = []
        for i in range(count):
            pid = self.rk.create_work_packet(
                run_id, phase=phase, role="Questioner",
                task=f"Packet {i+1} in {phase}",
            )
            pids.append(pid)
        return pids

    def _simulate_packet_lifecycle(self, run_id: str, pid: str,
                                    accept: bool = True):
        """Simulate packet: dispatch → receive → validate → accept/reject."""
        self.rk.dispatch_packet(run_id, pid)
        self.rk.receive_result(run_id, pid, "result.json")
        self.rk.start_validation(run_id, pid)
        if accept:
            self.rk.accept_packet(run_id, pid)
        else:
            self.rk.reject_packet(run_id, pid, error="Test rejection")

    # ══════════════════════════════════════════════════════════════════════
    #  get_ready_packets
    # ══════════════════════════════════════════════════════════════════════

    def test_get_ready_packets_returns_all_pending_in_phase(self):
        run_id = "supervisor_ready"
        self.rk.create_run(run_id)
        pids = self._create_packets_in_phase(run_id, "INTAKE", 3)

        ready = self.sl.get_ready_packets(run_id, "INTAKE")
        self.assertEqual(len(ready), 3)
        returned_pids = {p["work_packet_id"] for p in ready}
        self.assertEqual(returned_pids, set(pids))

    def test_get_ready_packets_excludes_dispatched(self):
        run_id = "supervisor_exclude_dispatched"
        self.rk.create_run(run_id)
        pids = self._create_packets_in_phase(run_id, "INTAKE", 2)
        # Dispatch one
        self.rk.dispatch_packet(run_id, pids[0])

        ready = self.sl.get_ready_packets(run_id, "INTAKE")
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]["work_packet_id"], pids[1])

    def test_get_ready_packets_empty_phase(self):
        run_id = "supervisor_empty"
        self.rk.create_run(run_id)
        ready = self.sl.get_ready_packets(run_id, "INTAKE")
        self.assertEqual(ready, [])

    # ══════════════════════════════════════════════════════════════════════
    #  dispatch_all
    # ══════════════════════════════════════════════════════════════════════

    def test_dispatch_all_dispatches_multiple_packets(self):
        run_id = "supervisor_dispatch_all"
        self.rk.create_run(run_id)
        pids = self._create_packets_in_phase(run_id, "INTAKE", 3)
        packets = [self.rk.get_packet(run_id, pid) for pid in pids]

        results = self.sl.dispatch_all(run_id, packets)

        for pid in pids:
            self.assertIn(pid, results)
            self.assertEqual(results[pid], "DISPATCHED")
            pkt = self.rk.get_packet(run_id, pid)
            self.assertEqual(pkt["status"], "DISPATCHED")

    # ══════════════════════════════════════════════════════════════════════
    #  determine_phase_outcome
    # ══════════════════════════════════════════════════════════════════════

    def test_outcome_all_accepted_passes(self):
        outcome = self.sl.determine_phase_outcome({
            "WP.A.001": "ACCEPTED",
            "WP.A.002": "ACCEPTED",
            "WP.A.003": "ACCEPTED",
        })
        self.assertTrue(outcome["passed"])
        self.assertEqual(outcome["accepted"], 3)
        self.assertEqual(outcome["summary"], "3/3 accepted")

    def test_outcome_any_rejected_fails(self):
        outcome = self.sl.determine_phase_outcome({
            "WP.A.001": "ACCEPTED",
            "WP.A.002": "REJECTED",
        })
        self.assertFalse(outcome["passed"])
        self.assertEqual(outcome["accepted"], 1)
        self.assertEqual(outcome["rejected"], 1)

    def test_outcome_accepted_plus_cancelled_passes(self):
        outcome = self.sl.determine_phase_outcome({
            "WP.A.001": "ACCEPTED",
            "WP.A.002": "CANCELLED",
        })
        self.assertTrue(outcome["passed"])

    def test_outcome_blocked_fails(self):
        outcome = self.sl.determine_phase_outcome({
            "WP.A.001": "BLOCKED",
        })
        self.assertFalse(outcome["passed"])

    # ══════════════════════════════════════════════════════════════════════
    #  supervise_phase — horizontal dispatch + poll
    # ══════════════════════════════════════════════════════════════════════

    def test_supervise_phase_with_all_accepted(self):
        """Create 3 packets, dispatch them, simulate acceptance, check pass."""
        run_id = "supervisor_phase_accept"
        self.rk.create_run(run_id)
        pids = self._create_packets_in_phase(run_id, "INTAKE", 3)

        # Dispatch
        ready = self.sl.get_ready_packets(run_id, "INTAKE")
        self.sl.dispatch_all(run_id, ready)

        # Simulate all accepted
        for pid in pids:
            self.rk.receive_result(run_id, pid, "result.json")
            self.rk.start_validation(run_id, pid)
            self.rk.accept_packet(run_id, pid)

        # Poll
        results = self.sl.poll_until_complete(run_id, pids, poll_interval=0.01)
        self.assertEqual(len(results), 3)
        for pid in pids:
            self.assertEqual(results[pid], "ACCEPTED")

        # Outcome
        outcome = self.sl.determine_phase_outcome(results)
        self.assertTrue(outcome["passed"])

    def test_supervise_phase_with_one_repair_requested(self):
        """Create 2 packets, accept one, reject one (→REPAIR_REQUESTED), check outcome."""
        run_id = "supervisor_phase_repair"
        self.rk.create_run(run_id)
        pids = self._create_packets_in_phase(run_id, "INTAKE", 2)

        ready = self.sl.get_ready_packets(run_id, "INTAKE")
        self.sl.dispatch_all(run_id, ready)

        # Accept first
        self.rk.receive_result(run_id, pids[0], "result.json")
        self.rk.start_validation(run_id, pids[0])
        self.rk.accept_packet(run_id, pids[0])

        # Reject second — goes to REPAIR_REQUESTED because max_repair_attempts=2
        self.rk.receive_result(run_id, pids[1], "result.json")
        self.rk.start_validation(run_id, pids[1])
        self.rk.reject_packet(run_id, pids[1], error="Needs repair")

        results = self.sl.poll_until_complete(run_id, pids, poll_interval=0.01)
        outcome = self.sl.determine_phase_outcome(results)
        # First accepted, second needs repair — not a clean pass
        self.assertFalse(outcome["passed"])
        self.assertEqual(outcome["accepted"], 1)
        self.assertEqual(outcome["repair_requested"], 1)

    def test_supervise_phase_with_first_rejection_requests_repair(self):
        """Create 2 packets, accept one, reject one (first rejection → REPAIR_REQUESTED)."""
        run_id = "supervisor_phase_repair_req"
        self.rk.create_run(run_id)
        pids = self._create_packets_in_phase(run_id, "INTAKE", 2)

        ready = self.sl.get_ready_packets(run_id, "INTAKE")
        self.sl.dispatch_all(run_id, ready)

        # Accept first
        self.rk.receive_result(run_id, pids[0], "result.json")
        self.rk.start_validation(run_id, pids[0])
        self.rk.accept_packet(run_id, pids[0])

        # Reject second with default max_repair_attempts=2 → REPAIR_REQUESTED
        self.rk.receive_result(run_id, pids[1], "result.json")
        self.rk.start_validation(run_id, pids[1])
        self.rk.reject_packet(run_id, pids[1], error="Needs repair")

        results = self.sl.poll_until_complete(run_id, pids, poll_interval=0.01)
        outcome = self.sl.determine_phase_outcome(results)
        self.assertFalse(outcome["passed"])
        self.assertEqual(outcome["accepted"], 1)
        self.assertEqual(outcome["repair_requested"], 1)

    # ══════════════════════════════════════════════════════════════════════
    #  get_active_phase
    # ══════════════════════════════════════════════════════════════════════

    def test_get_active_phase_after_create_and_first_transition(self):
        run_id = "supervisor_active"
        self.rk.create_run(run_id)
        # After create, current_phase is NEW. No phase is ACTIVE yet.
        active_before = self.sl.get_active_phase(run_id)
        self.assertIsNone(active_before)
        # Transition to INTAKE — first phase becomes ACTIVE
        self.rk.transition_to(run_id, "INTAKE")
        active = self.sl.get_active_phase(run_id)
        self.assertIsNotNone(active)
        self.assertEqual(active["phase"], "INTAKE")

    def test_get_active_phase_after_second_transition(self):
        run_id = "supervisor_active_transition"
        self.rk.create_run(run_id)
        self.rk.transition_to(run_id, "INTAKE")
        self.rk.transition_to(run_id, "QUESTIONING")
        active = self.sl.get_active_phase(run_id)
        self.assertIsNotNone(active)
        self.assertEqual(active["phase"], "QUESTIONING")

    # ══════════════════════════════════════════════════════════════════════
    #  _get_next_phase
    # ══════════════════════════════════════════════════════════════════════

    def test_next_phase_sequence(self):
        self.assertEqual(self.sl._get_next_phase("QUESTIONING"), "RESEARCHING")
        self.assertEqual(self.sl._get_next_phase("IMPLEMENTING"), "VALIDATOR_BUILDING")
        self.assertEqual(self.sl._get_next_phase("DONE"), None)
        self.assertEqual(self.sl._get_next_phase("UNKNOWN_PHASE"), None)

    # ══════════════════════════════════════════════════════════════════════
    #  are_dependencies_met
    # ══════════════════════════════════════════════════════════════════════

    def test_packet_with_no_deps_is_ready(self):
        run_id = "supervisor_deps_none"
        self.rk.create_run(run_id)
        pid = self.rk.create_work_packet(
            run_id, phase="INTAKE", role="Questioner",
            task="No deps",
        )
        pkt = self.rk.get_packet(run_id, pid)
        self.assertTrue(self.sl.are_dependencies_met(pkt, run_id))

    def test_packet_with_met_deps_is_ready(self):
        run_id = "supervisor_deps_met"
        self.rk.create_run(run_id)
        dep_pid = self.rk.create_work_packet(
            run_id, phase="INTAKE", role="Questioner",
            task="Dependency",
        )
        self._simulate_packet_lifecycle(run_id, dep_pid, accept=True)

        pid = self.rk.create_work_packet(
            run_id, phase="INTAKE", role="Questioner",
            task="Depends on dep",
            dependencies=[dep_pid],
        )
        pkt = self.rk.get_packet(run_id, pid)
        self.assertTrue(self.sl.are_dependencies_met(pkt, run_id))

    def test_packet_with_unmet_deps_not_ready(self):
        run_id = "supervisor_deps_unmet"
        self.rk.create_run(run_id)
        dep_pid = self.rk.create_work_packet(
            run_id, phase="INTAKE", role="Questioner",
            task="Unmet dependency",
        )
        # Don't dispatch or accept the dependency

        pid = self.rk.create_work_packet(
            run_id, phase="INTAKE", role="Questioner",
            task="Depends on unmet",
            dependencies=[dep_pid],
        )
        pkt = self.rk.get_packet(run_id, pid)
        self.assertFalse(self.sl.are_dependencies_met(pkt, run_id))


if __name__ == "__main__":
    unittest.main()
