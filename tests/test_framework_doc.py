import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrameworkDocTests(unittest.TestCase):
    def test_framework_doc_exists_and_locks_core_question(self):
        doc = (ROOT / "FRAMEWORK.md").read_text(encoding="utf-8")

        self.assertIn("Who is allowed to certify DONE?", doc)
        self.assertIn("Agents do work.", doc)
        self.assertIn("Policy engine judges the evidence.", doc)
        self.assertIn("Certifier writes the final status.", doc)
        self.assertIn("Pi only reports what the certifier wrote.", doc)

    def test_framework_doc_records_current_v13_state(self):
        doc = (ROOT / "FRAMEWORK.md").read_text(encoding="utf-8")

        self.assertIn("v1.3 = Strategy Planner", doc)
        self.assertIn("raw_simple_legacy -> DONE_PASS", doc)
        self.assertIn("raw_p2_provenance -> CERTIFIED_DONE", doc)
        self.assertIn("raw_missing_verifier -> NOT_DONE", doc)
        self.assertIn("raw goal -> branch candidates -> selected branch -> merged_plan.json", doc)
        self.assertIn("raw goal -> task type -> capability inventory -> strategy candidates", doc)

    def test_framework_doc_uses_actual_current_paths(self):
        doc = (ROOT / "FRAMEWORK.md").read_text(encoding="utf-8")

        for path in [
            ".agentic-pi/runtime/compile_raw_goal.py",
            ".agentic-pi/runtime/planning_proof_runner.py",
            ".agentic-pi/runtime/task_type_router.py",
            ".agentic-pi/runtime/capability_inventory.py",
            ".agentic-pi/runtime/strategy_generator.py",
            ".agentic-pi/runtime/strategy_applicability_gate.py",
            ".agentic-pi/runtime/strategy_scorer.py",
            ".agentic-pi/runtime/strategy_selector.py",
            ".agentic-pi/runtime/step_compiler.py",
            ".agentic-pi/runtime/strategy_proof_runner.py",
            ".agentic-pi/runtime/pi_cli.py",
            ".agentic-pi/runtime/policy_engine.py",
            ".agentic-pi/runtime/verifier_provenance.py",
            ".agentic-pi/validators/certify_run.py",
            ".agentic-pi/validators/smell_scanner.py",
            ".agentic-pi/validators/strength_scorer.py",
            ".agentic-pi/runtime/audit_run.py",
            ".agentic-pi/runtime/replay_run.py",
            ".agentic-pi/runtime/rollback_run.py",
        ]:
            with self.subTest(path=path):
                self.assertIn(path, doc)
                self.assertTrue((ROOT / path).exists())

    def test_framework_doc_separates_proven_from_not_proven(self):
        doc = (ROOT / "FRAMEWORK.md").read_text(encoding="utf-8")

        self.assertIn("## Proven Behavior", doc)
        self.assertIn("## Not Proven", doc)
        self.assertIn("prepared legacy full run through Pi -> DONE_PASS", doc)
        self.assertIn("prepared provenance full run through Pi -> CERTIFIED_DONE", doc)
        self.assertIn("arbitrary raw natural-language autonomy", doc)
        self.assertIn("full goal-runner.chain.md autonomous runtime", doc)
        self.assertIn("milestone planning", doc)
        self.assertIn("experience memory", doc)
        self.assertNotIn("Pi can safely solve arbitrary raw goals autonomously.", doc)


if __name__ == "__main__":
    unittest.main()
