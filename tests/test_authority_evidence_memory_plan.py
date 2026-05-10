import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs" / "V3_5_TO_V4_0_AUTHORITY_EVIDENCE_MEMORY_PLAN.md"


class AuthorityEvidenceMemoryPlanTests(unittest.TestCase):
    def test_reference_modules_are_ignored(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("modules/ace-main/", gitignore)
        self.assertIn("modules/mempalace-develop/", gitignore)

    def test_plan_preserves_current_version_history(self):
        doc = PLAN_PATH.read_text(encoding="utf-8")

        self.assertIn("v3.2 = Runtime Enforcement Proof", doc)
        self.assertIn("v3.3 = RPG Harness Test Record", doc)
        self.assertIn("v3.4 = RPG Test Aggregation", doc)
        self.assertIn("Do not rename or overwrite those milestones.", doc)

    def test_plan_includes_authority_and_evidence_sequence(self):
        doc = PLAN_PATH.read_text(encoding="utf-8")

        self.assertIn("v3.5.0 - Authority Artifact Prerequisite", doc)
        self.assertIn("final_status.json = machine-readable authority artifact", doc)
        self.assertIn("v3.5 - Evidence Freeze + Evidence Index", doc)
        self.assertIn("Every certifiable claim must cite frozen producer-linked evidence.", doc)
        self.assertIn("test_memory_cannot_enter_evidence_index", doc)

    def test_plan_uses_ace_and_mempalace_as_references_only(self):
        doc = PLAN_PATH.read_text(encoding="utf-8")

        self.assertIn("modules/ace-main/", doc)
        self.assertIn("modules/mempalace-develop/", doc)
        self.assertIn("Generator", doc)
        self.assertIn("Reflector", doc)
        self.assertIn("Curator", doc)
        self.assertIn("wings / rooms / closets / drawers", doc)
        self.assertIn("not vendored harness code", doc)

    def test_plan_keeps_memory_advisory(self):
        doc = PLAN_PATH.read_text(encoding="utf-8")

        self.assertIn("Memory can suggest.", doc)
        self.assertIn("Memory still cannot certify.", doc)
        self.assertIn("Memory still cannot bypass policy.", doc)
        self.assertIn("Memory still cannot replace frozen evidence.", doc)

    def test_source_of_truth_docs_reference_the_plan(self):
        for relative_path in ["README.md", "PROJECT_STATUS.md", "FRAMEWORK.md", "workspace_index.md"]:
            with self.subTest(path=relative_path):
                text = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("V3_5_TO_V4_0_AUTHORITY_EVIDENCE_MEMORY_PLAN.md", text)


if __name__ == "__main__":
    unittest.main()
