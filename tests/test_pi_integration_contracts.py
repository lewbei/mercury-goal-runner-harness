import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / ".pi" / "agents"
CHAINS_DIR = ROOT / ".pi" / "chains"

NEW_AGENT_FILES = [
    "goal-orchestrator.md",
    "verifier-generator.md",
    "verifier-reviewer.md",
]

FORBIDDEN_TOOLS = {"write", "edit", "apply_patch"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def front_matter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    return parts[1]


def front_matter_tools(text: str) -> set:
    header = front_matter(text)
    match = re.search(r"^tools:\s*(.+)$", header, flags=re.MULTILINE)
    if not match:
        return set()
    return {item.strip() for item in match.group(1).split(",") if item.strip()}


class PiIntegrationContractTests(unittest.TestCase):
    def test_new_pi_agent_files_exist_and_are_discoverable(self):
        for filename in NEW_AGENT_FILES:
            with self.subTest(filename=filename):
                path = AGENTS_DIR / filename
                self.assertTrue(path.is_file(), filename)
                text = read(path)
                self.assertIn("name:", front_matter(text))
                self.assertIn("description:", front_matter(text))

    def test_new_pi_agents_have_narrow_permissions(self):
        for filename in NEW_AGENT_FILES:
            with self.subTest(filename=filename):
                text = read(AGENTS_DIR / filename)
                tools = front_matter_tools(text)

                self.assertTrue(tools, filename)
                self.assertFalse(tools & FORBIDDEN_TOOLS, tools)
                self.assertLessEqual(tools, {"read", "ls", "bash"})

    def test_new_pi_agents_cannot_certify_done(self):
        for filename in NEW_AGENT_FILES:
            with self.subTest(filename=filename):
                text = read(AGENTS_DIR / filename)

                self.assertIn("certify DONE", text)
                self.assertIn("must not", text)
                self.assertIn("Final status comes only from", text)
                self.assertIn("certify_run.py", text)

    def test_goal_runner_chain_routes_final_status_to_certifier(self):
        chain = read(CHAINS_DIR / "goal-runner.chain.md")

        self.assertIn("No Pi agent may certify DONE.", chain)
        self.assertIn("certify_run.py + policy_engine.py decide final status", chain)
        self.assertIn("python .agentic-pi/validators/certify_run.py", chain)
        self.assertIn("The chain must not produce its own final status.", chain)
        self.assertIn("policy_decision.json", chain)

    def test_v05_doc_locks_integration_boundary(self):
        doc = read(ROOT / "docs" / "V0_5_PI_INTEGRATION.md")

        self.assertIn("Pi orchestration contract", doc)
        self.assertIn("deterministic certifier/policy engine as final authority", doc)
        self.assertIn("does not add", doc.lower())
        self.assertIn("memory behavior", doc)
        self.assertIn("new PlanGraph features", doc)
        self.assertIn("agent-issued final status", doc)

    def test_runtime_smoke_doc_records_local_evidence_boundary(self):
        doc = read(ROOT / "docs" / "V0_5_RUNTIME_SMOKES.md")

        self.assertIn("v0.5.1 = verifier-reviewer read-only smoke PASS", doc)
        self.assertIn("v0.5.2 = goal-orchestrator read-only status-report smoke PASS", doc)
        self.assertIn("v0.5.3 = goal-orchestrator disposable certifier-invocation smoke PASS", doc)
        self.assertIn("local runtime evidence, not automated CI evidence", doc)
        self.assertIn("full goal-runner.chain.md runtime", doc)
        self.assertIn("Short strict one-action prompts work better", doc)
        self.assertIn("goal-orchestrator bash remains risk", doc)

    def test_v057_doc_records_controlled_mini_chain_boundary(self):
        doc = read(ROOT / "docs" / "V0_5_7_CONTROLLED_MINI_CHAIN_SMOKE.md")

        self.assertIn("FUNCTIONAL PASS WITH PI EXIT CAVEAT", doc)
        self.assertIn(".agentic-runs/pi_smoke_mini_chain_p2_strong", doc)
        self.assertIn("verifier-reviewer read the disposable run artifacts with read-only tools", doc)
        self.assertIn("goal-orchestrator invoked the deterministic certifier through the Agent tool", doc)
        self.assertIn("final_status.md status: CERTIFIED_DONE", doc)
        self.assertIn("certification.json status: CERTIFIED_DONE", doc)
        self.assertIn("policy_decision.json status: CERTIFIED_DONE", doc)
        self.assertIn("stale extension context", doc)
        self.assertIn("full goal-runner.chain.md runtime", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v058_doc_records_pi_clean_exit_isolation_boundary(self):
        doc = read(ROOT / "docs" / "V0_5_8_PI_CLEAN_EXIT_SMOKE.md")

        self.assertIn("CLEAN EXIT PASS WITH COMMAND-COUNT CAVEAT", doc)
        self.assertIn("PI_CODING_AGENT_DIR=.agentic-runs/pi_smoke_clean_exit_config", doc)
        self.assertIn("packages=[npm:pi-subagents]", doc)
        self.assertIn("Pi process exit: 1", doc)
        self.assertIn("Pi process exit: 0", doc)
        self.assertIn("@tmustier/pi-agent-teams stale extension context", doc)
        self.assertIn("goal-orchestrator ran certify_run.py twice", doc)
        self.assertIn("strict one-command orchestration", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v059_doc_records_command_discipline_audit_boundary(self):
        doc = read(ROOT / "docs" / "V0_5_9_PI_COMMAND_DISCIPLINE_GATE.md")

        self.assertIn("COMMAND DISCIPLINE AUDIT IMPLEMENTED", doc)
        self.assertIn("python .agentic-pi/validators/certify_run.py .agentic-runs/<run_id>", doc)
        self.assertIn("positive_one_bash -> PASS", doc)
        self.assertIn("reject_duplicate_certifier_command -> FAIL", doc)
        self.assertIn("reject_manual_status_write -> FAIL", doc)
        self.assertIn("reject_nested_pi_duplicate_session -> FAIL", doc)
        self.assertIn("reject_non_disposable_deletion -> FAIL", doc)
        self.assertIn("reject_missing_status_inferred -> FAIL", doc)
        self.assertIn("full Pi goal-runner chain is safely autonomous", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v0510_doc_records_disposable_smoke_setup_boundary(self):
        doc = read(ROOT / "docs" / "V0_5_10_DISPOSABLE_SMOKE_HARNESS.md")

        self.assertIn("DISPOSABLE SMOKE SETUP IMPLEMENTED", doc)
        self.assertIn(".agentic-pi/runtime/setup_pi_smoke.py", doc)
        self.assertIn(".agentic-runs/pi_smoke_*", doc)
        self.assertIn("rewrites run_id only inside the copied disposable folder", doc)
        self.assertIn("hashes the source before and after", doc)
        self.assertIn("Pi should certify/report only", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v0511_doc_records_negative_status_safety_boundary(self):
        doc = read(ROOT / "docs" / "V0_5_11_NEGATIVE_STATUS_SAFETY_SMOKE.md")

        self.assertIn("NEGATIVE-STATUS SAFETY AUDIT IMPLEMENTED", doc)
        self.assertIn("NOT_DONE stays NOT_DONE", doc)
        self.assertIn("PROVISIONAL_DONE stays PROVISIONAL_DONE", doc)
        self.assertIn("DONE_FAIL stays DONE_FAIL", doc)
        self.assertIn("reject_repair_after_not_done -> FAIL", doc)
        self.assertIn("reject_provisional_upgrade -> FAIL", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v06_doc_records_local_host_integration_boundary(self):
        doc = read(ROOT / "docs" / "V0_6_LOCAL_CODING_AGENT_HOST_INTEGRATION.md")

        self.assertIn("LOCAL HOST INTEGRATION IMPLEMENTED", doc)
        self.assertIn(".agentic-pi/runtime/host_task_runner.py", doc)
        self.assertIn("sys.executable", doc)
        self.assertIn("reject_double_certifier_command -> FAIL", doc)
        self.assertIn("reject_source_run_mutation -> FAIL", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v07_doc_records_branch_generation_boundary(self):
        doc = read(ROOT / "docs" / "V0_7_BRANCH_GENERATION.md")

        self.assertIn("BRANCH CONTRACT AND GENERATION IMPLEMENTED", doc)
        self.assertIn("Branches are candidate execution plans", doc)
        self.assertIn("Branches are not verifier evidence", doc)
        self.assertIn(".agentic-pi/runtime/branch_generator.py", doc)
        self.assertIn("branch claiming forbidden final authority", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v08_doc_records_evidence_branch_selection_boundary(self):
        doc = read(ROOT / "docs" / "V0_8_EVIDENCE_BRANCH_SELECTION.md")

        self.assertIn("EVIDENCE-SEEKING BRANCH SELECTION IMPLEMENTED", doc)
        self.assertIn("path to P2/P3 certifying verifier evidence", doc)
        self.assertIn(".agentic-pi/runtime/evidence_branch_selector.py", doc)
        self.assertIn("NEED_USER_VERIFIER", doc)
        self.assertIn("final_status.md", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v09_doc_records_replay_rollback_audit_boundary(self):
        doc = read(ROOT / "docs" / "V0_9_REPLAY_ROLLBACK_AUDIT.md")

        self.assertIn("REPLAY ROLLBACK AUDIT IMPLEMENTED", doc)
        self.assertIn("Replay is read-only", doc)
        self.assertIn("Rollback is dry-run by default", doc)
        self.assertIn("Audit can block certification", doc)
        self.assertIn("Audit cannot certify DONE by itself", doc)
        self.assertIn("run_manifest.json", doc)
        self.assertIn("backup_manifest.schema.json", doc)
        self.assertIn("Replay checks `run_manifest.json`", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v10_docs_record_practical_package_freeze(self):
        freeze = read(ROOT / "docs" / "V1_0_PRACTICAL_PACKAGE_FREEZE.md")
        examples = read(ROOT / "docs" / "V1_0_EXAMPLES.md")

        self.assertIn("PRACTICAL PACKAGE FREEZE IMPLEMENTED", freeze)
        self.assertIn("goal-init", freeze)
        self.assertIn("goal-replay", freeze)
        self.assertIn("goal-audit", freeze)
        self.assertIn("goal-rollback", freeze)
        self.assertIn("Support tools cannot certify DONE by themselves", freeze)
        self.assertIn("Final status still comes only from", examples)
        self.assertIn("False-PASS Rejection", examples)

    def test_v11_doc_records_raw_goal_chain_boundary(self):
        doc = read(ROOT / "docs" / "V1_1_RAW_GOAL_CHAIN_PROOF.md")

        self.assertIn("RAW GOAL CHAIN PROOF IMPLEMENTED", doc)
        self.assertIn("raw goal -> goal_contract.json -> full harness run -> certifier status", doc)
        self.assertIn("full autonomous Pi goal-runner.chain.md execution", doc)
        self.assertIn("Pi can invoke a deterministic raw-goal compiler", doc)

    def test_v12_doc_records_planning_proof_boundary(self):
        doc = read(ROOT / "docs" / "V1_2_PLANNING_PROOF_HARDENING.md")

        self.assertIn("PLANNING PROOF HARDENING IMPLEMENTED", doc)
        self.assertIn("-> branch candidates", doc)
        self.assertIn("-> selected branch", doc)
        self.assertIn("-> merged_plan.json", doc)
        self.assertIn("The selected branch does not certify DONE", doc)
        self.assertIn("does not prove", doc)

    def test_v13_doc_records_strategy_planner_boundary(self):
        doc = read(ROOT / "docs" / "V1_3_STRATEGY_PLANNER.md")
        roadmap = read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md")

        self.assertIn("STRATEGY PLANNER IMPLEMENTED", doc)
        self.assertIn("task type", doc)
        self.assertIn("capability inventory", doc)
        self.assertIn("strategy candidates", doc)
        self.assertIn("applicability gate", doc)
        self.assertIn("selected strategy", doc)
        self.assertIn("Certifier writes final status", doc)
        self.assertIn("does not prove", doc.lower())
        self.assertIn("v1.4 Milestone Planning", roadmap)
        self.assertIn("v1.9 Strategy Search / Workflow Optimization", roadmap)
        self.assertIn("v2.0 Integrated Harness Proof Package", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)

    def test_v14_doc_records_milestone_planning_boundary(self):
        doc = read(ROOT / "docs" / "V1_4_MILESTONE_PLANNING.md")
        roadmap = read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md")

        self.assertIn("MILESTONE PLANNING IMPLEMENTED", doc)
        self.assertIn("milestone_plan.json", doc)
        self.assertIn("milestone_status.json", doc)
        self.assertIn("local_step_plan.json", doc)
        self.assertIn("goal-milestone-proof", doc)
        self.assertIn("Certifier writes final status", doc)
        self.assertIn("does not prove", doc.lower())
        self.assertIn("v1.4 Milestone Planning", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)

    def test_v15_doc_records_drift_replanning_boundary(self):
        doc = read(ROOT / "docs" / "V1_5_DRIFT_AWARE_REPLANNING.md")
        roadmap = read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md")

        self.assertIn("DRIFT-AWARE REPLANNING IMPLEMENTED", doc)
        self.assertIn("checkpoints/", doc)
        self.assertIn("plan_monitor_report.json", doc)
        self.assertIn("drift_report.json", doc)
        self.assertIn("delta_plan.json", doc)
        self.assertIn("goal-drift-proof", doc)
        self.assertIn("Certifier writes final status", doc)
        self.assertIn("does not prove", doc.lower())
        self.assertIn("v1.5 Drift-Aware Replanning", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)

    def test_v16_doc_records_trajectory_evaluation_boundary(self):
        doc = read(ROOT / "docs" / "V1_6_TRAJECTORY_LEVEL_EVALUATION.md")
        roadmap = read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md")

        self.assertIn("TRAJECTORY-LEVEL EVALUATION IMPLEMENTED", doc)
        self.assertIn("tool_selection_correct", doc)
        self.assertIn("tool_argument_correct", doc)
        self.assertIn("tool_order_correct", doc)
        self.assertIn("duplicate_certifier_call -> FAIL", doc)
        self.assertIn("wrong_command_order -> FAIL", doc)
        self.assertIn("cannot certify DONE", doc)
        self.assertIn("v1.6 Trajectory-Level Evaluation", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)

    def test_v17_doc_records_experience_memory_boundary(self):
        doc = read(ROOT / "docs" / "V1_7_EXPERIENCE_MEMORY.md")
        roadmap = read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md")

        self.assertIn("EXPERIENCE MEMORY IMPLEMENTED", doc)
        self.assertIn("experience_extract.json", doc)
        self.assertIn("learning record", doc)
        self.assertIn("retrieved_experience.json", doc)
        self.assertIn("memory can suggest", doc)
        self.assertIn("memory cannot certify DONE", doc)
        self.assertIn("memory cannot bypass the applicability gate", doc)
        self.assertIn("v1.7 Experience Memory", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)

    def test_v18_doc_records_domain_pack_boundary(self):
        doc = read(ROOT / "docs" / "V1_8_DOMAIN_PACKS.md")
        roadmap = read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md")

        self.assertIn("DOMAIN PACKS IMPLEMENTED", doc)
        self.assertIn("domain_pack_selection.json", doc)
        self.assertIn("coding", doc)
        self.assertIn("research", doc)
        self.assertIn("benchmark", doc)
        self.assertIn("domain packs can suggest", doc)
        self.assertIn("domain packs cannot certify DONE", doc)
        self.assertIn("unknown goals do not guess unsafe packs", doc)
        self.assertIn("v1.8 Domain Packs", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)

    def test_v19_doc_records_workflow_search_boundary(self):
        doc = read(ROOT / "docs" / "V1_9_STRATEGY_SEARCH.md")
        roadmap = read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md")

        self.assertIn("STRATEGY SEARCH IMPLEMENTED", doc)
        self.assertIn("workflow_candidates.json", doc)
        self.assertIn("selected_workflow.json", doc)
        self.assertIn("workflow_search_trace.json", doc)
        self.assertIn("workflow search cannot bypass certifier", doc)
        self.assertIn("workflow search cannot certify DONE", doc)
        self.assertIn("high false CERTIFIED_DONE risk", doc)
        self.assertIn("v1.9 Strategy Search / Workflow Optimization", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)

    def test_v20_doc_records_integrated_proof_package_boundary(self):
        doc = read(ROOT / "docs" / "V2_0_INTEGRATED_HARNESS_PROOF_PACKAGE.md")
        examples = read(ROOT / "docs" / "V2_0_EXAMPLES.md")
        roadmap = read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md")

        self.assertIn("INTEGRATED HARNESS PROOF PACKAGE IMPLEMENTED", doc)
        self.assertIn("proof_matrix.json", doc)
        self.assertIn("run_proof_matrix.py", doc)
        self.assertIn("proof_matrix_result.json", doc)
        self.assertIn("can_certify_done = false", doc)
        self.assertIn("full Pi goal-runner chain", doc)
        self.assertIn("DONE_PASS", examples)
        self.assertIn("PROVISIONAL_DONE", examples)
        self.assertIn("CERTIFIED_DONE", examples)
        self.assertIn("NOT_DONE", examples)
        self.assertIn("v2.0 Integrated Harness Proof Package", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)

    def test_v21_doc_records_controlled_pi_chain_boundary(self):
        doc = read(ROOT / "docs" / "V2_1_CONTROLLED_PI_CHAIN_RUNTIME_PROOF.md")
        roadmap = read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md")

        self.assertIn("CONTROLLED PI CHAIN RUNTIME PROOF IMPLEMENTED", doc)
        self.assertIn("run_pi_chain_smoke.py", doc)
        self.assertIn("verifier-generator -> verifier-reviewer -> goal-orchestrator", doc)
        self.assertIn("final_status_authority = certifier_only", doc)
        self.assertIn("can_certify_done = false", doc)
        self.assertIn("full Pi goal-runner chain is autonomously verified", doc)
        self.assertIn("v2.1 Controlled Pi Chain Runtime Proof", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)

    def test_v22_doc_records_direct_pi_mercury_boundary(self):
        doc = read(ROOT / "docs" / "V2_2_DIRECT_PI_MERCURY_BEHAVIOR_AUDIT.md")

        self.assertIn("DIRECT PI / MERCURY BEHAVIOR AUDIT IMPLEMENTED", doc)
        self.assertIn("Pi is the CLI/harness surface", doc)
        self.assertIn("Mercury is the LLM behavior inside Pi", doc)
        self.assertIn("verifier evidence before certifier invocation", doc)
        self.assertIn("status artifacts after certifier invocation", doc)
        self.assertIn("can_certify_done = false", doc)
        self.assertIn("does not prove arbitrary live Pi autonomy", doc)
        self.assertIn("v2.2 Direct Pi/Mercury Behavior Audit", read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md"))

    def test_v23_doc_records_real_pi_interactive_boundary(self):
        doc = read(ROOT / "docs" / "V2_3_REAL_PI_INTERACTIVE_SMOKE.md")
        roadmap = read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md")

        self.assertIn("REAL PI INTERACTIVE SMOKE EVIDENCE RECORDED", doc)
        self.assertIn("pi = the real external Pi agent launched from cmd", doc)
        self.assertIn("Mercury = the LLM behavior inside Pi", doc)
        self.assertIn("local smoke evidence, not automated CI evidence", doc)
        self.assertIn("final_status_authority: certifier_only", doc)
        self.assertIn("can_certify_done: false", doc)
        self.assertIn("Full autonomous Pi goal-runner runtime is proven", doc)
        self.assertIn("Both unsafe claims remain false", doc)
        self.assertIn("v2.3 Real Pi Interactive Smoke Evidence", roadmap)

    def test_v24_doc_records_real_pi_run_monitor_boundary(self):
        doc = read(ROOT / "docs" / "V2_4_REAL_PI_RUN_MONITOR.md")
        roadmap = read(ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md")

        self.assertIn("REAL PI RUN MONITOR IMPLEMENTED", doc)
        self.assertIn("actual Pi session/tool trajectory", doc)
        self.assertIn("exactly one allowed bash command", doc)
        self.assertIn("required result artifact read after bash command", doc)
        self.assertIn("final_status_authority = certifier_only", doc)
        self.assertIn("can_certify_done = false", doc)
        self.assertIn("It does not prove arbitrary Pi autonomy", doc)
        self.assertIn("v2.4 Real Pi Run Monitor", roadmap)

    def test_v30_doc_records_real_pi_behavior_evaluation_boundary(self):
        doc = read(ROOT / "docs" / "V3_0_REAL_PI_BEHAVIOR_EVALUATION.md")

        self.assertIn("REAL PI BEHAVIOR EVALUATION IMPLEMENTED", doc)
        self.assertIn("unsafe_attempt_caught", doc)
        self.assertIn("unsafe_attempt_missed", doc)
        self.assertIn("safe_refusal", doc)
        self.assertIn("inconclusive", doc)
        self.assertIn("deterministic monitor correctness", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v31_doc_records_real_pi_prompt_coverage_boundary(self):
        doc = read(ROOT / "docs" / "V3_1_REAL_PI_PROMPT_COVERAGE.md")

        self.assertIn("REAL PI PROMPT COVERAGE EVALUATION IMPLEMENTED", doc)
        self.assertIn("status_forgery", doc)
        self.assertIn("memory_authority", doc)
        self.assertIn("unsafe_attempt_missed_count must be 0", doc)
        self.assertIn("safe command-shaped probes", doc)
        self.assertIn("v3.1 does not prove", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v32_doc_records_runtime_enforcement_boundary(self):
        doc = read(ROOT / "docs" / "V3_2_RUNTIME_ENFORCEMENT_PROOF.md")

        self.assertIn("RUNTIME ENFORCEMENT PROOF IMPLEMENTED", doc)
        self.assertIn("command_gateway.py", doc)
        self.assertIn("protected_file_guard.py", doc)
        self.assertIn("MONITOR_FAIL", doc)
        self.assertIn("does not prove arbitrary prompts", doc)
        self.assertIn("Final status still comes only from", doc)

    def test_v34_doc_records_rpg_test_aggregation_boundary(self):
        doc = read(ROOT / "docs" / "V3_4_RPG_TEST_AGGREGATION.md")

        self.assertIn("RPG TEST AGGREGATION IMPLEMENTED", doc)
        self.assertIn("rpg_test_aggregator.py", doc)
        self.assertIn("false_certified_done_rate_bps", doc)
        self.assertIn("monitor_miss_rate_bps", doc)
        self.assertIn("confidence_intervals_bps", doc)
        self.assertIn("The aggregator cannot certify DONE", doc)

    def test_v350_doc_records_authority_artifact_boundary(self):
        doc = read(ROOT / "docs" / "V3_5_0_AUTHORITY_ARTIFACT_PREREQUISITE.md")

        self.assertIn("AUTHORITY ARTIFACT PREREQUISITE IMPLEMENTED", doc)
        self.assertIn("final_status.json = machine-readable authority", doc)
        self.assertIn("final_status.md   = derived human-readable view", doc)
        self.assertIn("Markdown cannot upgrade JSON authority", doc)
        self.assertIn("Do not claim that", doc)

    def test_framework_doc_is_linked_from_status_docs(self):
        readme = read(ROOT / "README.md")
        status = read(ROOT / "PROJECT_STATUS.md")

        self.assertIn("FRAMEWORK.md", readme)
        self.assertIn("FRAMEWORK.md", status)
        self.assertIn("V1_2_PLANNING_PROOF_HARDENING.md", readme)
        self.assertIn("V1_2_PLANNING_PROOF_HARDENING.md", status)
        self.assertIn("V1_3_STRATEGY_PLANNER.md", readme)
        self.assertIn("V1_3_STRATEGY_PLANNER.md", status)
        self.assertIn("V1_4_MILESTONE_PLANNING.md", readme)
        self.assertIn("V1_4_MILESTONE_PLANNING.md", status)
        self.assertIn("V1_5_DRIFT_AWARE_REPLANNING.md", readme)
        self.assertIn("V1_5_DRIFT_AWARE_REPLANNING.md", status)
        self.assertIn("V1_6_TRAJECTORY_LEVEL_EVALUATION.md", readme)
        self.assertIn("V1_6_TRAJECTORY_LEVEL_EVALUATION.md", status)
        self.assertIn("V1_7_EXPERIENCE_MEMORY.md", readme)
        self.assertIn("V1_7_EXPERIENCE_MEMORY.md", status)
        self.assertIn("V1_8_DOMAIN_PACKS.md", readme)
        self.assertIn("V1_8_DOMAIN_PACKS.md", status)
        self.assertIn("V1_9_STRATEGY_SEARCH.md", readme)
        self.assertIn("V1_9_STRATEGY_SEARCH.md", status)
        self.assertIn("V2_0_INTEGRATED_HARNESS_PROOF_PACKAGE.md", readme)
        self.assertIn("V2_0_INTEGRATED_HARNESS_PROOF_PACKAGE.md", status)
        self.assertIn("V2_0_EXAMPLES.md", readme)
        self.assertIn("V2_0_EXAMPLES.md", status)
        self.assertIn("V2_1_CONTROLLED_PI_CHAIN_RUNTIME_PROOF.md", readme)
        self.assertIn("V2_1_CONTROLLED_PI_CHAIN_RUNTIME_PROOF.md", status)
        self.assertIn("V2_2_DIRECT_PI_MERCURY_BEHAVIOR_AUDIT.md", readme)
        self.assertIn("V2_2_DIRECT_PI_MERCURY_BEHAVIOR_AUDIT.md", status)
        self.assertIn("V2_3_REAL_PI_INTERACTIVE_SMOKE.md", readme)
        self.assertIn("V2_3_REAL_PI_INTERACTIVE_SMOKE.md", status)
        self.assertIn("V2_4_REAL_PI_RUN_MONITOR.md", readme)
        self.assertIn("V2_4_REAL_PI_RUN_MONITOR.md", status)
        self.assertIn("V3_0_REAL_PI_BEHAVIOR_EVALUATION.md", readme)
        self.assertIn("V3_0_REAL_PI_BEHAVIOR_EVALUATION.md", status)
        self.assertIn("V3_1_REAL_PI_PROMPT_COVERAGE.md", readme)
        self.assertIn("V3_1_REAL_PI_PROMPT_COVERAGE.md", status)
        self.assertIn("V3_2_RUNTIME_ENFORCEMENT_PROOF.md", readme)
        self.assertIn("RPG_HARNESS_TEST_FORM.md", readme)
        self.assertIn("V3_4_RPG_TEST_AGGREGATION.md", readme)
        self.assertIn("V3_5_0_AUTHORITY_ARTIFACT_PREREQUISITE.md", readme)
        self.assertIn("V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md", readme)
        self.assertIn("V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md", status)

    def test_pi_prompt_contract_doc_locks_safe_prompt_patterns(self):
        doc = read(ROOT / "docs" / "PI_PROMPT_CONTRACTS.md")

        self.assertIn("One prompt = one action.", doc)
        self.assertIn("Do not mix", doc)
        self.assertIn("copy", doc)
        self.assertIn("repair", doc)
        self.assertIn("certify", doc)
        self.assertIn("Final status comes only from certify_run.py", doc)
        self.assertIn("Do not certify DONE yourself", doc)
        self.assertIn("MISSING", doc)
        self.assertIn("python .agentic-pi/validators/certify_run.py .agentic-runs/<run_id>", doc)
        self.assertIn("Backslash-to-forward-slash retry", doc)

    def test_pi_bash_allowlist_doc_locks_current_safety_boundary(self):
        doc = read(ROOT / "docs" / "PI_BASH_ALLOWLIST.md")

        self.assertIn("documentation-only for now", doc)
        self.assertIn("python .agentic-pi/validators/certify_run.py .agentic-runs/<run_id>", doc)
        self.assertIn("python .agentic-pi\\validators\\certify_run.py .agentic-runs\\<run_id>", doc)
        self.assertIn(".agentic-runs/pi_smoke_*", doc)
        self.assertIn("manual edit of final_status.md", doc)
        self.assertIn("manual edit of certification.json", doc)
        self.assertIn("manual edit of policy_decision.json", doc)
        self.assertIn("git reset", doc)
        self.assertIn("git clean", doc)
        self.assertIn("git push", doc)
        self.assertIn("path-normalization retry", doc)


if __name__ == "__main__":
    unittest.main()
