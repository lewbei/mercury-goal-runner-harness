import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / ".pi" / "agents"


class ProjectAgentFrontmatterTests(unittest.TestCase):
    def test_project_agents_do_not_use_literal_false_for_skills_or_extensions(self):
        """Literal false is parsed as a path/string by the subagent launcher."""
        agent_files = sorted(AGENTS_DIR.glob("*.md"))
        self.assertGreater(len(agent_files), 0, "expected project agent definitions")

        forbidden_lines = {"skills: false", "extensions: false"}
        violations = []
        for path in agent_files:
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.strip() in forbidden_lines:
                    violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")

        self.assertEqual([], violations)

    def test_prompt_compiler_has_fail_closed_preflight(self):
        prompt_compiler = (AGENTS_DIR / "prompt-compiler.md").read_text(encoding="utf-8")

        required_snippets = [
            "## HARD PREFLIGHT",
            "If the task is only a startup smoke test, health check, or asks for an exact reply, do not write files.",
            "BLOCKED: prompt-compiler requires an explicit run_id.",
            "BLOCKED: seeded run contract is missing.",
            ".agentic-runs/<run_id>/goal_contract.json",
            "Do not write root files such as `test.json`, `noexec.json`, or `smoke_test_output.txt`.",
        ]
        for snippet in required_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, prompt_compiler)


if __name__ == "__main__":
    unittest.main()
