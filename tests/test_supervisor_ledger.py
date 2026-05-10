#!/usr/bin/env python3
"""Unittest tests for the RPG-Harness v5 Supervisor Ledger (Phase 2).

Tests cover:
- Transition validator (validate_transition.py)
- Run Kernel state machine (run_kernel.py)
- Work packet lifecycle
- Phase queue management
- Dispatch log recording
- Budget enforcement
- Protected file enforcement
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[1]
RUN_KERNEL_DIR = ROOT / ".agentic-pi" / "run_kernel"
CORE_DIR = ROOT / ".agentic-pi" / "core"

if str(RUN_KERNEL_DIR) not in sys.path:
    sys.path.insert(0, str(RUN_KERNEL_DIR))

# ── Imports (late so path setup works) ────────────────────────────────────────

def _load_module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_VT = None
_RK = None


def _get_vt():
    global _VT
    if _VT is None:
        _VT = _load_module("validate_transition",
                           RUN_KERNEL_DIR / "validate_transition.py")
    return _VT


def _get_rk():
    global _RK
    if _RK is None:
        _RK = _load_module("run_kernel",
                           RUN_KERNEL_DIR / "run_kernel.py")
    return _RK


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════════════════════
#  Transition Validator Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestTransitionValidator(unittest.TestCase):
    """Test validate_transition.py."""

    def setUp(self):
        self.vt = _get_vt()

    def test_phase_name_valid(self):
        errors = self.vt.validate_phase_name("NEW")
        self.assertEqual(errors, [])

    def test_phase_name_invalid(self):
        errors = self.vt.validate_phase_name("INVALID_PHASE")
        self.assertGreater(len(errors), 0)
        self.assertIn("Unknown phase", errors[0])

    def test_all_registry_phases_recognized(self):
        registry = self.vt.load_phase_registry()
        for entry in registry:
            errors = self.vt.validate_phase_name(entry["phase"])
            self.assertEqual(errors, [],
                             f"Phase '{entry['phase']}' not recognized")

    def test_valid_transition_new_to_intake(self):
        errors = self.vt.validate_transition_with_registry("NEW", "INTAKE")
        self.assertEqual(errors, [])

    def test_valid_transition_full_chain(self):
        chain = [
            ("NEW", "INTAKE"),
            ("INTAKE", "QUESTIONING"),
            ("QUESTIONING", "RESEARCHING"),
            ("RESEARCHING", "DESIGNING"),
            ("DESIGNING", "STRUCTURING"),
            ("STRUCTURING", "PLANNING"),
            ("PLANNING", "WORKTREE_READY"),
            ("WORKTREE_READY", "IMPLEMENTING"),
            ("IMPLEMENTING", "VALIDATOR_BUILDING"),
            ("VALIDATOR_BUILDING", "VALIDATING"),
            ("VALIDATING", "EVIDENCE_INDEXING"),
            ("EVIDENCE_INDEXING", "POLICY_DECIDING"),
            ("POLICY_DECIDING", "REPLAYING"),
            ("REPLAYING", "CERTIFYING"),
            ("CERTIFYING", "REPORTING"),
            ("REPORTING", "MEMORY_CONSOLIDATING"),
            ("MEMORY_CONSOLIDATING", "DONE"),
        ]
        for from_phase, to_phase in chain:
            with self.subTest(f"{from_phase} -> {to_phase}"):
                errors = self.vt.validate_transition_with_registry(from_phase, to_phase)
                self.assertEqual(errors, [])

    def test_invalid_transition_new_to_certifying(self):
        errors = self.vt.validate_transition_with_registry("NEW", "CERTIFYING")
        self.assertGreater(len(errors), 0)

    def test_wildcard_transition_authority_violation(self):
        errors = self.vt.validate_transition_with_registry("IMPLEMENTING",
                                                           "BLOCKED_BY_AUTHORITY_VIOLATION")
        self.assertEqual(errors, [])

    def test_blocked_to_repair_transitions(self):
        blocked_repair_pairs = [
            ("BLOCKED_BY_GOAL_AMBIGUITY", "REPAIRING_PLAN"),
            ("BLOCKED_BY_MISSING_SUCCESS_CRITERIA", "REPAIRING_PLAN"),
            ("BLOCKED_BY_ARTIFACT_MISPLACEMENT", "REPAIRING_ARTIFACT_ROUTING"),
            ("BLOCKED_BY_VALIDATOR_UNTRUSTED", "REPAIRING_VALIDATOR"),
            ("BLOCKED_BY_EVIDENCE_GAP", "REPAIRING_EVIDENCE"),
            ("BLOCKED_BY_REPLAY_MISMATCH", "REPAIRING_EVIDENCE"),
            ("BLOCKED_BY_AUTHORITY_VIOLATION", "REPAIRING_PLAN"),
        ]
        for from_phase, to_phase in blocked_repair_pairs:
            with self.subTest(f"{from_phase} -> {to_phase}"):
                errors = self.vt.validate_transition_with_registry(from_phase, to_phase)
                self.assertEqual(errors, [])

    def test_repair_to_forward_transitions(self):
        repair_forward_pairs = [
            ("REPAIRING_PLAN", "PLANNING"),
            ("REPAIRING_ARTIFACT_ROUTING", "WORKTREE_READY"),
            ("REPAIRING_VALIDATOR", "VALIDATOR_BUILDING"),
            ("REPAIRING_EVIDENCE", "EVIDENCE_INDEXING"),
            ("REPAIRING_IMPLEMENTATION", "IMPLEMENTING"),
        ]
        for from_phase, to_phase in repair_forward_pairs:
            with self.subTest(f"{from_phase} -> {to_phase}"):
                errors = self.vt.validate_transition_with_registry(from_phase, to_phase)
                self.assertEqual(errors, [])

    def test_all_rules_have_known_phases(self):
        rules = self.vt.load_transition_rules()
        registry = self.vt.load_phase_registry()
        known_phases = {e["phase"] for e in registry}
        for rule in rules:
            from_phase = rule.get("from")
            to_phase = rule.get("to")
            if from_phase is not None:
                self.assertIn(from_phase, known_phases,
                              f"Rule from '{from_phase}' not in registry")
            self.assertIn(to_phase, known_phases,
                          f"Rule to '{to_phase}' not in registry")


# ══════════════════════════════════════════════════════════════════════════════
#  Run Kernel Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestRunKernel(unittest.TestCase):
    """Test run_kernel.py state machine."""

    def setUp(self):
        self.rk = _get_rk()
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.old_runs_dir = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp_dir

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs_dir
        shutil.rmtree(self.tmp_dir)

    def _assert_state(self, run_id: str, expected_phase: str):
        state = self.rk.get_run_state(run_id)
        self.assertEqual(state["current_phase"], expected_phase)
        return state

    def test_create_run(self):
        run_dir = self.rk.create_run("test_create_001")
        self.assertTrue(run_dir.exists())
        self.assertTrue((run_dir / "run_state.json").exists())
        self.assertTrue((run_dir / "phase_queue.json").exists())
        self.assertTrue((run_dir / "run_manifest.json").exists())
        self.assertTrue((run_dir / "work_packets").is_dir())
        self.assertTrue((run_dir / "work_results").is_dir())
        self.assertTrue((run_dir / "validation_results").is_dir())
        self.assertTrue((run_dir / "dispatch_log.jsonl").exists())
        self._assert_state("test_create_001", "NEW")

    def test_create_duplicate_run_raises(self):
        self.rk.create_run("test_dup_001")
        with self.assertRaises(FileExistsError):
            self.rk.create_run("test_dup_001")

    def test_get_run_state(self):
        self.rk.create_run("test_state_001")
        state = self.rk.get_run_state("test_state_001")
        self.assertEqual(state["schema_version"], "run_state_v1")
        self.assertEqual(state["overall_status"], "IN_PROGRESS")
        self.assertEqual(len(state["phase_history"]), 1)
        self.assertEqual(state["phase_history"][0]["phase"], "NEW")

    def test_get_phase_queue(self):
        self.rk.create_run("test_queue_001")
        pq = self.rk.get_phase_queue("test_queue_001")
        self.assertEqual(pq["schema_version"], "phase_queue_v1")
        self.assertGreater(len(pq["phases"]), 0)
        phase_names = [p["phase"] for p in pq["phases"]]
        self.assertIn("IMPLEMENTING", phase_names)
        self.assertIn("CERTIFYING", phase_names)
        self.assertIn("POLICY_DECIDING", phase_names)

    def test_list_runs(self):
        self.rk.create_run("test_list_001")
        self.rk.create_run("test_list_002")
        runs = self.rk.list_runs()
        self.assertIn("test_list_001", runs)
        self.assertIn("test_list_002", runs)

    def test_get_dispatch_log_empty(self):
        self.rk.create_run("test_log_empty_001")
        log = self.rk.get_dispatch_log("test_log_empty_001")
        self.assertGreaterEqual(len(log), 1)  # at least run_created

    def test_valid_transition(self):
        self.rk.create_run("test_trans_001")
        self.rk.transition_to("test_trans_001", "INTAKE")
        self._assert_state("test_trans_001", "INTAKE")
        self.assertEqual(
            self.rk.get_run_state("test_trans_001")["previous_phase"],
            "NEW",
        )

    def test_invalid_transition_raises(self):
        self.rk.create_run("test_bad_trans_001")
        with self.assertRaises(RuntimeError):
            self.rk.transition_to("test_bad_trans_001", "CERTIFYING")
        self._assert_state("test_bad_trans_001", "NEW")

    def test_blocked_state_transition(self):
        self.rk.create_run("test_blocked_001")
        self.rk.transition_to("test_blocked_001", "INTAKE")
        self.rk.transition_to("test_blocked_001", "QUESTIONING")
        self.rk.transition_to("test_blocked_001", "BLOCKED_BY_GOAL_AMBIGUITY")
        self._assert_state("test_blocked_001", "BLOCKED_BY_GOAL_AMBIGUITY")
        state = self.rk.get_run_state("test_blocked_001")
        self.assertEqual(state["overall_status"], "BLOCKED")

    def test_repair_forward_transition(self):
        self.rk.create_run("test_repair_001")
        # Must go through proper chain before blocking
        self.rk.transition_to("test_repair_001", "INTAKE")
        self.rk.transition_to("test_repair_001", "QUESTIONING")
        self.rk.transition_to("test_repair_001", "BLOCKED_BY_GOAL_AMBIGUITY")
        self.rk.transition_to("test_repair_001", "REPAIRING_PLAN")
        self.rk.transition_to("test_repair_001", "PLANNING")
        self._assert_state("test_repair_001", "PLANNING")

    def test_phase_history_records_transitions(self):
        self.rk.create_run("test_history_001")
        self.rk.transition_to("test_history_001", "INTAKE")
        self.rk.transition_to("test_history_001", "QUESTIONING")
        self.rk.transition_to("test_history_001", "RESEARCHING")
        state = self.rk.get_run_state("test_history_001")
        self.assertEqual(len(state["phase_history"]), 4)  # NEW + 3 transitions
        self.assertEqual(state["phase_history"][1]["phase"], "INTAKE")
        self.assertEqual(state["phase_history"][2]["phase"], "QUESTIONING")
        self.assertEqual(state["phase_history"][3]["phase"], "RESEARCHING")

    def test_phase_queue_updates_on_transition(self):
        self.rk.create_run("test_pq_update_001")
        self.rk.transition_to("test_pq_update_001", "INTAKE")
        pq = self.rk.get_phase_queue("test_pq_update_001")
        intake_phase = [p for p in pq["phases"] if p["phase"] == "INTAKE"][0]
        self.assertEqual(intake_phase["status"], "ACTIVE")
        self.assertIsNotNone(intake_phase["started_at"])
        # The first forward phase (INTAKE) becomes active; NEW is not a phase queue entry

    def test_dispatch_log_records_events(self):
        self.rk.create_run("test_dlog_001")
        self.rk.transition_to("test_dlog_001", "INTAKE")
        log = self.rk.get_dispatch_log("test_dlog_001")
        events = [e["event"] for e in log]
        self.assertIn("run_created", events)
        self.assertIn("phase_transition", events)

    def test_run_manifest_contains_metadata(self):
        self.rk.create_run("test_manifest_001", goal_contract_path="goals/test.json")
        manifest = load_json(self.rk.get_run_dir("test_manifest_001") / "run_manifest.json")
        self.assertEqual(manifest["run_id"], "test_manifest_001")
        self.assertEqual(manifest["goal_contract_path"], "goals/test.json")
        self.assertEqual(manifest["schema_version"], "run_manifest_v1")


# ══════════════════════════════════════════════════════════════════════════════
#  Work Packet Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkPacketLifecycle(unittest.TestCase):
    """Test the work packet lifecycle."""

    def setUp(self):
        self.rk = _get_rk()
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.old_runs_dir = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp_dir
        self.rk.create_run("test_wp_lifecycle_001")

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs_dir
        shutil.rmtree(self.tmp_dir)

    def test_create_packet(self):
        pid = self.rk.create_work_packet(
            "test_wp_lifecycle_001",
            phase="INTAKE",
            role="Questioner",
            task="Create question contract",
        )
        self.assertTrue(pid.startswith("WP.INTAKE."))
        pkt = self.rk.get_packet("test_wp_lifecycle_001", pid)
        self.assertEqual(pkt["status"], "PENDING")
        self.assertEqual(pkt["phase"], "INTAKE")
        self.assertEqual(pkt["role"], "Questioner")
        self.assertFalse(pkt["status_claim_allowed"])

    def test_dispatch_packet(self):
        pid = self.rk.create_work_packet(
            "test_wp_lifecycle_001",
            phase="INTAKE",
            role="Questioner",
            task="Create question contract",
        )
        self.rk.dispatch_packet("test_wp_lifecycle_001", pid)
        pkt = self.rk.get_packet("test_wp_lifecycle_001", pid)
        self.assertEqual(pkt["status"], "DISPATCHED")
        self.assertIsNotNone(pkt["dispatch_timestamp"])

    def test_dispatch_non_pending_raises(self):
        pid = self.rk.create_work_packet(
            "test_wp_lifecycle_001",
            phase="INTAKE",
            role="Questioner",
            task="Create question contract",
        )
        self.rk.dispatch_packet("test_wp_lifecycle_001", pid)
        with self.assertRaises(RuntimeError):
            self.rk.dispatch_packet("test_wp_lifecycle_001", pid)

    def test_full_lifecycle_accept(self):
        pid = self.rk.create_work_packet(
            "test_wp_lifecycle_001",
            phase="INTAKE",
            role="Questioner",
            task="Create question contract",
        )
        self.rk.dispatch_packet("test_wp_lifecycle_001", pid)
        self.rk.receive_result("test_wp_lifecycle_001", pid, "work_results/r1.json")
        self.rk.start_validation("test_wp_lifecycle_001", pid)
        self.rk.accept_packet("test_wp_lifecycle_001", pid, "validation_results/v1.json")

        pkt = self.rk.get_packet("test_wp_lifecycle_001", pid)
        self.assertEqual(pkt["status"], "ACCEPTED")
        self.assertEqual(pkt["result_path"], "work_results/r1.json")
        self.assertEqual(pkt["validation_result_path"], "validation_results/v1.json")

    def test_reject_with_repair(self):
        pid = self.rk.create_work_packet(
            "test_wp_lifecycle_001",
            phase="INTAKE",
            role="Questioner",
            task="Create question contract",
            max_repair_attempts=1,
        )
        self.rk.dispatch_packet("test_wp_lifecycle_001", pid)
        self.rk.receive_result("test_wp_lifecycle_001", pid, "work_results/r1.json")
        self.rk.start_validation("test_wp_lifecycle_001", pid)
        self.rk.reject_packet("test_wp_lifecycle_001", pid, error="Content invalid")

        pkt = self.rk.get_packet("test_wp_lifecycle_001", pid)
        self.assertEqual(pkt["status"], "REPAIR_REQUESTED")
        self.assertEqual(pkt["repair_attempt_count"], 1)

    def test_reject_exhausts_budget(self):
        pid = self.rk.create_work_packet(
            "test_wp_lifecycle_001",
            phase="INTAKE",
            role="Questioner",
            task="Create question contract",
            max_repair_attempts=0,
        )
        self.rk.dispatch_packet("test_wp_lifecycle_001", pid)
        self.rk.receive_result("test_wp_lifecycle_001", pid, "work_results/r1.json")
        self.rk.start_validation("test_wp_lifecycle_001", pid)
        self.rk.reject_packet("test_wp_lifecycle_001", pid, error="Content invalid")

        pkt = self.rk.get_packet("test_wp_lifecycle_001", pid)
        self.assertEqual(pkt["status"], "REJECTED")

    def test_block_packet(self):
        pid = self.rk.create_work_packet(
            "test_wp_lifecycle_001",
            phase="INTAKE",
            role="Questioner",
            task="Create question contract",
        )
        self.rk.block_packet("test_wp_lifecycle_001", pid, error="External dependency")
        pkt = self.rk.get_packet("test_wp_lifecycle_001", pid)
        self.assertEqual(pkt["status"], "BLOCKED")

    def test_cancel_packet(self):
        pid = self.rk.create_work_packet(
            "test_wp_lifecycle_001",
            phase="INTAKE",
            role="Questioner",
            task="Create question contract",
        )
        self.rk.cancel_packet("test_wp_lifecycle_001", pid, error="No longer needed")
        pkt = self.rk.get_packet("test_wp_lifecycle_001", pid)
        self.assertEqual(pkt["status"], "CANCELLED")

    def test_list_packets_empty(self):
        packets = self.rk.list_packets("test_wp_lifecycle_001")
        self.assertEqual(packets, [])

    def test_list_packets_filtered(self):
        pid1 = self.rk.create_work_packet(
            "test_wp_lifecycle_001",
            phase="INTAKE",
            role="Questioner",
            task="Task A",
        )
        pid2 = self.rk.create_work_packet(
            "test_wp_lifecycle_001",
            phase="RESEARCHING",
            role="Researcher",
            task="Task B",
        )
        intake_packets = self.rk.list_packets("test_wp_lifecycle_001", phase="INTAKE")
        self.assertEqual(len(intake_packets), 1)
        self.assertEqual(intake_packets[0]["work_packet_id"], pid1)

        pending = self.rk.list_packets("test_wp_lifecycle_001", status="PENDING")
        self.assertEqual(len(pending), 2)

    def test_phase_queue_includes_packet_ids(self):
        pid = self.rk.create_work_packet(
            "test_wp_lifecycle_001",
            phase="INTAKE",
            role="Questioner",
            task="Create question contract",
        )
        pq = self.rk.get_phase_queue("test_wp_lifecycle_001")
        intake_entry = [p for p in pq["phases"] if p["phase"] == "INTAKE"][0]
        self.assertIn(pid, intake_entry["work_packet_ids"])

    def test_mark_phase_completed(self):
        self.rk.mark_phase_completed("test_wp_lifecycle_001", "INTAKE")
        pq = self.rk.get_phase_queue("test_wp_lifecycle_001")
        intake_entry = [p for p in pq["phases"] if p["phase"] == "INTAKE"][0]
        self.assertEqual(intake_entry["status"], "COMPLETED")
        self.assertIsNotNone(intake_entry["completed_at"])


# ══════════════════════════════════════════════════════════════════════════════
#  Dependency Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPacketDependencies(unittest.TestCase):
    """Test dependency resolution for work packets."""

    def setUp(self):
        self.rk = _get_rk()
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.old_runs_dir = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp_dir
        self.rk.create_run("test_dep_001")

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs_dir
        shutil.rmtree(self.tmp_dir)

    def test_get_next_pending_no_deps(self):
        pid = self.rk.create_work_packet(
            "test_dep_001",
            phase="INTAKE",
            role="Questioner",
            task="Task A",
        )
        next_pkt = self.rk.get_next_pending_packet("test_dep_001")
        self.assertIsNotNone(next_pkt)
        self.assertEqual(next_pkt["work_packet_id"], pid)

    def test_get_next_pending_with_met_deps(self):
        pid1 = self.rk.create_work_packet(
            "test_dep_001",
            phase="INTAKE",
            role="Questioner",
            task="Task A",
        )
        pid2 = self.rk.create_work_packet(
            "test_dep_001",
            phase="QUESTIONING",
            role="Questioner",
            task="Task B",
            dependencies=[pid1],
        )

        # Without pid1 accepted, pid2 should not be returned
        next_pkt = self.rk.get_next_pending_packet("test_dep_001")
        self.assertEqual(next_pkt["work_packet_id"], pid1)

        # Accept pid1
        self.rk.dispatch_packet("test_dep_001", pid1)
        self.rk.receive_result("test_dep_001", pid1, "work_results/r1.json")
        self.rk.start_validation("test_dep_001", pid1)
        self.rk.accept_packet("test_dep_001", pid1)

        # Now pid2 should be next
        next_pkt = self.rk.get_next_pending_packet("test_dep_001")
        self.assertIsNotNone(next_pkt)
        self.assertEqual(next_pkt["work_packet_id"], pid2)

    def test_get_next_pending_deps_not_met(self):
        pid1 = self.rk.create_work_packet(
            "test_dep_001",
            phase="INTAKE",
            role="Questioner",
            task="Task A",
        )
        pid2 = self.rk.create_work_packet(
            "test_dep_001",
            phase="QUESTIONING",
            role="Questioner",
            task="Task B",
            dependencies=[pid1],
        )

        # pid2 has unmet dep -> next should be pid1
        next_pkt = self.rk.get_next_pending_packet("test_dep_001")
        self.assertEqual(next_pkt["work_packet_id"], pid1)

    def test_get_next_pending_no_pending_packets(self):
        pid = self.rk.create_work_packet(
            "test_dep_001",
            phase="INTAKE",
            role="Questioner",
            task="Task A",
        )
        self.rk.dispatch_packet("test_dep_001", pid)
        next_pkt = self.rk.get_next_pending_packet("test_dep_001")
        self.assertIsNone(next_pkt)


# ══════════════════════════════════════════════════════════════════════════════
#  Trusted Core Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestTrustedCoreFiles(unittest.TestCase):
    """Test that the trusted core files exist and are valid JSON."""

    def test_trusted_core_manifest_exists(self):
        path = CORE_DIR / "trusted_core_manifest.json"
        self.assertTrue(path.exists(), f"Missing: {path}")
        data = load_json(path)
        self.assertEqual(data["schema_version"], "trusted_core_manifest_v1")
        self.assertIn("core_components", data)

    def test_core_authority_policy_exists(self):
        path = CORE_DIR / "core_authority_policy.json"
        self.assertTrue(path.exists(), f"Missing: {path}")
        data = load_json(path)
        self.assertEqual(data["schema_version"], "core_authority_policy_v1")
        self.assertIn("rules", data)
        # Only Certifier may certify
        for rule in data["rules"]:
            if rule["role"] == "Certifier":
                self.assertTrue(rule["may_certify"])
                self.assertTrue(rule["may_claim_done"])
            else:
                self.assertFalse(rule["may_certify"],
                                 f"Role '{rule['role']}' may_certify must be False")

    def test_protected_artifacts_exists(self):
        path = CORE_DIR / "protected_artifacts.json"
        self.assertTrue(path.exists(), f"Missing: {path}")
        data = load_json(path)
        self.assertEqual(data["schema_version"], "protected_artifacts_v1")
        self.assertIn("protected_paths", data)
        self.assertIn("allowed_writers", data)

    def test_status_lattice_exists(self):
        path = CORE_DIR / "status_lattice.json"
        self.assertTrue(path.exists(), f"Missing: {path}")
        data = load_json(path)
        self.assertEqual(data["schema_version"], "status_lattice_v1")
        self.assertIn("statuses", data)
        for status_name, info in data["statuses"].items():
            self.assertIn("is_final", info,
                          f"Status '{status_name}' missing is_final")

    def test_final_status_not_in_agent_writers(self):
        """Verify no non-Certifier role can write final_status.json."""
        data = load_json(CORE_DIR / "core_authority_policy.json")
        for rule in data["rules"]:
            if rule["role"] not in ("Certifier", "PolicyJudge", "ReplayJudge"):
                self.assertIn(
                    "final_status.json",
                    rule.get("may_not_write_types", []),
                    f"Role '{rule['role']}' does not forbid final_status.json"
                )


# ══════════════════════════════════════════════════════════════════════════════
#  Integration Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestIntegrationScenarios(unittest.TestCase):
    """Integration-level scenarios combining multiple components."""

    def setUp(self):
        self.rk = _get_rk()
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.old_runs_dir = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp_dir

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs_dir
        shutil.rmtree(self.tmp_dir)

    def test_simple_goal_pipeline(self):
        """Simulate a simple goal pipeline through the first few phases."""
        run_id = "test_pipeline_simple"
        self.rk.create_run(run_id)
        self.rk.transition_to(run_id, "INTAKE")

        # Create and process intake packet
        pid1 = self.rk.create_work_packet(
            run_id, phase="INTAKE", role="Questioner",
            task="Create goal contract",
        )
        self.rk.dispatch_packet(run_id, pid1)
        self.rk.receive_result(run_id, pid1, "work_results/intake_result.json")
        self.rk.start_validation(run_id, pid1)
        self.rk.accept_packet(run_id, pid1, "validation_results/intake_val.json")

        # Move to QUESTIONING
        self.rk.mark_phase_completed(run_id, "INTAKE")
        self.rk.transition_to(run_id, "QUESTIONING")

        # Verify state
        state = self.rk.get_run_state(run_id)
        self.assertEqual(state["current_phase"], "QUESTIONING")

        # Verify dispatch log
        log = self.rk.get_dispatch_log(run_id)
        events = [e["event"] for e in log]
        self.assertIn("work_packet_created", events)
        self.assertIn("work_packet_dispatched", events)
        self.assertIn("work_packet_result_received", events)
        self.assertIn("work_packet_accepted", events)
        self.assertIn("phase_completed", events)
        self.assertIn("phase_transition", events)

        # Verify packet persisted
        pkt = self.rk.get_packet(run_id, pid1)
        self.assertEqual(pkt["status"], "ACCEPTED")

        # Phase queue reflects completed INTAKE
        pq = self.rk.get_phase_queue(run_id)
        intake_entry = [p for p in pq["phases"] if p["phase"] == "INTAKE"][0]
        self.assertEqual(intake_entry["status"], "COMPLETED")

    def test_blocked_and_repair_scenario(self):
        """Simulate a block -> repair -> forward flow."""
        run_id = "test_repair_scenario"
        self.rk.create_run(run_id)

        # Goal ambiguity: must go through proper chain
        self.rk.transition_to(run_id, "INTAKE")
        self.rk.transition_to(run_id, "QUESTIONING")
        self.rk.transition_to(run_id, "BLOCKED_BY_GOAL_AMBIGUITY")

        state = self.rk.get_run_state(run_id)
        self.assertEqual(state["overall_status"], "BLOCKED")

        # Repair
        self.rk.transition_to(run_id, "REPAIRING_PLAN")
        rp_pkt = self.rk.create_work_packet(
            run_id, phase="REPAIRING_PLAN", role="Planner",
            task="Repair goal clarity",
            max_repair_attempts=1,
        )
        self.rk.dispatch_packet(run_id, rp_pkt)
        self.rk.receive_result(run_id, rp_pkt, "work_results/repair_result.json")
        self.rk.start_validation(run_id, rp_pkt)
        self.rk.accept_packet(run_id, rp_pkt, "validation_results/repair_val.json")

        # Back to planning
        self.rk.transition_to(run_id, "PLANNING")
        self._assert_state(run_id, "PLANNING")

    def test_multiple_packets_per_phase(self):
        """Multiple work packets in one phase."""
        run_id = "test_multi_packet"
        self.rk.create_run(run_id)
        # Must go through chain to reach IMPLEMENTING
        for phase in ["INTAKE", "QUESTIONING", "RESEARCHING", "DESIGNING",
                      "STRUCTURING", "PLANNING", "WORKTREE_READY"]:
            self.rk.transition_to(run_id, phase)
        self.rk.transition_to(run_id, "IMPLEMENTING")

        pids = []
        for i in range(3):
            pid = self.rk.create_work_packet(
                run_id, phase="IMPLEMENTING", role="Engineer",
                task=f"Implement feature {i+1}",
                dependencies=[pids[-1]] if pids else None,
            )
            pids.append(pid)

        packets = self.rk.list_packets(run_id, phase="IMPLEMENTING")
        self.assertEqual(len(packets), 3)

        # Process sequentially
        for i, pid in enumerate(pids):
            self.rk.dispatch_packet(run_id, pid)
            self.rk.receive_result(run_id, pid, f"work_results/impl_{i}.json")
            self.rk.start_validation(run_id, pid)
            self.rk.accept_packet(run_id, pid, f"validation_results/impl_{i}.json")

        pq = self.rk.get_phase_queue(run_id)
        impl_entry = [p for p in pq["phases"] if p["phase"] == "IMPLEMENTING"][0]
        self.assertEqual(len(impl_entry["work_packet_ids"]), 3)

    def _assert_state(self, run_id: str, expected_phase: str):
        state = self.rk.get_run_state(run_id)
        self.assertEqual(state["current_phase"], expected_phase)


# ══════════════════════════════════════════════════════════════════════════════
#  Schema File Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaFilesExist(unittest.TestCase):
    """Verify all expected schema and config files exist for Phase 2."""

    def test_run_state_schema(self):
        self.assertTrue((RUN_KERNEL_DIR / "run_state.schema.json").exists())

    def test_work_packet_schema(self):
        self.assertTrue((RUN_KERNEL_DIR / "work_packet.schema.json").exists())

    def test_phase_queue_schema(self):
        self.assertTrue((RUN_KERNEL_DIR / "phase_queue.schema.json").exists())

    def test_transition_rules(self):
        self.assertTrue((RUN_KERNEL_DIR / "transition_rules.json").exists())

    def test_phase_registry(self):
        self.assertTrue((RUN_KERNEL_DIR / "phase_registry.json").exists())

    def test_phase_budget(self):
        self.assertTrue((RUN_KERNEL_DIR / "phase_budget.json").exists())

    def test_validate_transition(self):
        self.assertTrue((RUN_KERNEL_DIR / "validate_transition.py").exists())

    def test_run_kernel(self):
        self.assertTrue((RUN_KERNEL_DIR / "run_kernel.py").exists())

    def test_core_directory(self):
        self.assertTrue(CORE_DIR.is_dir())
        self.assertTrue((CORE_DIR / "trusted_core_manifest.json").exists())
        self.assertTrue((CORE_DIR / "core_authority_policy.json").exists())
        self.assertTrue((CORE_DIR / "protected_artifacts.json").exists())
        self.assertTrue((CORE_DIR / "status_lattice.json").exists())


if __name__ == "__main__":
    unittest.main()
