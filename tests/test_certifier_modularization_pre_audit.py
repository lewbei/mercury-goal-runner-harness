import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "CERTIFIER_MODULARIZATION_PRE_AUDIT_V1.md"
CERTIFIER = ROOT / ".agentic-pi" / "validators" / "certify_run.py"
PROOF_MATRIX = ROOT / ".agentic-pi" / "proof_matrix" / "proof_matrix.json"


class CertifierModularizationPreAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.certifier_functions = {
            node.name
            for node in ast.parse(CERTIFIER.read_text(encoding="utf-8")).body
            if isinstance(node, ast.FunctionDef)
        }

    def test_pre_audit_preserves_authority_boundary(self):
        required = [
            "Status: pre-refactor audit only",
            "This file does not certify DONE",
            "Policy decides.",
            "Certifier writes final status.",
            "Do not create a second writer",
            "does not implement modularization",
            "does not execute, certify, or change final status artifacts",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_current_certifier_function_map_names_existing_functions(self):
        required_functions = [
            "status_after_failures",
            "build_final_status_data",
            "resolve_run_path",
            "validate_touched_files",
            "validate_step_shape",
            "load_merged_steps",
            "validate_against_merged_plan",
            "split_artifact_command",
            "validate_artifact_command_allowlist",
            "run_artifact_command_test",
            "load_verifier_contract",
            "load_verifier_artifacts",
            "record_verifier_smell_reports",
            "record_verifier_strength_reports",
            "run_policy_engine",
            "apply_replay_gate",
            "apply_evidence_freeze_gate",
            "apply_memory_authority_gate",
            "evaluate_done_criteria",
            "check_validator_certification",
            "main",
        ]
        for name in required_functions:
            with self.subTest(function=name):
                self.assertIn(name, self.certifier_functions)
                self.assertIn(f"`{name}`", self.doc)

    def test_future_module_seams_are_explicitly_non_authority_expanding(self):
        seams = [
            "certifier_io.py",
            "certifier_paths.py",
            "certifier_step_logs.py",
            "certifier_artifact_commands.py",
            "certifier_goal_outputs.py",
            "certifier_verifier_pipeline.py",
            "certifier_gates/",
            "certifier_final_status.py",
        ]
        for seam in seams:
            with self.subTest(seam=seam):
                self.assertIn(seam, self.doc)
        self.assertIn("These are future seams only. They are not implemented by this audit.", self.doc)
        self.assertIn("Policy decides; certifier writes final status", self.doc)

    def test_golden_behavior_plan_covers_authority_and_legacy_edges(self):
        cases = [
            "missing verifier artifact -> NOT_DONE",
            "P0 verifier evidence -> PROVISIONAL_DONE",
            "P1 verifier evidence -> PROVISIONAL_DONE",
            "P2 strong verifier evidence -> CERTIFIED_DONE",
            "legacy pass -> DONE_PASS (deprecated compatibility only)",
            "legacy fail -> DONE_FAIL (deprecated compatibility only)",
            "policy CERTIFIED_DONE plus later replay/evidence/audit gate failure -> final NOT_DONE",
            "artifact command shell/operator/eval/path-escape/protected-argument attempt -> blocked",
            "final_status.md says CERTIFIED_DONE while final_status.json says NOT_DONE -> authoritative status remains NOT_DONE",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertIn(case, self.doc)

    def test_proof_matrix_tracks_pre_audit_lock_test(self):
        matrix = PROOF_MATRIX.read_text(encoding="utf-8")
        self.assertIn('"claim_id": "certifier_modularization_pre_audit"', matrix)
        self.assertIn("tests/test_certifier_modularization_pre_audit.py", matrix)
        self.assertIn("pre-refactor audit only", matrix)


if __name__ == "__main__":
    unittest.main()
