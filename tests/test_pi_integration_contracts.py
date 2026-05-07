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
