import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ".agentic-pi" / "diagnostics" / "host_integration" / "run_host_integration_evaluation.py"
RUN_ROOT = ROOT / ".agentic-runs"


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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HostIntegrationEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.output_dir = ROOT / "diagnostic_outputs" / "test_host_integration"
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)

    def tearDown(self):
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        runner = load_module("host_task_runner_for_cleanup", ROOT / ".agentic-pi" / "runtime" / "host_task_runner.py")
        for path in RUN_ROOT.glob("pi_smoke_host_*"):
            if path.is_dir():
                runner.safe_rmtree(path)

    def test_host_integration_evaluation_outputs_expected_metrics(self):
        result = run_python(
            str(RUNNER),
            "--output-dir",
            "diagnostic_outputs/test_host_integration",
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        metrics = load_json(self.output_dir / "host_integration_metrics.json")
        rows = {row["task_id"]: row for row in metrics["cases"]}

        self.assertEqual(metrics["total_cases"], 6)
        self.assertTrue(metrics["status_match"])
        self.assertEqual(metrics["false_certified_done_count"], 0)
        self.assertEqual(metrics["expected_failures_caught"], 3)
        self.assertEqual(rows["certify_p2_strong_once"]["observed_status"], "CERTIFIED_DONE")
        self.assertEqual(rows["certify_p1_visible_provisional"]["observed_status"], "PROVISIONAL_DONE")
        self.assertEqual(rows["reject_double_certifier_command"]["status"], "FAIL")
        self.assertTrue((self.output_dir / "host_integration_report.md").is_file())

    def test_host_task_result_schema_validates_generated_rows(self):
        result = run_python(
            str(RUNNER),
            "--output-dir",
            "diagnostic_outputs/test_host_integration",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        validator = load_module(
            "validate_schema_for_host_integration_tests",
            ROOT / ".agentic-pi" / "validators" / "validate_schema.py",
        )
        schema = validator.load_json(ROOT / ".agentic-pi" / "schemas" / "host_task_result.schema.json")
        metrics = load_json(self.output_dir / "host_integration_metrics.json")

        for row in metrics["cases"]:
            with self.subTest(task=row["task_id"]):
                row = dict(row)
                row.pop("expected_result")
                self.assertEqual(validator.validate(row, schema), [])


if __name__ == "__main__":
    unittest.main()
