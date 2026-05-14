import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".agentic-pi" / "runtime"
PREFLIGHT = ".agentic-pi/runtime/planning_efficiency_v2_preflight.py"
STAGE3_PREFLIGHT = ".agentic-pi/runtime/stage3_runtime_preflight.py"
GUARDED_EXECUTION_V2 = ".agentic-pi/runtime/guarded_execution_v2.py"
HARDENING = ".agentic-pi/runtime/planning_efficiency_v2_1_hardening.py"
DEFAULT_GOAL = RUNTIME / "planning_efficiency_v2_goal.json"


def run_python(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_runtime_module(module_name: str):
    sys.path.insert(0, str(RUNTIME.resolve()))
    try:
        spec = importlib.util.spec_from_file_location(module_name, RUNTIME / f"{module_name}.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class PlanningEfficiencyV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="planning_efficiency_v2_test_"))
        self.goal = self.tmpdir / "goal.json"
        self.plan = self.tmpdir / "planning_efficiency_v2_plan.json"
        self.expected = self.tmpdir / "planning_efficiency_v2_expected_artifacts.json"
        self.compile_report = self.tmpdir / "planning_efficiency_v2_compile_report.json"
        self.lint_report = self.tmpdir / "planning_efficiency_v2_lint_report.json"
        self.preflight_report = self.tmpdir / "planning_efficiency_v2_preflight_report.json"
        self.hardening_work_dir = self.tmpdir / "planning_efficiency_v2_1_hardening"
        self.hardening_report = self.tmpdir / "planning_efficiency_v2_1_hardening_report.json"
        write_json(self.goal, load_json(DEFAULT_GOAL))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        shutil.rmtree(ROOT / ".agentic-runs" / "planning_efficiency_v2_unittest_execution", ignore_errors=True)

    def run_preflight(self):
        return run_python(
            PREFLIGHT,
            "--goal", str(self.goal),
            "--plan-output", str(self.plan),
            "--expected-output", str(self.expected),
            "--compile-report-output", str(self.compile_report),
            "--lint-report-output", str(self.lint_report),
            "--output", str(self.preflight_report),
        )

    def test_preflight_compiles_lints_hashes_and_does_not_execute(self):
        result = self.run_preflight()
        report = load_json(self.preflight_report)
        plan = load_json(self.plan)
        expected = load_json(self.expected)
        compile_report = load_json(self.compile_report)
        lint_report = load_json(self.lint_report)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_EFFICIENCY_V2_PREFLIGHT_PASS")
        self.assertEqual(compile_report["status"], "PLAN_COMPILE_PASS")
        self.assertEqual(lint_report["status"], "PLAN_LINT_PASS")
        self.assertEqual(len(plan["actions"]), 3)
        self.assertEqual(len(expected["artifacts"]), 3)
        self.assertTrue(report["execution_gate"]["may_pass_plan_to_guarded_execution"])
        self.assertFalse(report["runtime_execution"]["guarded_execution_invoked"])
        self.assertFalse(report["runtime_execution"]["plan_execution_attempted"])
        self.assertFalse(report["runtime_execution"]["can_certify_done"])
        self.assertIn("plan", report["generated_hashes"])
        self.assertTrue(any(check["check_id"] == "deterministic_replay_hashes_match" and check["status"] == "PASS" for check in report["criteria"]))
        self.assertTrue(any(check["check_id"] == "final_status_enum_values_absent" and check["status"] == "PASS" for check in report["criteria"]))
        self.assertTrue(any(check["check_id"] == "protected_status_artifact_names_absent" and check["status"] == "PASS" for check in report["criteria"]))

    def test_generated_plan_can_feed_guarded_execution_v2_after_stage3_preflight(self):
        result = self.run_preflight()
        self.assertEqual(result.returncode, 0, result.stdout)
        stage3_report = self.tmpdir / "stage3_runtime_preflight_report_v1.json"
        execution_report = self.tmpdir / "guarded_execution_v2_report.json"
        ledger = self.tmpdir / "guarded_execution_v2_ledger.json"
        stage3 = run_python(STAGE3_PREFLIGHT, "--output", str(stage3_report))
        self.assertEqual(stage3.returncode, 0, stage3.stdout)

        execution = run_python(
            GUARDED_EXECUTION_V2,
            "--preflight-report", str(stage3_report),
            "--plan", str(self.plan),
            "--expected-artifacts", str(self.expected),
            "--planning-preflight-report", str(self.preflight_report),
            "--run-id", "planning_efficiency_v2_unittest_execution",
            "--output", str(execution_report),
            "--ledger-output", str(ledger),
        )
        report = load_json(execution_report)
        self.assertEqual(execution.returncode, 0, execution.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V2_PASS")
        self.assertEqual(report["runtime_execution"]["safe_artifacts_written"], 3)
        self.assertTrue(report["runtime_execution"]["planning_preflight_checked"])
        self.assertFalse(report["runtime_execution"]["goal_execution_attempted"])
        self.assertEqual(report["runtime_execution"]["status_authority"], "certifier_only")
        self.assertTrue(any(check["check_id"] == "planning_efficiency_v2_preflight_usable" and check["status"] == "PASS" for check in report["criteria"]))

    def test_guarded_execution_v2_rejects_mismatched_planning_preflight_binding(self):
        result = self.run_preflight()
        self.assertEqual(result.returncode, 0, result.stdout)
        stage3_report = self.tmpdir / "stage3_runtime_preflight_report_v1.json"
        execution_report = self.tmpdir / "guarded_execution_v2_report.json"
        ledger = self.tmpdir / "guarded_execution_v2_ledger.json"
        stage3 = run_python(STAGE3_PREFLIGHT, "--output", str(stage3_report))
        self.assertEqual(stage3.returncode, 0, stage3.stdout)
        bad_preflight = load_json(self.preflight_report)
        bad_preflight["execution_gate"]["guarded_execution_inputs"]["plan"] = "artifacts/not_the_generated_plan.json"
        bad_preflight_path = self.tmpdir / "bad_planning_preflight_report.json"
        write_json(bad_preflight_path, bad_preflight)

        execution = run_python(
            GUARDED_EXECUTION_V2,
            "--preflight-report", str(stage3_report),
            "--plan", str(self.plan),
            "--expected-artifacts", str(self.expected),
            "--planning-preflight-report", str(bad_preflight_path),
            "--run-id", "planning_efficiency_v2_unittest_execution",
            "--output", str(execution_report),
            "--ledger-output", str(ledger),
        )
        report = load_json(execution_report)
        ledger_report = load_json(ledger)
        self.assertNotEqual(execution.returncode, 0, execution.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V2_FAIL")
        self.assertEqual(report["runtime_execution"]["safe_artifacts_written"], 0)
        self.assertTrue(report["runtime_execution"]["planning_preflight_checked"])
        self.assertEqual(ledger_report["action_count_executed"], 0)
        self.assertTrue(any(check["check_id"] == "planning_efficiency_v2_preflight_usable" and check["status"] == "FAIL" for check in report["criteria"]))

    def test_guarded_execution_v2_rejects_post_preflight_plan_tampering(self):
        result = self.run_preflight()
        self.assertEqual(result.returncode, 0, result.stdout)
        stage3_report = self.tmpdir / "stage3_runtime_preflight_report_v1.json"
        execution_report = self.tmpdir / "guarded_execution_v2_report.json"
        ledger = self.tmpdir / "guarded_execution_v2_ledger.json"
        stage3 = run_python(STAGE3_PREFLIGHT, "--output", str(stage3_report))
        self.assertEqual(stage3.returncode, 0, stage3.stdout)
        tampered_plan = load_json(self.plan)
        tampered_plan["actions"][0]["content"] = "Tampered after preflight but still shaped as a safe artifact."
        write_json(self.plan, tampered_plan)

        execution = run_python(
            GUARDED_EXECUTION_V2,
            "--preflight-report", str(stage3_report),
            "--plan", str(self.plan),
            "--expected-artifacts", str(self.expected),
            "--planning-preflight-report", str(self.preflight_report),
            "--run-id", "planning_efficiency_v2_unittest_execution",
            "--output", str(execution_report),
            "--ledger-output", str(ledger),
        )
        report = load_json(execution_report)
        ledger_report = load_json(ledger)
        self.assertNotEqual(execution.returncode, 0, execution.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V2_FAIL")
        self.assertEqual(report["runtime_execution"]["safe_artifacts_written"], 0)
        self.assertEqual(ledger_report["action_count_executed"], 0)
        planning_check = next(check for check in report["criteria"] if check["check_id"] == "planning_efficiency_v2_preflight_usable")
        self.assertEqual(planning_check["status"], "FAIL")
        self.assertTrue(any("plan hash mismatch" in item for item in planning_check["actual"]))

    def test_preflight_blocks_token_like_content_before_writing_plan_outputs(self):
        goal = load_json(self.goal)
        goal["artifact_specs"][1]["content"] = "api_key should never appear in generated planning artifacts"
        write_json(self.goal, goal)

        result = self.run_preflight()
        report = load_json(self.preflight_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_EFFICIENCY_V2_PREFLIGHT_FAIL")
        self.assertTrue(any(check["check_id"] == "sensitive_token_patterns_absent" and check["status"] == "FAIL" for check in report["criteria"]))
        self.assertTrue(any(item["code"] == "TOKEN_PATTERN" for item in report["repair_hints"]))
        self.assertFalse(self.plan.exists())
        self.assertFalse(self.expected.exists())
        self.assertFalse(self.lint_report.exists())
        self.assertTrue(self.compile_report.exists())
        self.assertFalse(report["runtime_execution"]["plan_execution_attempted"])

    def test_preflight_blocks_final_status_enum_leak_before_writing_plan_outputs(self):
        goal = load_json(self.goal)
        goal["artifact_specs"][1]["artifact_id"] = "A.CERTIFIED_DONE"
        write_json(self.goal, goal)

        result = self.run_preflight()
        report = load_json(self.preflight_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_EFFICIENCY_V2_PREFLIGHT_FAIL")
        self.assertTrue(any(check["check_id"] == "final_status_enum_values_absent" and check["status"] == "FAIL" for check in report["criteria"]))
        self.assertTrue(any(item["code"] == "FINAL_STATUS_ENUM_LEAK" for item in report["repair_hints"]))
        self.assertFalse(self.plan.exists())
        self.assertFalse(self.expected.exists())
        self.assertFalse(self.lint_report.exists())

    def test_preflight_blocks_protected_status_artifact_name_leak(self):
        goal = load_json(self.goal)
        goal["artifact_specs"][2]["artifact_id"] = "Final_Status.Json"
        write_json(self.goal, goal)

        result = self.run_preflight()
        report = load_json(self.preflight_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_EFFICIENCY_V2_PREFLIGHT_FAIL")
        self.assertTrue(any(check["check_id"] == "protected_status_artifact_names_absent" and check["status"] == "FAIL" for check in report["criteria"]))
        self.assertTrue(any(item["code"] == "PROTECTED_STATUS_ARTIFACT_NAME" for item in report["repair_hints"]))
        self.assertFalse(self.plan.exists())
        self.assertFalse(self.expected.exists())
        self.assertFalse(self.lint_report.exists())

    def test_preflight_blocks_mixed_case_protected_output_path(self):
        protected_plan_output = self.tmpdir / "Final_Status.Json"

        result = run_python(
            PREFLIGHT,
            "--goal", str(self.goal),
            "--plan-output", str(protected_plan_output),
            "--expected-output", str(self.expected),
            "--compile-report-output", str(self.compile_report),
            "--lint-report-output", str(self.lint_report),
            "--output", str(self.preflight_report),
        )
        report = load_json(self.preflight_report)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_EFFICIENCY_V2_PREFLIGHT_FAIL")
        self.assertTrue(any(check["check_id"] == "output_paths_unprotected" and check["status"] == "FAIL" for check in report["criteria"]))
        self.assertFalse(protected_plan_output.exists())

    def test_same_goal_yields_same_generated_hashes_across_preflights(self):
        first = self.run_preflight()
        first_hashes = load_json(self.preflight_report)["generated_hashes"]
        self.assertEqual(first.returncode, 0, first.stdout)
        second = self.run_preflight()
        second_hashes = load_json(self.preflight_report)["generated_hashes"]
        self.assertEqual(second.returncode, 0, second.stdout)
        self.assertEqual(first_hashes, second_hashes)

    def test_preflight_validator_rejects_execution_claims(self):
        module = load_runtime_module("planning_efficiency_v2_preflight")
        plan, expected, compile_report, lint_report, report = module.build_preflight(
            load_json(self.goal),
            self.plan,
            self.expected,
            self.compile_report,
            self.lint_report,
            self.preflight_report,
        )
        report["runtime_execution"]["guarded_execution_invoked"] = True
        report["runtime_execution"]["can_certify_done"] = True

        errors = module.validate_preflight_report(report)
        self.assertIn("runtime_execution.guarded_execution_invoked must be false", errors)
        self.assertIn("runtime_execution.can_certify_done must be false", errors)

    def test_v21_hardening_runs_three_byte_stable_preflights(self):
        result = run_python(
            HARDENING,
            "--goal", str(self.goal),
            "--work-dir", str(self.hardening_work_dir),
            "--output", str(self.hardening_report),
        )
        report = load_json(self.hardening_report)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "PLANNING_EFFICIENCY_V2_1_HARDENING_PASS")
        self.assertEqual(report["iteration_count"], 3)
        self.assertTrue(any(check["check_id"] == "three_run_byte_stability" and check["status"] == "PASS" for check in report["criteria"]))
        self.assertTrue(any(check["check_id"] == "protected_status_artifacts_not_created" and check["status"] == "PASS" for check in report["criteria"]))
        self.assertTrue(any(check["check_id"] == "final_status_enum_values_absent" and check["status"] == "PASS" for check in report["criteria"]))
        self.assertFalse(report["runtime_execution"]["can_certify_done"])
        protected_names = {"final_status.json", "final_status.md", "certification.json", "policy_decision.json"}
        created_protected = [path for path in self.hardening_work_dir.rglob("*") if path.name in protected_names]
        self.assertEqual(created_protected, [])

    def test_preflight_tools_have_no_live_model_or_command_runner_calls(self):
        text = (ROOT / PREFLIGHT).read_text(encoding="utf-8").lower()
        for token in ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]:
            with self.subTest(token=token):
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
