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


if __name__ == "__main__":
    unittest.main()
