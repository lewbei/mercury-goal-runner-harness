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
        self.assertIn("python .agentic-pi\\validators\\certify_run.py", chain)
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

    def test_pi_bash_allowlist_doc_locks_current_safety_boundary(self):
        doc = read(ROOT / "docs" / "PI_BASH_ALLOWLIST.md")

        self.assertIn("documentation-only for now", doc)
        self.assertIn("python .agentic-pi\\validators\\certify_run.py .agentic-runs\\<run_id>", doc)
        self.assertIn(".agentic-runs/pi_smoke_*", doc)
        self.assertIn("manual edit of final_status.md", doc)
        self.assertIn("manual edit of certification.json", doc)
        self.assertIn("manual edit of policy_decision.json", doc)
        self.assertIn("git reset", doc)
        self.assertIn("git clean", doc)
        self.assertIn("git push", doc)


if __name__ == "__main__":
    unittest.main()
