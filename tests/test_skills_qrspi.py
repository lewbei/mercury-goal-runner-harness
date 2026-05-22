#!/usr/bin/env python3
"""Unittest tests for RPG-Harness v5 Phase 9: QRSPI Skill Integration.

Tests cover:
- All 13 skill directories and SKILL.md files exist
- Each skill references the correct phase, role, and artifact
- No skill claims certify authority
- Skill content matches phase registry expectations
- Authority boundaries are consistently stated
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def default_skills_dir() -> Path:
    for candidate in (
        ROOT / ".pi" / "skills",
        ROOT / "skills",
        ROOT / ".agentic-pi" / "skills",
    ):
        if candidate.is_dir():
            return candidate
    return ROOT / ".pi" / "skills"


SKILLS_DIR = default_skills_dir()
REGISTRY_PATH = ROOT / ".agentic-pi" / "run_kernel" / "phase_registry.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


# ── Expected skills map: skill_dir -> (phase, role, artifact_pattern) ─────────

EXPECTED_SKILLS = {
    "question-contract": {
        "phases": ["INTAKE", "QUESTIONING"],
        "role": "Questioner",
        "artifact": "question_contract.json",
    },
    "research-pack": {
        "phases": ["RESEARCHING"],
        "role": "Researcher",
        "artifact": "research_pack.md",
    },
    "design-options": {
        "phases": ["DESIGNING"],
        "role": "Designer",
        "artifact": "design_options.json",
    },
    "structure-outline": {
        "phases": ["STRUCTURING"],
        "role": "Structurer",
        "artifact": "structure_outline.json",
    },
    "root-plan": {
        "phases": ["PLANNING"],
        "role": "Planner",
        "artifact": "plan_graph.json",
    },
    "artifact-contract": {
        "phases": ["WORKTREE_READY"],
        "role": "Engineer",
        "artifact": "workspace_manifest.json",
    },
    "validator-factory": {
        "phases": ["VALIDATOR_BUILDING"],
        "role": "ValidatorEngineer",
        "artifact": "validator_spec.json",
    },
    "path-grounding": {
        "phases": ["IMPLEMENTING"],
        "role": "Engineer",
        "artifact": None,  # reference skill, no standalone artifact
    },
    "harness-grill": {
        "phases": ["VALIDATING"],
        "role": "Critic",
        "artifact": "verifier_artifacts/",
    },
    "harness-tdd": {
        "phases": ["VALIDATING"],
        "role": "Critic",
        "artifact": "test_outputs/",
    },
    "harness-diagnose": {
        "phases": ["VALIDATING"],
        "role": "Critic",
        "artifact": "diagnostic_report.json",
    },
    "harness-certify": {
        "phases": ["CERTIFYING"],
        "role": "Certifier",
        "artifact": "certification.json + final_status.json",
    },
    "write-memory": {
        "phases": ["MEMORY_CONSOLIDATING"],
        "role": "MemoryWriter",
        "artifact": "memory_write_proposal.json",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  Skill File Existence Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSkillFilesExist(unittest.TestCase):
    """All 13 skill directories and SKILL.md files exist."""

    def test_13_skills_exist(self):
        skill_dirs = sorted(d.name for d in SKILLS_DIR.iterdir() if d.is_dir())
        expected = sorted(EXPECTED_SKILLS.keys())
        missing = sorted(set(expected) - set(skill_dirs))
        self.assertEqual(missing, [],
                         f"Expected QRSPI skills missing from {SKILLS_DIR}: {missing}; found {skill_dirs}")

    def test_all_skills_have_skill_md(self):
        for skill_name in EXPECTED_SKILLS:
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            self.assertTrue(skill_md.exists(),
                            f"Missing SKILL.md for skill '{skill_name}'")

    def test_skill_md_files_not_empty(self):
        for skill_name in EXPECTED_SKILLS:
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            content = skill_md.read_text(encoding="utf-8").strip()
            self.assertGreater(len(content), 50,
                              f"SKILL.md for '{skill_name}' is too short")


# ══════════════════════════════════════════════════════════════════════════════
#  Skill Content Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSkillContent(unittest.TestCase):
    """Each skill correctly references its phase, role, and artifact type."""

    def test_skills_reference_phase(self):
        for skill_name, expected in EXPECTED_SKILLS.items():
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            content = skill_md.read_text(encoding="utf-8")
            for phase in expected["phases"]:
                self.assertIn(phase, content,
                              f"Skill '{skill_name}' should reference phase '{phase}'")

    def test_skills_reference_role(self):
        for skill_name, expected in EXPECTED_SKILLS.items():
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            content = skill_md.read_text(encoding="utf-8")
            self.assertIn(expected["role"], content,
                          f"Skill '{skill_name}' should reference role '{expected['role']}'")

    def test_skills_reference_artifact(self):
        for skill_name, expected in EXPECTED_SKILLS.items():
            if expected["artifact"] is None:
                continue  # path-grounding has no standalone artifact
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            content = skill_md.read_text(encoding="utf-8")
            # Check that any part of the artifact reference appears in the content
            artifact_str = expected["artifact"]
            parts = artifact_str.replace(" + ", " ").split()
            found = any(p in content for p in parts if p)
            self.assertTrue(found,
                          f"Skill '{skill_name}' should reference artifact '{expected['artifact']}'" + 
                          f" (looked for any of: {parts})")


# ══════════════════════════════════════════════════════════════════════════════
#  Authority Boundary Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSkillAuthorityBoundaries(unittest.TestCase):
    """No skill (except harness-certify) claims certify authority.

    The only skill that may write final_status.json, certification.json,
    or policy_decision.json is harness-certify.
    """

    def test_skills_have_authority_boundaries_section(self):
        skip_skills = {"harness-certify"}  # this one IS the certifier
        for skill_name in EXPECTED_SKILLS:
            if skill_name in skip_skills:
                continue
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            content = skill_md.read_text(encoding="utf-8")
            self.assertIn("Authority Boundaries", content,
                          f"Skill '{skill_name}' missing Authority Boundaries section")
            has_refusal = "Do NOT certify" in content or "Do NOT claim DONE" in content \
                          or "Do NOT write authority" in content or "cannot certify" in content
            self.assertTrue(has_refusal,
                          f"Skill '{skill_name}' does not forbid certification")
            has_fs_refusal = "final_status.json" in content or "authority files" in content \
                          or "Do NOT change status" in content or "cannot override" in content \
                          or "Do NOT write any" in content
            self.assertTrue(has_fs_refusal,
                          f"Skill '{skill_name}' does not forbid final_status.json or authority files")

    def test_only_certify_skill_can_certify(self):
        """Verify harness-certify explicitly claims authority, others don't."""
        for skill_name in EXPECTED_SKILLS:
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            content = skill_md.read_text(encoding="utf-8")

            if skill_name == "harness-certify":
                self.assertIn("final_status.json", content)
                self.assertIn("certifier_only", content)
                self.assertNotIn("Do NOT certify", content,
                                "harness-certify should not forbid certification")
                self.assertNotIn("Do NOT claim DONE", content,
                                "harness-certify should not forbid claiming DONE")
            else:
                has_refusal = "Do NOT certify" in content or "Do NOT claim DONE" in content \
                              or "Do NOT write authority" in content or "cannot certify" in content
                self.assertTrue(has_refusal,
                              f"Skill '{skill_name}' should forbid certification")


