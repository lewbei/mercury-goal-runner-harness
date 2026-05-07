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
        "validate_schema_for_strength_tests",
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
        "smell_scanner_for_strength_tests",
        ROOT / ".agentic-pi" / "validators" / "smell_scanner.py",
    )


def load_scorer():
    return load_module(
        "strength_scorer_for_tests",
        ROOT / ".agentic-pi" / "validators" / "strength_scorer.py",
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


class StrengthScorerTests(unittest.TestCase):
    def setUp(self):
        self.scanner = load_scanner()
        self.scorer = load_scorer()
        self.created_run_dirs = []

    def tearDown(self):
        for run_dir in self.created_run_dirs:
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def score(self, artifact):
        smell_report = self.scanner.scan_verifier_artifact(artifact)
        return self.scorer.score_verifier_artifact(artifact, smell_report)

    def load_fixture_artifact(self, case_name, artifact_name):
        return load_json(
            DIAGNOSTIC_DIR
            / case_name
            / "verifier_artifacts"
            / artifact_name
        )

    def test_strength_report_schema_accepts_valid_report(self):
        report = self.score(base_artifact())

        self.assertEqual(validate(report, "verifier_strength_report.schema.json"), [])

    def test_strength_report_schema_rejects_unknown_field(self):
        report = self.score(base_artifact())
        report["unexpected"] = True

        errors = validate(report, "verifier_strength_report.schema.json")

        self.assertTrue(any("unexpected field unexpected" in error for error in errors), errors)

    def test_p0_self_test_is_weak_or_advisory(self):
        artifact = self.load_fixture_artifact("case_p0_self_test", "V.P0_SELF.json")

        report = self.score(artifact)

        self.assertIn(report["strength_level"], {"weak", "advisory"})
        self.assertIn("same_worker_self_test", report["penalties"])
        self.assertIn("p0_self_authored", report["penalties"])

    def test_p1_existing_visible_test_is_advisory_or_gating(self):
        artifact = self.load_fixture_artifact("case_p1_existing_test", "V.P1_EXISTING.json")

        report = self.score(artifact)

        self.assertIn(report["strength_level"], {"advisory", "gating"})
        self.assertIn("executes_target_artifact", report["positive_factors"])
        self.assertNotIn("p0_self_authored", report["penalties"])

    def test_p2_independent_verifier_is_certifying(self):
        artifact = self.load_fixture_artifact("case_p2_independent_test", "V.P2_INDEPENDENT.json")

        report = self.score(artifact)

        self.assertEqual(report["strength_level"], "certifying")
        self.assertGreaterEqual(report["score"], 8)
        self.assertIn("p2_or_p3_authority", report["positive_factors"])
        self.assertIn("independent_authority", report["positive_factors"])
        self.assertEqual(report["penalties"], [])

    def test_zero_assertion_verifier_is_weak_or_advisory(self):
        artifact = base_artifact(assertion_count=0)

        report = self.score(artifact)

        self.assertIn("zero_assertions", report["penalties"])
        self.assertIn(report["strength_level"], {"weak", "advisory"})

    def test_mock_heavy_verifier_is_downgraded(self):
        clean_report = self.score(base_artifact())
        mock_heavy_report = self.score(base_artifact(mock_ratio_percent=80))

        self.assertIn("mock_heavy", mock_heavy_report["penalties"])
        self.assertLess(mock_heavy_report["score"], clean_report["score"])
        self.assertNotEqual(mock_heavy_report["strength_level"], "certifying")

    def test_certifier_records_strength_reports_without_changing_status(self):
        case_name = "case_p2_independent_test"
        run_dir = RUN_ROOT / f"test_{case_name}"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        shutil.copytree(DIAGNOSTIC_DIR / case_name, run_dir)
        self.created_run_dirs.append(run_dir)

        result = run_python(".agentic-pi/validators/certify_run.py", str(run_dir))

        self.assertEqual(result.returncode, 0, result.stdout)
        certification = load_json(run_dir / "certification.json")
        self.assertEqual(certification["status"], "CERTIFIED_DONE")
        report_path = run_dir / "verifier_strength_reports" / "V.P2_INDEPENDENT.json"
        self.assertTrue(report_path.is_file())
        report = load_json(report_path)
        self.assertEqual(report["strength_level"], "certifying")
        self.assertIn(
            "verifier strength score recorded: V.P2_INDEPENDENT=certifying",
            certification["passed_checks"],
        )


if __name__ == "__main__":
    unittest.main()
