import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepoStructureCleanupTests(unittest.TestCase):
    def test_agentic_pi_ownership_docs_exist(self):
        for relative_path in [
            ".agentic-pi/README.md",
            ".agentic-pi/runtime/README.md",
            ".agentic-pi/diagnostics/README.md",
        ]:
            with self.subTest(path=relative_path):
                path = ROOT / relative_path
                self.assertTrue(path.is_file(), relative_path)
                text = path.read_text(encoding="utf-8")
                self.assertIn("certify done", text.lower())
                self.assertIn("Final status", text)

    def test_agentic_autonomy_probe_prompt_preserves_authority_boundary(self):
        prompt = (ROOT / ".agentic-pi" / "prompts" / "agentic_autonomy_probe.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Who is allowed to certify DONE?", prompt)
        self.assertIn("multi-step", prompt)
        self.assertIn("repair loop", prompt)
        self.assertIn("memory only as advisory", prompt)
        self.assertIn("do not certify DONE yourself", prompt)
        self.assertIn("Final status comes only from certify_run.py and policy_engine.py", prompt)

    def test_v27_plan_keeps_unbounded_bash_as_probe_not_safety_claim(self):
        doc = (ROOT / "docs" / "V2_7_AGENTIC_AUTONOMY_PROOF_PLAN.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("AGENTIC AUTONOMY PROBE IMPLEMENTED", doc)
        self.assertIn("multi-step autonomous planning", doc)
        self.assertIn("repair loop", doc)
        self.assertIn("memory", doc)
        self.assertIn("arbitrary goal-runner.chain.md", doc)
        self.assertIn("unbounded bash", doc)
        self.assertIn("we should not try to prove", doc.lower())
        self.assertIn("unbounded bash is safe", doc)
        self.assertIn("Final status still comes only from certify_run.py and policy_engine.py", doc)

    def test_workspace_index_points_to_current_and_next_structure(self):
        index = (ROOT / "workspace_index.md").read_text(encoding="utf-8")

        self.assertIn("v2.9 Live Negative Prompt Capture", index)
        self.assertIn("arbitrary-goal chain probing", index)
        self.assertIn("agentic autonomy probe boundary", index)
        self.assertIn("agentic negative-probe hardening boundary", index)
        self.assertIn("negative prompt capture boundary", index)
        self.assertIn(".agentic-pi/README.md", index)


if __name__ == "__main__":
    unittest.main()