# ══════════════════════════════════════════════════════════════════════════════
#  Phase Registry Consistency Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPhaseRegistryConsistency(unittest.TestCase):
    """Verify phase_registry.json is consistent with the skills."""

    def setUp(self):
        self.registry = load_json(REGISTRY_PATH)

    def test_registry_has_phases_for_all_skills(self):
        registry_phases = {e["phase"] for e in self.registry["phases"]}
        skill_phases = set()
        for expected in EXPECTED_SKILLS.values():
            for p in expected["phases"]:
                skill_phases.add(p)
        # Every skill phase must exist in the registry (except generic ones)
        for sp in skill_phases:
            self.assertIn(sp, registry_phases,
                          f"Phase '{sp}' from skills not found in phase_registry.json")

    def test_registry_roles_match_skills(self):
        for entry in self.registry["phases"]:
            phase = entry["phase"]
            role = entry.get("role", "")
            expected_role = None
            for skill_name, expected in EXPECTED_SKILLS.items():
                if phase in expected["phases"]:
                    expected_role = expected["role"]
                    break
            if expected_role and entry.get("expected_output"):
                # Not all phases have skills; only check ones that do
                self.assertEqual(role, expected_role,
                                f"Phase '{phase}' has role '{role}' in registry "
                                f"but skill expects '{expected_role}'")


# ══════════════════════════════════════════════════════════════════════════════
#  No Python files in Skills (info-only)
# ══════════════════════════════════════════════════════════════════════════════

class TestSkillsAreInfoOnly(unittest.TestCase):
    """Skills should be markdown info files, not executable code."""

    def test_no_python_files_in_skills(self):
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            py_files = list(skill_dir.glob("*.py"))
            self.assertEqual(len(py_files), 0,
                            f"Skill '{skill_dir.name}' contains Python files: {py_files}")

    def test_skills_directory_has_no_root_py(self):
        py_files = list(SKILLS_DIR.glob("*.py"))
        self.assertEqual(len(py_files), 0,
                        f"Root skills directory contains Python files: {py_files}")


if __name__ == "__main__":
    unittest.main()
