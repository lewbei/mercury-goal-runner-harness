import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / ".agentic-pi" / "diagnostics" / "trajectory_evaluation" / "cases"
MANIFEST = ROOT / ".agentic-pi" / "diagnostics" / "trajectory_evaluation" / "manifest.json"
TOOL_USE_AUDIT = ROOT / ".agentic-pi" / "evaluation" / "tool_use_audit.py"
SESSION_TRACE_SCORER = ROOT / ".agentic-pi" / "evaluation" / "session_trace_scorer.py"
RUNNER = ROOT / ".agentic-pi" / "diagnostics" / "trajectory_evaluation" / "run_trajectory_evaluation.py"


EXPECTED_CASES = {
    "correct_trajectory": ("PASS", "pi_smoke_one_bash_p2_strong"),
    "duplicate_certifier_call": ("FAIL", "pi_smoke_one_bash_p2_strong"),
    "manual_status_write": ("FAIL", "pi_smoke_one_bash_p2_strong"),
    "missing_status_read": ("FAIL", "pi_smoke_one_bash_p2_strong"),
    "unsafe_deletion": ("FAIL", "diagnostic_eval_p2_strong"),
    "wrong_command_order": ("FAIL", "pi_smoke_one_bash_p2_strong"),
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(instance, schema_name):
    validator = load_module(
        "validate_schema_for_trajectory_tests",
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


class TrajectoryEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool_use_audit = load_module("tool_use_audit_for_tests", TOOL_USE_AUDIT)
        cls.session_trace_scorer = load_module("session_trace_scorer_for_tests", SESSION_TRACE_SCORER)

    def test_case_inventory_is_exact(self):
        self.assertEqual(
            sorted(path.stem for path in CASES_DIR.glob("*.jsonl")),
            sorted(EXPECTED_CASES),
        )
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "v1.6")
        self.assertEqual(
            {
                case_id: (case["expected_trajectory_status"], case["run_id"])
                for case_id, case in manifest["cases"].items()
            },
            EXPECTED_CASES,
        )

    def test_correct_trajectory_scores_pass_and_cannot_certify(self):
        report = self.tool_use_audit.audit_tool_use(
            CASES_DIR / "correct_trajectory.jsonl",
            "pi_smoke_one_bash_p2_strong",
        )

        self.assertEqual(report["trajectory_status"], "PASS", report)
        self.assertFalse(report["can_certify_done"])
        self.assertEqual(report["final_status_authority"], "certifier_only")
        self.assertTrue(report["metrics"]["tool_selection_correct"])
        self.assertTrue(report["metrics"]["tool_argument_correct"])
        self.assertTrue(report["metrics"]["tool_order_correct"])
        self.assertGreaterEqual(report["metrics"]["score"], 90)
        self.assertEqual(validate(report, "tool_use_audit.schema.json"), [])

    def test_negative_trajectory_cases_fail_with_expected_metrics(self):
        expected = {
            "duplicate_certifier_call": ("duplicate_certifier_invocations", 1),
            "manual_status_write": ("manual_status_write_attempt", True),
            "missing_status_read": ("missing_status_read", True),
            "unsafe_deletion": ("unsafe_tool_attempts", 1),
            "wrong_command_order": ("tool_order_correct", False),
        }

        for case_id, (metric, expected_value) in expected.items():
            with self.subTest(case=case_id):
                _, run_id = EXPECTED_CASES[case_id]
                report = self.tool_use_audit.audit_tool_use(CASES_DIR / f"{case_id}.jsonl", run_id)

                self.assertEqual(report["trajectory_status"], "FAIL", report)
                self.assertFalse(report["can_certify_done"])
                if isinstance(expected_value, bool):
                    self.assertIs(report["metrics"][metric], expected_value)
                else:
                    self.assertGreaterEqual(report["metrics"][metric], expected_value)
                self.assertEqual(validate(report, "tool_use_audit.schema.json"), [])

    def test_session_trace_scorer_aggregates_without_certifying(self):
        reports = [
            self.tool_use_audit.audit_tool_use(
                CASES_DIR / "correct_trajectory.jsonl",
                "pi_smoke_one_bash_p2_strong",
            ),
            self.tool_use_audit.audit_tool_use(
                CASES_DIR / "duplicate_certifier_call.jsonl",
                "pi_smoke_one_bash_p2_strong",
            ),
        ]
        score = self.session_trace_scorer.score_reports(reports)

        self.assertEqual(score["trajectory_status"], "FAIL")
        self.assertFalse(score["can_certify_done"])
        self.assertEqual(score["final_status_authority"], "certifier_only")
        self.assertEqual(score["case_count"], 2)
        self.assertEqual(score["failed_count"], 1)
        self.assertEqual(validate(score, "trajectory_score.schema.json"), [])

    def test_cli_exit_codes_match_trajectory_status(self):
        passing = run_python(
            str(TOOL_USE_AUDIT),
            str(CASES_DIR / "correct_trajectory.jsonl"),
            "--run-id",
            "pi_smoke_one_bash_p2_strong",
        )
        failing = run_python(
            str(TOOL_USE_AUDIT),
            str(CASES_DIR / "wrong_command_order.jsonl"),
            "--run-id",
            "pi_smoke_one_bash_p2_strong",
        )

        self.assertEqual(passing.returncode, 0, passing.stdout)
        self.assertIn('"trajectory_status": "PASS"', passing.stdout)
        self.assertEqual(failing.returncode, 1, failing.stdout)
        self.assertIn('"trajectory_status": "FAIL"', failing.stdout)

    def test_trajectory_diagnostic_runner_outputs_expected_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_python(str(RUNNER), "--output-dir", tmp)
            self.assertEqual(result.returncode, 0, result.stdout)

            metrics = json.loads((Path(tmp) / "trajectory_metrics.json").read_text(encoding="utf-8"))
            report = (Path(tmp) / "trajectory_report.md").read_text(encoding="utf-8")

        self.assertEqual(metrics["version"], "v1.6")
        self.assertEqual(metrics["status_match_rate"], 1.0)
        self.assertEqual(metrics["unsafe_trajectory_count"], 5)
        self.assertFalse(metrics["can_certify_done"])
        self.assertIn("Trajectory-Level Evaluation Report", report)
        self.assertIn("does not certify DONE", report)

    def test_v16_doc_locks_trajectory_boundary(self):
        doc = (ROOT / "docs" / "V1_6_TRAJECTORY_LEVEL_EVALUATION.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "V1_ROADMAP_STRATEGY_REPLANNING_MEMORY.md").read_text(encoding="utf-8")

        self.assertIn("TRAJECTORY-LEVEL EVALUATION IMPLEMENTED", doc)
        self.assertIn(".agentic-pi/evaluation/trajectory_metrics.py", doc)
        self.assertIn(".agentic-pi/evaluation/tool_use_audit.py", doc)
        self.assertIn(".agentic-pi/evaluation/session_trace_scorer.py", doc)
        self.assertIn("duplicate_certifier_call -> FAIL", doc)
        self.assertIn("wrong_command_order -> FAIL", doc)
        self.assertIn("cannot certify DONE", doc)
        self.assertIn("v1.6 Trajectory-Level Evaluation", roadmap)
        self.assertIn("IMPLEMENTED", roadmap)


if __name__ == "__main__":
    unittest.main()
