import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = ROOT / ".agentic-pi" / "diagnostics" / "evaluation"
CASES_DIR = EVALUATION_DIR / "cases"
RUNNER = EVALUATION_DIR / "run_diagnostic_evaluation.py"
RUN_ROOT = ROOT / ".agentic-runs"

EXPECTED_CASES = {
    "file_exists_but_wrong": "NOT_DONE",
    "self_test_only": "PROVISIONAL_DONE",
    "p1_visible_only": "PROVISIONAL_DONE",
    "p2_weak": "PROVISIONAL_DONE",
    "p2_strong": "CERTIFIED_DONE",
    "missing_verifier": "NOT_DONE",
}

REQUIRED_FIXTURE_FILES = [
    "case.json",
    "goal_contract.json",
    "verifier_contract.json",
    "step_logs/001.json",
    "trace.jsonl",
    "artifacts/output.txt",
]


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


class DiagnosticEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.output_dir = RUN_ROOT / "test_diagnostic_evaluation_outputs"
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)

    def tearDown(self):
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        for run_dir in RUN_ROOT.glob("test_diagnostic_evaluation_*"):
            if run_dir.is_dir():
                shutil.rmtree(run_dir)

    def case_dirs(self):
        return sorted(path for path in CASES_DIR.iterdir() if path.is_dir())

    def run_evaluation(self):
        return run_python(
            str(RUNNER),
            "--output-dir",
            str(self.output_dir),
            "--run-prefix",
            "test_diagnostic_evaluation",
        )

    def test_case_inventory_is_exact(self):
        self.assertEqual(
            [path.name for path in self.case_dirs()],
            sorted(EXPECTED_CASES),
        )

    def test_cases_are_copy_ready_run_folders(self):
        for case_name, expected_policy_status in EXPECTED_CASES.items():
            with self.subTest(case=case_name):
                case_dir = CASES_DIR / case_name
                for rel_path in REQUIRED_FIXTURE_FILES:
                    self.assertTrue((case_dir / rel_path).exists(), rel_path)

                case = load_json(case_dir / "case.json")
                goal = load_json(case_dir / "goal_contract.json")
                verifier_contract = load_json(case_dir / "verifier_contract.json")
                step = load_json(case_dir / "step_logs" / "001.json")

                self.assertEqual(case["case_id"], case_name)
                self.assertEqual(case["expected_policy_status"], expected_policy_status)
                self.assertEqual(goal["run_id"], f"diagnostic_eval_{case_name}")
                self.assertEqual(verifier_contract["run_id"], f"diagnostic_eval_{case_name}")
                self.assertEqual(step["run_id"], f"diagnostic_eval_{case_name}")
                self.assertEqual(goal["final_outputs"], ["artifacts/output.txt"])
                self.assertEqual(verifier_contract["target_artifacts"], ["artifacts/output.txt"])

    def test_diagnostic_evaluation_outputs_expected_metrics(self):
        result = self.run_evaluation()

        self.assertEqual(result.returncode, 0, result.stdout)
        metrics_path = self.output_dir / "diagnostic_metrics.json"
        report_path = self.output_dir / "diagnostic_report.md"
        self.assertTrue(metrics_path.is_file(), result.stdout)
        self.assertTrue(report_path.is_file(), result.stdout)

        metrics = load_json(metrics_path)
        rows = {row["case_id"]: row for row in metrics["cases"]}

        self.assertEqual(metrics["total_cases"], 6)
        self.assertEqual(set(rows), set(EXPECTED_CASES))
        for case_name, expected_status in EXPECTED_CASES.items():
            self.assertEqual(
                rows[case_name]["statuses"]["policy_engine"],
                expected_status,
                case_name,
            )

        self.assertEqual(
            metrics["modes"]["policy_engine"]["false_certified_done_rate"],
            0.0,
        )
        self.assertGreater(
            metrics["modes"]["file_existence"]["false_certified_done_rate"],
            metrics["modes"]["policy_engine"]["false_certified_done_rate"],
        )
        self.assertGreater(
            metrics["modes"]["artifact_test"]["false_certified_done_rate"],
            metrics["modes"]["policy_engine"]["false_certified_done_rate"],
        )

    def test_diagnostic_matrix_shows_policy_gain_cases(self):
        result = self.run_evaluation()
        self.assertEqual(result.returncode, 0, result.stdout)
        metrics = load_json(self.output_dir / "diagnostic_metrics.json")
        rows = {row["case_id"]: row for row in metrics["cases"]}

        self.assertEqual(rows["self_test_only"]["statuses"]["artifact_test"], "CERTIFIED_DONE")
        self.assertEqual(rows["self_test_only"]["statuses"]["policy_engine"], "PROVISIONAL_DONE")
        self.assertEqual(rows["p2_weak"]["statuses"]["provenance_gate"], "CERTIFIED_DONE")
        self.assertEqual(rows["p2_weak"]["statuses"]["policy_engine"], "PROVISIONAL_DONE")
        self.assertEqual(rows["p2_strong"]["statuses"]["policy_engine"], "CERTIFIED_DONE")
        self.assertEqual(rows["missing_verifier"]["statuses"]["policy_engine"], "NOT_DONE")

    def test_v04_doc_locks_small_diagnostic_boundary(self):
        doc = (ROOT / "docs" / "V0_4_DIAGNOSTIC_EVALUATION.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("small diagnostic evaluation", doc)
        self.assertIn("false CERTIFIED_DONE rate", doc)
        self.assertIn("does not add", doc)
        self.assertIn("Pi integration", doc)
        self.assertIn("SWE-bench", doc)


if __name__ == "__main__":
    unittest.main()
