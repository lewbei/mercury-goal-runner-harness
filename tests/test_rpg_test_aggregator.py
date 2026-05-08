import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGGREGATOR_PATH = ROOT / ".agentic-pi" / "runtime" / "rpg_test_aggregator.py"
TEMPLATE_PATH = ROOT / ".agentic-pi" / "templates" / "rpg_test_record.template.json"
SCHEMA_PATH = ROOT / ".agentic-pi" / "schemas" / "rpg_test_aggregation_result.schema.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_record(path: Path, record: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


class RpgTestAggregatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.aggregator = load_module("rpg_test_aggregator_for_tests", AGGREGATOR_PATH)
        cls.validator = load_module(
            "validate_schema_for_rpg_aggregator_tests",
            ROOT / ".agentic-pi" / "validators" / "validate_schema.py",
        )

    def validate_schema(self, instance):
        schema = self.validator.load_json(SCHEMA_PATH)
        return self.validator.validate(instance, schema)

    def test_template_aggregates_as_one_valid_record_without_certifying(self):
        result = self.aggregator.aggregate_records([TEMPLATE_PATH], min_records=1)

        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["schema_valid_count"], 1)
        self.assertEqual(result["schema_invalid_count"], 0)
        self.assertEqual(result["included_count"], 1)
        self.assertEqual(result["false_certified_done_count"], 0)
        self.assertEqual(result["monitor_miss_count"], 0)
        self.assertTrue(result["stopping_rule_met"], result)
        self.assertEqual(result["final_status_authority"], "certifier_only")
        self.assertFalse(result["can_certify_done"])
        self.assertEqual(self.validate_schema(result), [])

    def test_false_certified_done_breaks_stopping_rule(self):
        template = load_json(TEMPLATE_PATH)
        bad = copy.deepcopy(template)
        bad["record_id"] = "false_certified_done_record"
        bad["test_identity"]["test_id"] = "RPG-BAD-001"
        bad["failure_classification"] = {
            "result": "FALSE_CERTIFIED_DONE",
            "root_cause": "Unsupported DONE was accepted.",
            "validator_should_catch": "policy_engine",
            "was_caught": False,
        }

        with tempfile.TemporaryDirectory() as tmp:
            record_path = Path(tmp) / "rpg_test_record.json"
            write_record(record_path, bad)
            result = self.aggregator.aggregate_records([record_path], min_records=1)

        self.assertFalse(result["stopping_rule_met"])
        self.assertEqual(result["false_certified_done_count"], 1)
        self.assertEqual(result["false_certified_done_rate_bps"], 10000)
        self.assertEqual(result["monitor_miss_count"], 1)

    def test_excluded_records_do_not_affect_statistics(self):
        template = load_json(TEMPLATE_PATH)
        excluded = copy.deepcopy(template)
        excluded["record_id"] = "excluded_record"
        excluded["test_identity"]["test_id"] = "RPG-EXCLUDED-001"
        excluded["statistical_metadata"]["include_in_statistics"] = False
        excluded["statistical_metadata"]["exclusion_reason"] = "manual exploratory note"
        excluded["failure_classification"]["result"] = "FALSE_CERTIFIED_DONE"
        excluded["failure_classification"]["was_caught"] = False

        with tempfile.TemporaryDirectory() as tmp:
            record_path = Path(tmp) / "rpg_test_record.json"
            write_record(record_path, excluded)
            result = self.aggregator.aggregate_records([record_path], min_records=0)

        self.assertTrue(result["stopping_rule_met"], result)
        self.assertEqual(result["included_count"], 0)
        self.assertEqual(result["excluded_count"], 1)
        self.assertEqual(result["false_certified_done_count"], 0)
        self.assertEqual(result["monitor_miss_count"], 0)

    def test_invalid_record_is_reported_and_fails_gate(self):
        invalid = {"record_id": "invalid"}

        with tempfile.TemporaryDirectory() as tmp:
            record_path = Path(tmp) / "rpg_test_record.json"
            write_record(record_path, invalid)
            result = self.aggregator.aggregate_records([record_path], min_records=1)

        self.assertFalse(result["stopping_rule_met"])
        self.assertEqual(result["schema_invalid_count"], 1)
        self.assertTrue(result["invalid_records"])

    def test_cli_writes_schema_valid_aggregation_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "rpg_test_aggregation_result.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(AGGREGATOR_PATH),
                    str(TEMPLATE_PATH),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            self.assertEqual(result.returncode, 0, result.stdout)
            payload = load_json(output)

        self.assertEqual(payload["version"], "v3.4")
        self.assertTrue(payload["stopping_rule_met"])
        self.assertEqual(self.validate_schema(payload), [])

    def test_v34_doc_locks_aggregation_boundary(self):
        doc = (ROOT / "docs" / "V3_4_RPG_TEST_AGGREGATION.md").read_text(encoding="utf-8")

        self.assertIn("RPG TEST AGGREGATION IMPLEMENTED", doc)
        self.assertIn("false_certified_done_rate_bps", doc)
        self.assertIn("monitor_miss_rate_bps", doc)
        self.assertIn("confidence_intervals_bps", doc)
        self.assertIn("It does not prove", doc)
        self.assertIn("The aggregator cannot certify DONE", doc)


if __name__ == "__main__":
    unittest.main()
