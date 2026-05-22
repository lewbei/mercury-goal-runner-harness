import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_DOC = ROOT / "docs" / "FRAMEWORK.md"


def read_framework_doc() -> str:
    return FRAMEWORK_DOC.read_text(encoding="utf-8")


class FrameworkDocTests(unittest.TestCase):
    def test_framework_doc_exists_and_locks_core_question(self):
        doc = read_framework_doc()

        self.assertIn("Who is allowed to certify DONE?", doc)
        self.assertIn("Agents do work.", doc)
        self.assertIn("Policy engine judges the evidence.", doc)
        self.assertIn("Certifier writes the final status.", doc)
        self.assertIn("Pi only reports what the certifier wrote.", doc)

    def test_framework_doc_records_current_state(self):
        doc = read_framework_doc()

        self.assertIn("v3.7 = MemPalace + ACE memory governance", doc)
        self.assertIn("Real Pi Agentic Autonomy Probe Layer", doc)
        self.assertIn("Agentic Negative-Probe Hardening Layer", doc)
        self.assertIn("Live Negative Prompt Capture Layer", doc)
        self.assertIn("Real Pi Behavior Evaluation Layer", doc)
        self.assertIn("Real Pi Prompt Coverage Evaluation Layer", doc)
        self.assertIn("Runtime Enforcement Proof Layer", doc)
        self.assertIn("RPG Harness Test Record Layer", doc)
        self.assertIn("RPG Test Aggregation Layer", doc)
        self.assertIn("raw_simple_historical_compatibility -> DONE_PASS", doc)
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
        self.assertIn("negative prompt -> Pi/Mercury trace -> agentic_autonomy_monitor.py -> expected FAIL", doc)
        self.assertIn("captured negative prompt behavior -> run_real_pi_behavior_evaluation.py -> caught / missed / safe_refusal / inconclusive", doc)
        self.assertIn("captured prompt matrix -> run_real_pi_behavior_matrix.py -> caught / missed / safe_refusal / inconclusive by category/trial", doc)
        self.assertIn("Pi/Mercury-shaped command -> command_gateway.py -> protected_file_guard.py", doc)
        self.assertIn("Pi/Mercury trace -> RPG test record -> regression decision -> deterministic gates", doc)
        self.assertIn("RPG test records -> rpg_test_aggregator.py -> false-certified / monitor-miss / false-block metrics", doc)
        self.assertIn("policy_decision.json -> certification.json -> final_status.json -> final_status.md", doc)
        self.assertIn("trace/logs/artifacts/verifier evidence/policy -> evidence_index.json -> evidence_freeze.json", doc)
        self.assertIn("current run observation -> memory/*.jsonl -> advisory repair context only", doc)
        self.assertIn("candidate lesson -> quarantine memory -> not retrievable by future runs", doc)
        self.assertIn("MemPalace durable card -> context_pack.json -> ACE reflection -> curator delta -> memory_write_gate.py", doc)

    def test_framework_doc_uses_actual_current_paths(self):
        doc = read_framework_doc()

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
            ".agentic-pi/runtime/run_live_negative_prompt_capture.py",
            ".agentic-pi/runtime/run_real_pi_behavior_evaluation.py",
            ".agentic-pi/runtime/run_real_pi_behavior_matrix.py",
            ".agentic-pi/runtime/command_gateway.py",
            ".agentic-pi/runtime/protected_file_guard.py",
            ".agentic-pi/runtime/run_enforced_pi_smoke.py",
            ".agentic-pi/runtime/rpg_test_aggregator.py",
            ".agentic-pi/runtime/final_status_renderer.py",
            ".agentic-pi/runtime/evidence_indexer.py",
            ".agentic-pi/runtime/evidence_freezer.py",
            ".agentic-pi/runtime/run_memory_clerk.py",
            ".agentic-pi/runtime/quarantine_memory_writer.py",
            ".agentic-pi/runtime/mempalace_adapter.py",
            ".agentic-pi/runtime/context_pack_builder.py",
            ".agentic-pi/runtime/ace_reflector.py",
            ".agentic-pi/runtime/ace_curator.py",
            ".agentic-pi/runtime/memory_write_gate.py",
            ".agentic-pi/schemas/rpg_test_record.schema.json",
            ".agentic-pi/schemas/rpg_test_aggregation_result.schema.json",
            ".agentic-pi/schemas/final_status.schema.json",
            ".agentic-pi/schemas/evidence_index.schema.json",
            ".agentic-pi/schemas/evidence_freeze.schema.json",
            ".agentic-pi/schemas/evidence_hash_manifest.schema.json",
            ".agentic-pi/schemas/run_journal_entry.schema.json",
            ".agentic-pi/schemas/learning_candidate.schema.json",
            ".agentic-pi/schemas/mempalace_card.schema.json",
            ".agentic-pi/schemas/context_pack.schema.json",
            ".agentic-pi/schemas/reflection_report.schema.json",
            ".agentic-pi/schemas/curator_delta.schema.json",
            ".agentic-pi/schemas/memory_write_decision.schema.json",
            ".agentic-pi/templates/rpg_test_record.template.json",
            ".agentic-pi/prompts/negative_autonomy/",
            ".agentic-pi/prompts/real_behavior_matrix/",
            ".agentic-pi/schemas/live_negative_prompt_capture_result.schema.json",
            ".agentic-pi/schemas/real_pi_behavior_evaluation_result.schema.json",
            ".agentic-pi/schemas/real_pi_behavior_matrix_result.schema.json",
            ".agentic-pi/schemas/runtime_enforcement_result.schema.json",
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
            ".agentic-pi/validators/validate_final_status.py",
            ".agentic-pi/validators/validate_evidence_index.py",
            ".agentic-pi/validators/validate_evidence_freeze.py",
            ".agentic-pi/validators/validate_run_local_memory.py",
            ".agentic-pi/validators/validate_quarantine_memory.py",
            ".agentic-pi/validators/validate_memory_card.py",
            ".agentic-pi/validators/validate_context_pack.py",
            ".agentic-pi/validators/validate_memory_write_gate.py",
            ".agentic-pi/validators/validate_memory_authority.py",
            ".agentic-pi/validators/validate_memory_contradictions.py",
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
        doc = read_framework_doc()

        self.assertIn("## Proven Behavior", doc)
        self.assertIn("## Not Proven", doc)
        self.assertIn("prepared historical-compatibility full run through Pi -> DONE_PASS", doc)
        self.assertIn("prepared provenance full run through Pi -> CERTIFIED_DONE", doc)
        self.assertIn("arbitrary raw natural-language autonomy", doc)
        self.assertIn("full goal-runner.chain.md autonomous runtime", doc)
        self.assertIn("strict internal Pi tool-call audit for arbitrary live Pi chain smoke", doc)
        self.assertIn("additional live real Pi weak/failing transcript captures beyond fixtures", doc)
        self.assertIn("live real Pi trace captures for every status class", doc)
        self.assertIn("every malicious prompt is classified", doc)
        self.assertIn("live behavior evaluation on a large adversarial prompt set", doc)
        self.assertIn("broad real Pi prompt coverage beyond the current bounded matrix", doc)
        self.assertIn("arbitrary command-gateway bypasses", doc)
        self.assertIn("statistical proof beyond recorded RPG test records", doc)
        self.assertIn("live campaign quality beyond collected RPG records", doc)
        self.assertIn("semantic quality of milestones", doc)
        self.assertIn("automatic repair application", doc)
        self.assertIn("deterministic trajectory evaluation", doc)
        self.assertIn("domain pack quality", doc)
        self.assertNotIn("Pi can safely solve arbitrary raw goals autonomously.", doc)


if __name__ == "__main__":
    unittest.main()
