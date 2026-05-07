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

    def test_framework_doc_records_current_v26_state(self):
        doc = (ROOT / "FRAMEWORK.md").read_text(encoding="utf-8")

        self.assertIn("v2.7 = Real Pi Agentic Autonomy Probe", doc)
        self.assertIn("Real Pi Agentic Autonomy Probe Layer", doc)
        self.assertIn("raw_simple_legacy -> DONE_PASS", doc)
        self.assertIn("raw_p2_provenance -> CERTIFIED_DONE", doc)
        self.assertIn("raw_missing_verifier -> NOT_DONE", doc)
        self.assertIn("raw goal -> branch candidates -> selected branch -> merged_plan.json", doc)
        self.assertIn("raw goal -> task type -> capability inventory -> strategy candidates", doc)
        self.assertIn("raw goal -> selected strategy -> milestone_plan.json -> local_step_plan.json", doc)
        self.assertIn("raw goal -> worker -> checkpoints -> drift_report.json -> delta_plan.json", doc)
        self.assertIn("Pi/tool session -> tool_use_audit.json -> trajectory_score.json", doc)
        self.assertIn("completed run -> experience_extract.json -> learning record -> retrieved_experience.json", doc)
        self.assertIn("task_type_decision.json -> domain_pack_selection.json -> domain-aware strategy_candidates.json", doc)
        self.assertIn("domain / memory / trajectory / drift evidence -> workflow_candidates.json -> workflow_search_trace.json", doc)
        self.assertIn("proof_matrix.json -> run_proof_matrix.py -> proof_matrix_result.json", doc)
        self.assertIn("verifier-generator -> verifier-reviewer -> goal-orchestrator", doc)
        self.assertIn("Pi/Mercury session -> verifier evidence -> certifier -> status artifacts", doc)
        self.assertIn("real `pi` interactive prompt -> Mercury tool use -> pi_chain_runtime_result.json", doc)
        self.assertIn("captured real Pi transcript -> pi_real_session_monitor.py", doc)
        self.assertIn("captured real Pi negative-status transcript -> pi_real_session_monitor.py", doc)
        self.assertIn("real Pi stdout/transcript -> pi_session_trace.jsonl -> pi_session_trace_monitor.py", doc)

    def test_framework_doc_uses_actual_current_paths(self):
        doc = (ROOT / "FRAMEWORK.md").read_text(encoding="utf-8")

        for path in [
            ".agentic-pi/runtime/compile_raw_goal.py",
            ".agentic-pi/runtime/planning_proof_runner.py",
            ".agentic-pi/runtime/task_type_router.py",
            ".agentic-pi/runtime/domain_pack_selector.py",
            ".agentic-pi/runtime/workflow_search.py",
            ".agentic-pi/runtime/run_proof_matrix.py",
            ".agentic-pi/runtime/run_pi_chain_smoke.py",
            ".agentic-pi/runtime/pi_direct_behavior_audit.py",
            ".agentic-pi/runtime/pi_real_session_monitor.py",
            ".agentic-pi/runtime/pi_session_trace_monitor.py",
            ".agentic-pi/runtime/run_real_pi_trace_smoke.py",
            ".agentic-pi/diagnostics/pi_real_interactive/",
            ".agentic-pi/runtime/capability_inventory.py",
            ".agentic-pi/runtime/strategy_generator.py",
            ".agentic-pi/runtime/strategy_applicability_gate.py",
            ".agentic-pi/runtime/strategy_scorer.py",
            ".agentic-pi/runtime/strategy_selector.py",
            ".agentic-pi/runtime/milestone_builder.py",
            ".agentic-pi/runtime/milestone_tracker.py",
            ".agentic-pi/runtime/local_step_planner.py",
            ".agentic-pi/runtime/step_compiler.py",
            ".agentic-pi/runtime/strategy_proof_runner.py",
            ".agentic-pi/runtime/milestone_proof_runner.py",
            ".agentic-pi/runtime/checkpoint_writer.py",
            ".agentic-pi/runtime/plan_monitor.py",
            ".agentic-pi/runtime/drift_detector.py",
            ".agentic-pi/runtime/replan_controller.py",
            ".agentic-pi/runtime/drift_proof_runner.py",
            ".agentic-pi/runtime/experience_extractor.py",
            ".agentic-pi/runtime/learning_record_writer.py",
            ".agentic-pi/runtime/strategy_memory.py",
            ".agentic-pi/runtime/experience_retriever.py",
            ".agentic-pi/runtime/pi_cli.py",
            ".agentic-pi/evaluation/trajectory_metrics.py",
            ".agentic-pi/evaluation/tool_use_audit.py",
            ".agentic-pi/evaluation/session_trace_scorer.py",
            ".agentic-pi/runtime/policy_engine.py",
            ".agentic-pi/runtime/verifier_provenance.py",
            ".agentic-pi/validators/certify_run.py",
            ".agentic-pi/validators/smell_scanner.py",
            ".agentic-pi/validators/strength_scorer.py",
            ".agentic-pi/validators/validate_delta_plan.py",
            ".agentic-pi/runtime/audit_run.py",
            ".agentic-pi/runtime/replay_run.py",
            ".agentic-pi/runtime/rollback_run.py",
            ".agentic-pi/domain_packs/",
            ".agentic-pi/proof_matrix/proof_matrix.json",
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
        self.assertIn("strict internal Pi tool-call audit for arbitrary live Pi chain smoke", doc)
        self.assertIn("additional live real Pi weak/failing transcript captures beyond fixtures", doc)
        self.assertIn("live real Pi trace captures for every status class", doc)
        self.assertIn("semantic quality of milestones", doc)
        self.assertIn("automatic repair application", doc)
        self.assertIn("deterministic trajectory evaluation", doc)
        self.assertIn("domain pack quality", doc)
        self.assertNotIn("Pi can safely solve arbitrary raw goals autonomously.", doc)


if __name__ == "__main__":
    unittest.main()
