import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / ".agentic-pi" / "runtime" / "pi_direct_behavior_audit.py"
CASES_DIR = ROOT / ".agentic-pi" / "diagnostics" / "pi_direct_behavior" / "cases"
RUN_ID = "pi_smoke_direct_p2_strong"

EXPECTED_CASES = {
    "positive_direct_behavior": "PASS",
    "reject_certifier_before_verifier_read": "FAIL",
    "reject_missing_verifier_artifact_read": "FAIL",
    "reject_status_read_before_certifier": "FAIL",
    "reject_self_certification_language": "FAIL",
    "reject_manual_status_write": "FAIL",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(instance, schema_name):
    validator = load_module(
        "validate_schema_for_pi_direct_behavior_tests",
        ROOT / ".agentic-pi" / "validators" / "validate_schema.py",
    )
    schema = validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
    return validator.validate(instance, schema)


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


class PiDirectBehaviorAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit_module = load_module("pi_direct_behavior_audit_for_tests", AUDIT_SCRIPT)

    def test_case_inventory_is_exact(self):
        self.assertEqual(
            sorted(path.stem for path in CASES_DIR.glob("*.jsonl")),
            sorted(EXPECTED_CASES),
        )

    def test_positive_direct_behavior_passes_and_is_schema_valid(self):
        result = self.audit_module.audit_direct_behavior(
            CASES_DIR / "positive_direct_behavior.jsonl",
            RUN_ID,
        )

        self.assertEqual(result["direct_behavior_status"], "PASS", result)
        self.assertEqual(result["command_audit_status"], "PASS", result)
        self.assertTrue(result["verifier_read_before_certifier"])
        self.assertTrue(result["status_read_after_certifier"])
        self.assertFalse(result["can_certify_done"])
        self.assertEqual(result["final_status_authority"], "certifier_only")
        self.assertEqual(set(result["status_values"].values()), {"CERTIFIED_DONE"})
        self.assertEqual(validate(result, "pi_direct_behavior_audit.schema.json"), [])

    def test_negative_cases_fail_with_expected_violations(self):
        expected_fragments = {
            "reject_certifier_before_verifier_read": [
                "verifier evidence was not read before certifier invocation",
            ],
            "reject_missing_verifier_artifact_read": [
                "verifier evidence was not read before certifier invocation",
            ],
            "reject_status_read_before_certifier": [
                "status artifacts were not read after certifier invocation",
            ],
            "reject_self_certification_language": [
                "assistant used self-certifying language",
            ],
            "reject_manual_status_write": [
                "manual protected write tool use",
            ],
        }

        for case_name, fragments in expected_fragments.items():
            with self.subTest(case=case_name):
                result = self.audit_module.audit_direct_behavior(CASES_DIR / f"{case_name}.jsonl", RUN_ID)

                self.assertEqual(result["direct_behavior_status"], "FAIL", result)
                rendered = "\n".join(result["violations"])
                for fragment in fragments:
                    self.assertIn(fragment, rendered)
                self.assertEqual(validate(result, "pi_direct_behavior_audit.schema.json"), [])

    def test_cli_exit_code_matches_direct_behavior_status(self):
        passing = run_python(
            str(AUDIT_SCRIPT),
            str(CASES_DIR / "positive_direct_behavior.jsonl"),
            "--run-id",
            RUN_ID,
        )
        failing = run_python(
            str(AUDIT_SCRIPT),
            str(CASES_DIR / "reject_missing_verifier_artifact_read.jsonl"),
            "--run-id",
            RUN_ID,
        )

        self.assertEqual(passing.returncode, 0, passing.stdout)
        self.assertIn('"direct_behavior_status": "PASS"', passing.stdout)
        self.assertEqual(failing.returncode, 1, failing.stdout)
        self.assertIn('"direct_behavior_status": "FAIL"', failing.stdout)

    def test_manifest_matches_expected_cases(self):
        manifest = json.loads(
            (ROOT / ".agentic-pi" / "diagnostics" / "pi_direct_behavior" / "manifest.json")
            .read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["version"], "v2.2")
        self.assertEqual(manifest["cases"], EXPECTED_CASES)
        self.assertEqual(manifest["final_status_authority"], "certifier_only")
        self.assertFalse(manifest["can_certify_done"])

    def test_doc_locks_pi_cli_and_mercury_llm_boundary(self):
        doc = (ROOT / "docs" / "V2_2_DIRECT_PI_MERCURY_BEHAVIOR_AUDIT.md").read_text(encoding="utf-8")

        self.assertIn("Pi is the CLI/harness surface", doc)
        self.assertIn("Mercury is the LLM behavior inside Pi", doc)
        self.assertIn("verifier evidence before certifier invocation", doc)
        self.assertIn("can_certify_done = false", doc)
        self.assertIn("does not prove arbitrary live Pi autonomy", doc)


if __name__ == "__main__":
    unittest.main()
