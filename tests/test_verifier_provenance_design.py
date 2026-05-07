import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_schema_validator():
    module_path = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
    spec = importlib.util.spec_from_file_location("validate_schema", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path):
    validator = load_schema_validator()
    return validator.load_json(path)


def validate(instance, schema_name):
    validator = load_schema_validator()
    schema = validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
    return validator.validate(instance, schema)


def valid_verifier_artifact():
    return {
        "artifact_id": "V.CSV_BEHAVIOR_TEST_001",
        "run_id": "real_goal_002",
        "target_artifact": "cli_tool.py",
        "kind": "command_test",
        "source": "same_run_worker",
        "created_at": "2026-05-06T00:00:00Z",
        "created_at_phase": "post_solution",
        "author_agent": "guarded-worker",
        "author_model": "inception/mercury-2",
        "provenance_level": "P0",
        "depends_on_solution": True,
        "same_worker_as_solution": True,
        "executes_code": True,
        "assertion_count": 2,
        "mock_ratio_percent": 0,
        "smell_flags": [],
        "authority": "advisory",
        "solution_exists_at_creation": True,
    }


def valid_verifier_contract():
    return {
        "run_id": "csv_cli_001",
        "target_goal": "Create a CSV summary CLI.",
        "target_artifacts": ["cli_tool.py"],
        "required_verifier_level": "P2",
        "allow_self_generated_only": False,
        "required_behaviors": [
            "reads CSV path from command line",
            "prints row count",
            "prints column count",
            "prints column names",
        ],
        "forbidden_verifier_patterns": [
            "file existence only",
            "exit code only",
            "print-only observation",
            "test written after solution by same worker",
        ],
        "minimum_strength_level": "certifying",
        "certifying_authority_levels": ["P2", "P3"],
        "provisional_authority_levels": ["P0", "P1"],
    }


def valid_certification(status):
    return {
        "run_id": "csv_cli_001",
        "status": status,
        "passed_checks": [],
        "failed_checks": [],
        "artifact_hashes": {},
        "audit_chain_valid": True,
        "generated_by": "agentic-pi-certifier-v0.3.2",
        "timestamp": "2026-05-06T00:00:00Z",
    }


class VerifierProvenanceDesignTests(unittest.TestCase):
    def test_valid_verifier_artifact_schema_passes(self):
        errors = validate(valid_verifier_artifact(), "verifier_artifact.schema.json")

        self.assertEqual(errors, [])

    def test_missing_provenance_level_fails(self):
        artifact = valid_verifier_artifact()
        del artifact["provenance_level"]

        errors = validate(artifact, "verifier_artifact.schema.json")

        self.assertTrue(any("missing required field provenance_level" in error for error in errors), errors)

    def test_unknown_verifier_artifact_field_fails(self):
        artifact = valid_verifier_artifact()
        artifact["unexpected"] = True

        errors = validate(artifact, "verifier_artifact.schema.json")

        self.assertTrue(any("unexpected field unexpected" in error for error in errors), errors)

    def test_invalid_provenance_level_fails(self):
        artifact = valid_verifier_artifact()
        artifact["provenance_level"] = "P4"

        errors = validate(artifact, "verifier_artifact.schema.json")

        self.assertTrue(any("value 'P4' not in enum" in error for error in errors), errors)

    def test_invalid_authority_fails(self):
        artifact = valid_verifier_artifact()
        artifact["authority"] = "final"

        errors = validate(artifact, "verifier_artifact.schema.json")

        self.assertTrue(any("value 'final' not in enum" in error for error in errors), errors)

    def test_valid_verifier_contract_schema_passes(self):
        errors = validate(valid_verifier_contract(), "verifier_contract.schema.json")

        self.assertEqual(errors, [])

    def test_certification_schema_allows_legacy_and_provenance_statuses(self):
        for status in ["DONE_PASS", "DONE_FAIL", "NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE"]:
            with self.subTest(status=status):
                errors = validate(valid_certification(status), "certification.schema.json")
                self.assertEqual(errors, [])

    def test_certification_schema_rejects_unknown_status(self):
        errors = validate(valid_certification("SELF_CERTIFIED_DONE"), "certification.schema.json")

        self.assertTrue(any("SELF_CERTIFIED_DONE" in error for error in errors), errors)

    def test_cross_field_policy_rule_is_documented_as_deferred(self):
        design = (ROOT / "VERIFIER_PROVENANCE_DESIGN.md").read_text(encoding="utf-8")
        policy = (ROOT / "certification_policy.yaml").read_text(encoding="utf-8")

        self.assertIn("allow_self_generated_only must be false", design)
        self.assertIn("P2_P3_REQUIRE_NOT_SELF_GENERATED_ONLY", policy)

    def test_docs_lock_current_direction_without_overclaim(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        status = (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")
        problem = (ROOT / "PROBLEM_AND_GAP.md").read_text(encoding="utf-8")

        self.assertIn("Verifier-Provenance Goal Runner Harness", readme)
        self.assertIn("Mercury Goal Runner Harness v1.9", status)
        self.assertIn("Verifier-Provenance Goal Runner Harness", status)
        self.assertNotIn("v0.4 should add evidence-seeking branch selection", readme)
        self.assertNotIn("we solve verification", problem.lower())


if __name__ == "__main__":
    unittest.main()
