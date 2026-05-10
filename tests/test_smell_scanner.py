import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_DIR = ROOT / ".agentic-pi" / "diagnostics" / "provenance_gate"
RUN_ROOT = ROOT / ".agentic-runs"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def validate(instance, schema_name):
    validator = load_module(
        "validate_schema_for_smell_tests",
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


def load_scanner():
    return load_module(
        "smell_scanner_for_tests",
        ROOT / ".agentic-pi" / "validators" / "smell_scanner.py",
    )


def base_artifact(**overrides):
    artifact = {
        "artifact_id": "V.TEST",
        "run_id": "test_run",
        "target_artifact": "out.txt",
        "kind": "command_test",
        "source": "independent_verifier_agent",
        "created_at": "2026-05-07T00:00:00+00:00",
        "created_at_phase": "pre_solution",
        "author_agent": "independent-verifier",
        "author_model": "deterministic-independent-verifier",
        "provenance_level": "P2",
        "depends_on_solution": False,
        "same_worker_as_solution": False,
        "executes_code": True,
        "assertion_count": 2,
        "mock_ratio_percent": 0,
        "smell_flags": [],
        "authority": "certifying",
        "solution_exists_at_creation": False,
    }
    artifact.update(overrides)
    return artifact


class SmellScannerTests(unittest.TestCase):
    def setUp(self):
        self.scanner = load_scanner()
        self.created_run_dirs = []

    def tearDown(self):
        for run_dir in self.created_run_dirs:
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def test_smell_report_schema_accepts_valid_report(self):
        report = self.scanner.scan_verifier_artifact(base_artifact())

        self.assertEqual(validate(report, "verifier_smell_report.schema.json"), [])

    def test_smell_report_schema_rejects_unknown_field(self):
        report = self.scanner.scan_verifier_artifact(base_artifact())
        report["unexpected"] = True

        errors = validate(report, "verifier_smell_report.schema.json")

        self.assertTrue(any("'unexpected'" in error and "unexpected field" in error for error in errors), errors)

    def test_p0_self_test_gets_self_certification_smells(self):
        artifact = load_json(
            DIAGNOSTIC_DIR
            / "case_p0_self_test"
            / "verifier_artifacts"
            / "V.P0_SELF.json"
        )

        report = self.scanner.scan_verifier_artifact(artifact)

        self.assertIn("same_worker_self_test", report["smell_flags"])
        self.assertIn("post_solution_test", report["smell_flags"])
        self.assertIn("depends_on_solution", report["smell_flags"])
        self.assertIn("p0_self_authored", report["smell_flags"])
        self.assertIn("advisory_only", report["smell_flags"])
        self.assertGreater(report["authority_penalty"], 0)

    def test_p1_visible_verifier_gets_warning_smells(self):
        artifact = load_json(
            DIAGNOSTIC_DIR
            / "case_p1_existing_test"
            / "verifier_artifacts"
            / "V.P1_EXISTING.json"
        )

        report = self.scanner.scan_verifier_artifact(artifact)

        self.assertIn("local_visible_verifier", report["smell_flags"])
        self.assertIn("gating_only", report["smell_flags"])
        self.assertNotIn("same_worker_self_test", report["smell_flags"])
        self.assertNotIn("p0_self_authored", report["smell_flags"])
        self.assertFalse(report["disqualifying"])

    def test_p2_independent_verifier_has_no_critical_smell(self):
        artifact = load_json(
            DIAGNOSTIC_DIR
            / "case_p2_independent_test"
            / "verifier_artifacts"
            / "V.P2_INDEPENDENT.json"
        )

        report = self.scanner.scan_verifier_artifact(artifact)

        self.assertFalse(report["disqualifying"])
        self.assertNotIn("same_worker_self_test", report["smell_flags"])
        self.assertNotIn("p0_self_authored", report["smell_flags"])
        self.assertNotIn("advisory_only", report["smell_flags"])

    def test_zero_assertion_verifier_gets_zero_assertions(self):
        report = self.scanner.scan_verifier_artifact(base_artifact(assertion_count=0))

        self.assertIn("zero_assertions", report["smell_flags"])
        self.assertTrue(report["disqualifying"])

    def test_mock_heavy_verifier_gets_mock_heavy(self):
        report = self.scanner.scan_verifier_artifact(base_artifact(mock_ratio_percent=80))

        self.assertIn("mock_heavy", report["smell_flags"])
        self.assertGreaterEqual(report["authority_penalty"], 2)

    def test_certifier_records_smell_reports_without_changing_v033_status(self):
        case_name = "case_p0_self_test"
        run_dir = RUN_ROOT / f"test_{case_name}"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        shutil.copytree(DIAGNOSTIC_DIR / case_name, run_dir)
        self.created_run_dirs.append(run_dir)

        result = run_python(".agentic-pi/validators/certify_run.py", str(run_dir))

        self.assertEqual(result.returncode, 0, result.stdout)
        certification = load_json(run_dir / "certification.json")
        self.assertEqual(certification["status"], "PROVISIONAL_DONE")
        report_path = run_dir / "verifier_smell_reports" / "V.P0_SELF.json"
        self.assertTrue(report_path.is_file())
        report = load_json(report_path)
        self.assertIn("same_worker_self_test", report["smell_flags"])
        self.assertIn("verifier smell scan recorded: V.P0_SELF", certification["passed_checks"])


if __name__ == "__main__":
    unittest.main()
