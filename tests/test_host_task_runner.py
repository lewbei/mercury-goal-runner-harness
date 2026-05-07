import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOST_RUNNER = ROOT / ".agentic-pi" / "runtime" / "host_task_runner.py"
CASES_DIR = ROOT / ".agentic-pi" / "diagnostics" / "host_integration" / "cases"
RUN_ROOT = ROOT / ".agentic-runs"


EXPECTED_CASES = {
    "certify_p1_visible_provisional": ("PASS", "PROVISIONAL_DONE"),
    "certify_p2_strong_once": ("PASS", "CERTIFIED_DONE"),
    "read_status_p2_strong": ("PASS", "CERTIFIED_DONE"),
    "reject_double_certifier_command": ("FAIL", "CERTIFIED_DONE"),
    "reject_manual_status_write": ("FAIL", ""),
    "reject_source_run_mutation": ("FAIL", "CERTIFIED_DONE"),
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


class HostTaskRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_module("host_task_runner_for_tests", HOST_RUNNER)

    def tearDown(self):
        for path in RUN_ROOT.glob("pi_smoke_host_*"):
            if path.is_dir():
                self.runner.safe_rmtree(path)

    def test_case_inventory_is_exact(self):
        self.assertEqual(
            sorted(path.name for path in CASES_DIR.iterdir() if path.is_dir()),
            sorted(EXPECTED_CASES),
        )

    def test_host_task_schemas_validate(self):
        validator = load_module(
            "validate_schema_for_host_task_tests",
            ROOT / ".agentic-pi" / "validators" / "validate_schema.py",
        )
        schema = validator.load_json(ROOT / ".agentic-pi" / "schemas" / "host_task.schema.json")

        for case_name in EXPECTED_CASES:
            with self.subTest(case=case_name):
                task = load_json(CASES_DIR / case_name / "host_task.json")
                self.assertEqual(validator.validate(task, schema), [])

    def test_host_task_results_match_expected(self):
        for case_name, (expected_result, expected_status) in EXPECTED_CASES.items():
            with self.subTest(case=case_name):
                result = self.runner.evaluate_task(CASES_DIR / case_name / "host_task.json")

                self.assertEqual(result["status"], expected_result, result)
                self.assertEqual(result["observed_status"], expected_status)
                self.assertTrue(result["source_unchanged"])
                if expected_result == "PASS":
                    self.assertEqual(result["violations"], [])
                    self.assertLessEqual(result["command_count"], 1)
                else:
                    self.assertTrue(result["violations"], result)

    def test_rejects_non_smoke_target(self):
        with self.assertRaises(ValueError):
            self.runner.ensure_smoke_target(RUN_ROOT, "regular_host_run")

    def test_cli_exit_code_matches_task_result(self):
        passing = run_python(
            str(HOST_RUNNER),
            str(CASES_DIR / "certify_p2_strong_once" / "host_task.json"),
        )
        failing = run_python(
            str(HOST_RUNNER),
            str(CASES_DIR / "reject_double_certifier_command" / "host_task.json"),
        )

        self.assertEqual(passing.returncode, 0, passing.stdout)
        self.assertIn('"status": "PASS"', passing.stdout)
        self.assertEqual(failing.returncode, 1, failing.stdout)
        self.assertIn('"status": "FAIL"', failing.stdout)


if __name__ == "__main__":
    unittest.main()
