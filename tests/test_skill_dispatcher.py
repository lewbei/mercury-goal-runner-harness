#!/usr/bin/env python3
"""Tests for the progressive skill dispatcher.

Tests:
- Skills accumulate correctly across the phase chain
- Deterministic phases add no new skills
- Early phases have only their own skills
- Later phases have all prior skills
- Accumulated context is well-formatted
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_dispatcher():
    import importlib.util
    path = ROOT / ".agentic-pi" / "runtime" / "skill_dispatcher.py"
    spec = importlib.util.spec_from_file_location("skill_dispatcher", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SkillAccumulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = load_dispatcher()

    def test_intake_has_only_question_contract(self):
        skills = self.d.get_accumulated_skills("INTAKE")
        self.assertIn("question-contract", skills)
        self.assertEqual(len(skills), 1, f"Expected only question-contract, got {skills}")

    def test_researching_has_question_and_research(self):
        skills = self.d.get_accumulated_skills("RESEARCHING")
        self.assertIn("question-contract", skills)
        self.assertIn("research-pack", skills)
        self.assertEqual(len(skills), 2, f"Expected 2 skills, got {skills}")

    def test_planning_has_all_prior_skills(self):
        skills = self.d.get_accumulated_skills("PLANNING")
        expected_skills = [
            "question-contract",
            "research-pack",
            "design-options",
            "structure-outline",
            "root-plan",
        ]
        for es in expected_skills:
            self.assertIn(es, skills, f"Expected {es} in PLANNING skills")
        self.assertEqual(len(skills), len(expected_skills),
                        f"Expected {len(expected_skills)} skills, got {len(skills)}: {skills}")

    def test_implementing_has_artifact_contract_and_path_grounding(self):
        skills = self.d.get_accumulated_skills("IMPLEMENTING")
        self.assertIn("artifact-contract", skills)
        self.assertIn("path-grounding", skills)
        # All prior skills should also be present
        self.assertIn("question-contract", skills)
        self.assertIn("root-plan", skills)

    def test_validating_adds_all_validator_skills(self):
        skills = self.d.get_accumulated_skills("VALIDATING")
        self.assertIn("harness-grill", skills)
        self.assertIn("harness-tdd", skills)
        self.assertIn("harness-diagnose", skills)
        # Prior skills preserved
        self.assertIn("path-grounding", skills)
        self.assertIn("validator-factory", skills)

    def test_policy_deciding_adds_no_new_skills(self):
        """Deterministic phase — no new skill added."""
        before = self.d.get_accumulated_skills("VALIDATING")
        after = self.d.get_accumulated_skills("POLICY_DECIDING")
        # POLICY_DECIDING should have the same skills as VALIDATING
        # (nothing new in EVIDENCE_INDEXING or POLICY_DECIDING)
        self.assertEqual(before, after,
                        "POLICY_DECIDING should not add new skills after VALIDATING")

    def test_certifying_has_harness_certify(self):
        skills = self.d.get_accumulated_skills("CERTIFYING")
        self.assertIn("harness-certify", skills)
        # All validating skills also present
        self.assertIn("harness-grill", skills)

    def test_memory_consolidating_has_write_memory(self):
        skills = self.d.get_accumulated_skills("MEMORY_CONSOLIDATING")
        self.assertIn("write-memory", skills)
        # All prior skills preserved
        self.assertIn("harness-certify", skills)
        self.assertIn("path-grounding", skills)
        self.assertIn("question-contract", skills)

    def test_accumulated_context_formats_correctly(self):
        context = self.d.format_accumulated_context("IMPLEMENTING")
        self.assertIn("Accumulated Skills Context", context)
        self.assertIn("Run phase: IMPLEMENTING", context)
        self.assertIn("### Skill: question-contract", context)
        self.assertIn("### Skill: root-plan", context)
        self.assertIn("### Skill: artifact-contract", context)
        self.assertIn("### Skill: path-grounding", context)

    def test_accumulated_context_includes_skill_text(self):
        context = self.d.format_accumulated_context("QUESTIONING")
        self.assertIn("Question Contract Skill", context,
                      "Context should include the skill's actual text")

    def test_new_phase_has_no_skills(self):
        skills = self.d.get_accumulated_skills("NEW")
        self.assertEqual(skills, [])

    def test_done_has_all_skills(self):
        """DONE preserves all accumulated skills from the full run."""
        skills = self.d.get_accumulated_skills("DONE")
        all_expected = [
            "question-contract",
            "research-pack",
            "design-options",
            "structure-outline",
            "root-plan",
            "artifact-contract",
            "path-grounding",
            "validator-factory",
            "harness-grill",
            "harness-tdd",
            "harness-diagnose",
            "harness-certify",
            "write-memory",
        ]
        for es in all_expected:
            self.assertIn(es, skills, f"Expected {es} in DONE skills")
        self.assertEqual(len(skills), len(all_expected),
                        f"Expected {len(all_expected)} skills, got {len(skills)}")


class SkillMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = load_dispatcher()

    def test_question_contract_metadata(self):
        meta = self.d.load_skill_metadata("question-contract")
        self.assertIn("phase", meta)
        self.assertIn("role", meta)
        self.assertEqual(meta["role"], "Questioner")

    def test_research_pack_metadata(self):
        meta = self.d.load_skill_metadata("research-pack")
        self.assertIn("phase", meta)
        self.assertEqual(meta["role"], "Researcher")

    def test_unknown_skill_returns_empty_metadata(self):
        meta = self.d.load_skill_metadata("nonexistent-skill")
        self.assertEqual(meta, {})

    def test_load_skill_text_returns_content(self):
        text = self.d.load_skill_text("question-contract")
        self.assertIn("Question Contract Skill", text)
        self.assertIn("## Purpose", text)


if __name__ == "__main__":
    unittest.main()
