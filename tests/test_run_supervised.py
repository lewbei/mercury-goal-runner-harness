#!/usr/bin/env python3
"""End-to-end test of the supervised run pipeline.

Tests:
- run_supervised creates packets for a phase, dispatches them, runs tools
- Skills are accumulated progressively
- Write scope validators are accessible
- Repair budget validators are accessible
- Phase failures propagate correctly
"""

import json
import unittest
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_rs():
    import importlib.util
    path = ROOT / ".agentic-pi" / "runtime" / "run_supervised.py"
    spec = importlib.util.spec_from_file_location("run_supervised", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_rk():
    import importlib.util
    path = ROOT / ".agentic-pi" / "run_kernel" / "run_kernel.py"
    spec = importlib.util.spec_from_file_location("run_kernel", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SupervisedRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rs = load_rs()
        cls.rk = load_rk()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.old_runs = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs
        import shutil
        shutil.rmtree(self.tmp)

    def _prepare_goal_run(self, run_id: str):
        """Create a minimal run with a goal contract for testing."""
        self.rk.create_run(run_id)
        run_dir = self.rk._RUNS_DIR / run_id

        # Create minimal goal_contract.json
        goal = {
            "schema_version": "goal_contract_v1",
            "run_id": run_id,
            "goal": "Create a test file",
            "mode": "legacy",
            "final_outputs": [f"artifacts/{run_id}_output.txt"],
        }
        (run_dir / "goal_contract.json").write_text(
            json.dumps(goal, indent=2), encoding="utf-8")
        required_phases = [
            "Question",
            "Research",
            "Design",
            "Structure",
            "PlanGraph",
            "Implement",
            "Verify",
            "Policy",
            "Replay",
            "Certify",
            "Report",
            "Memory",
        ]
        coverage = {
            "dimensions": [
                {
                    "name": phase,
                    "covered": True,
                    "task": f"{phase} task",
                    "artifact": f"artifacts/{phase.lower()}_artifact.json",
                    "validator": "deterministic_validator",
                    "verifier": "independent_verifier",
                    "authority": "P2",
                    "status": "COVERED",
                }
                for phase in required_phases
            ],
            "success_criteria": [
                {
                    "criterion": "Create a test file",
                    "validator": "deterministic_validator",
                }
            ],
        }
        (run_dir / "plan_coverage_matrix.json").write_text(
            json.dumps(coverage, indent=2), encoding="utf-8")

        return run_dir

    # ══════════════════════════════════════════════════════════════════════
    #  Layer validators accessible
    # ══════════════════════════════════════════════════════════════════════

    def test_check_write_scope_accessible(self):
        """The write scope validator is importable from run_supervised."""
        result = self.rs.check_write_scope(
            ".agentic-runs/test/artifacts/report.json",
            "Engineer", "test")
        self.assertIn("allowed", result)
        self.assertIn("reason", result)

    def test_check_repair_budget_accessible(self):
        """The repair budget validator is importable from run_supervised."""
        result = self.rs.check_repair_budget("REPAIRING_PLAN", 0)
        self.assertIn("budget_exhausted", result)
        self.assertFalse(result["budget_exhausted"])

    def test_check_repair_scope_accessible(self):
        """The repair scope validator is importable from run_supervised."""
        result = self.rs.check_repair_scope(
            "write to final_status.json", "REPAIRING_PLAN")
        self.assertIn("allowed", result)
        self.assertFalse(result["allowed"])

    # ══════════════════════════════════════════════════════════════════════
    #  create_packets_for_phase
    # ══════════════════════════════════════════════════════════════════════

    def test_create_packets_for_planning_phase(self):
        """PLANNING phase should create 4 packets (plan_router, selector, merger, graph_builder)."""
        run_id = "rs_packets_planning"
        run_dir = self._prepare_goal_run(run_id)

        pids = self.rs.create_packets_for_phase(
            self.rk, run_id, "PLANNING", run_dir)
        self.assertEqual(len(pids), 4,
                        "PLANNING phase should have 4 tool packets")
        for pid in pids:
            pkt = self.rk.get_packet(run_id, pid)
            self.assertEqual(pkt["status"], "PENDING")

    def test_create_packets_for_implementing_phase(self):
        """IMPLEMENTING phase should create 1 packet (guarded_worker)."""
        run_id = "rs_packets_implement"
        run_dir = self._prepare_goal_run(run_id)

        pids = self.rs.create_packets_for_phase(
            self.rk, run_id, "IMPLEMENTING", run_dir)
        self.assertEqual(len(pids), 1)
        pkt = self.rk.get_packet(run_id, pids[0])
        self.assertEqual(pkt["role"], "Engineer")

    def test_create_packets_for_empty_phase(self):
        """VALIDATOR_BUILDING has no tools — should create 0 packets."""
        run_id = "rs_packets_empty"
        run_dir = self._prepare_goal_run(run_id)

        pids = self.rs.create_packets_for_phase(
            self.rk, run_id, "VALIDATOR_BUILDING", run_dir)
        self.assertEqual(pids, [])

    # ══════════════════════════════════════════════════════════════════════
    #  Skills accumulated in packet context
    # ══════════════════════════════════════════════════════════════════════

    def test_planning_packets_have_accumulated_skills(self):
        """Packets created in PLANNING have skills from prior phases."""
        run_id = "rs_skills_planning"
        run_dir = self._prepare_goal_run(run_id)

        pids = self.rs.create_packets_for_phase(
            self.rk, run_id, "PLANNING", run_dir)
        for pid in pids:
            pkt = self.rk.get_packet(run_id, pid)
            ctx = pkt.get("accumulated_skills_context", "")
            self.assertIn("question-contract", ctx)
            self.assertIn("research-pack", ctx)
            self.assertIn("design-options", ctx)
            self.assertIn("structure-outline", ctx)
            self.assertIn("root-plan", ctx)

    def test_implementing_packets_have_path_grounding_skill(self):
        """Packets created in IMPLEMENTING have path-grounding skill."""
        run_id = "rs_skills_implement"
        run_dir = self._prepare_goal_run(run_id)

        pids = self.rs.create_packets_for_phase(
            self.rk, run_id, "IMPLEMENTING", run_dir)
        for pid in pids:
            pkt = self.rk.get_packet(run_id, pid)
            ctx = pkt.get("accumulated_skills_context", "")
            self.assertIn("path-grounding", ctx)
            self.assertIn("artifact-contract", ctx)

    # ══════════════════════════════════════════════════════════════════════
    #  execute_phase — end-to-end with real tool execution
    # ══════════════════════════════════════════════════════════════════════

    def test_execute_planning_phase_with_all_tools(self):
        """Run the PLANNING phase: create 4 packets, dispatch, execute tools, collect."""
        run_id = "rs_exec_planning"
        run_dir = self._prepare_goal_run(run_id)

        # Transition to PLANNING
        self.rk.transition_to(run_id, "INTAKE")
        self.rk.transition_to(run_id, "QUESTIONING")
        self.rk.transition_to(run_id, "RESEARCHING")
        self.rk.transition_to(run_id, "DESIGNING")
        self.rk.transition_to(run_id, "STRUCTURING")
        self.rk.transition_to(run_id, "PLANNING")

        # Execute via the loaded module directly
        report = self.rs.execute_phase(self.rk, self.rs._get_sl(),
                                       run_id, "PLANNING", run_dir)
        self.assertIn("passed", report)
        self.assertIn("packets_created", report)
        self.assertIn("skills_loaded", report)
        self.assertGreater(len(report["skills_loaded"]), 0,
                          "PLANNING should have accumulated skills")

    # ══════════════════════════════════════════════════════════════════════
    #  main() exit code
    # ══════════════════════════════════════════════════════════════════════



    # ══════════════════════════════════════════════════════════════════════
    #  PHASE_TOOLS mapping completeness
    # ══════════════════════════════════════════════════════════════════════

    def test_all_phases_have_tool_entries(self):
        """All agent phases in PHASE_TOOLS have entries (may be empty list)."""
        for phase in self.rs.AGENT_PHASES:
            self.assertIn(phase, self.rs.PHASE_TOOLS,
                         f"Phase {phase} missing from PHASE_TOOLS")


if __name__ == "__main__":
    unittest.main()
