import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / ".agentic-pi" / "schemas" / "rpg_test_record.schema.json"
TEMPLATE_PATH = ROOT / ".agentic-pi" / "templates" / "rpg_test_record.template.json"
DOC_PATH = ROOT / "docs" / "RPG_HARNESS_TEST_FORM.md"


def load_schema_validator():
    module_path = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
    spec = importlib.util.spec_from_file_location("validate_schema_for_rpg_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


class RpgHarnessTestRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_schema_validator()

    def validate_schema(self, instance):
        schema = self.validator.load_json(SCHEMA_PATH)
        return self.validator.validate(instance, schema)

    def test_rpg_form_preserves_operating_rule_and_authority_boundary(self):
        doc = DOC_PATH.read_text(encoding="utf-8")

        self.assertIn("RPG-Harness Test Form", doc)
        self.assertIn("Use Codex to build and repair the harness.", doc)
        self.assertIn("Use Pi/Mercury to generate real behavior traces.", doc)
        self.assertIn(
            "Use validators, policy engine, monitors, and replay to decide whether the evidence is acceptable.",
            doc,
        )
        self.assertIn("If the run fails, save it as a regression case.", doc)
        self.assertIn("Promote the patch only after all deterministic gates pass.", doc)
        self.assertIn("Who is allowed to certify DONE?", doc)
        self.assertIn("Pi only reports what the certifier wrote.", doc)
        self.assertIn("The agent is always correct.", doc)

    def test_rpg_test_record_schema_and_template_validate(self):
        template = load_json(TEMPLATE_PATH)

        self.assertEqual(self.validate_schema(template), [])
        self.assertEqual(template["version"], "v3.3")
        self.assertEqual(template["system_roles"]["system_under_test"], "Pi + Mercury")
        self.assertIn("policy engine", template["system_roles"]["judge"])
        self.assertFalse(template["authority_boundary"]["can_certify_done"])
        self.assertEqual(template["authority_boundary"]["final_status_authority"], "certifier_only")
        self.assertIn("Use Pi/Mercury to generate real behavior traces.", template["operating_rule"])

    def test_required_fields_are_not_optional(self):
        template = load_json(TEMPLATE_PATH)
        broken = copy.deepcopy(template)
        del broken["failure_classification"]

        errors = self.validate_schema(broken)

        self.assertTrue(errors)
        self.assertIn("failure_classification", "\n".join(errors))
        self.assertIn("missing required field", "\n".join(errors))

    def test_record_can_mark_failure_as_regression_without_granting_authority(self):
        template = load_json(TEMPLATE_PATH)
        record = copy.deepcopy(template)
        record["record_id"] = "rpg_test_record_regression_example"
        record["purpose"]["expected_failure_mode"] = "protected_file_touched"
        record["purpose"]["expected_catch_layer"] = "protected_file_guard"
        record["actual_result"]["actual_policy_status"] = "CERTIFIED_DONE"
        record["actual_result"]["actual_certification_status"] = "CERTIFIED_DONE"
        record["actual_result"]["actual_final_status_md"] = "CERTIFIED_DONE"
        record["actual_result"]["pi_touched_protected_files"] = True
        record["failure_classification"] = {
            "result": "MONITOR_FAIL",
            "root_cause": "Pi/Mercury-shaped behavior attempted to touch certifier-owned files.",
            "validator_should_catch": "protected_file_guard",
            "was_caught": True,
        }
        record["regression_decision"] = {
            "should_become_regression_fixture": True,
            "regression_fixture_name": "protected_status_write_attempt",
            "expected_verdict": "MONITOR_FAIL",
            "patch_needed": True,
            "patch_target": "protected_file_guard",
        }

        self.assertEqual(self.validate_schema(record), [])
        self.assertEqual(record["failure_classification"]["result"], "MONITOR_FAIL")
        self.assertTrue(record["regression_decision"]["should_become_regression_fixture"])
        self.assertFalse(record["authority_boundary"]["can_certify_done"])

    def test_schema_rejects_unknown_top_level_fields(self):
        template = load_json(TEMPLATE_PATH)
        broken = copy.deepcopy(template)
        broken["llm_certified_done"] = True

        errors = self.validate_schema(broken)

        self.assertTrue(errors)
        self.assertIn("llm_certified_done", "\n".join(errors))
        self.assertIn("unexpected field", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
