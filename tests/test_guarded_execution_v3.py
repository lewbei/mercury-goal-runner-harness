import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_REPORT = ROOT / ".agentic-runs" / "stage3_runtime_preflight" / "stage3_runtime_preflight_report_v1.json"
PREFLIGHT_TOOL = ".agentic-pi/runtime/stage3_runtime_preflight.py"
GUARDED_EXECUTION = ".agentic-pi/runtime/guarded_execution_v3.py"
DEFAULT_INITIAL = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v3_initial_plan.json"
DEFAULT_REPAIR = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v3_repair_plan.json"
DEFAULT_EXPECTED = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v3_expected_artifacts.json"


FINAL_PATHS = [
    "artifacts/guarded_execution_v3_summary.txt",
    "artifacts/guarded_execution_v3_observation.txt",
    "artifacts/guarded_execution_v3_boundary.txt",
]


def run_python(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_execution_module():
    spec = importlib.util.spec_from_file_location("guarded_execution_v3", ROOT / GUARDED_EXECUTION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.path.insert(0, str((ROOT / ".agentic-pi" / "runtime").resolve()))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class GuardedExecutionV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = run_python(PREFLIGHT_TOOL)
        if result.returncode != 0:
            raise AssertionError(result.stdout)

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="guarded_execution_v3_test_"))
        self.preflight = self.tmpdir / "stage3_runtime_preflight_report_v1.json"
        self.initial = self.tmpdir / "initial_plan.json"
        self.repair = self.tmpdir / "repair_plan.json"
        self.expected = self.tmpdir / "expected_artifacts.json"
        self.run_id = f"guarded_execution_v3_test_{self.tmpdir.name.split('_')[-1]}"
        self.run_dir = ROOT / ".agentic-runs" / self.run_id
        self.output = self.tmpdir / "guarded_execution_v3_report.json"
        self.ledger = self.tmpdir / "guarded_execution_v3_ledger.json"
        write_json(self.preflight, load_json(PREFLIGHT_REPORT))
        write_json(self.initial, load_json(DEFAULT_INITIAL))
        write_json(self.repair, load_json(DEFAULT_REPAIR))
        write_json(self.expected, load_json(DEFAULT_EXPECTED))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def run_execution(self, *extra):
        return run_python(
            GUARDED_EXECUTION,
            "--preflight-report", str(self.preflight),
            "--initial-plan", str(self.initial),
            "--repair-plan", str(self.repair),
            "--expected-artifacts", str(self.expected),
            "--run-id", self.run_id,
            "--output", str(self.output),
            "--ledger-output", str(self.ledger),
            *extra,
        )

    def assert_no_final_artifacts_written(self):
        for rel_path in FINAL_PATHS:
            self.assertFalse((self.run_dir / rel_path).exists(), rel_path)
        self.assertFalse((self.run_dir / "artifacts" / "guarded_execution_v3_wrong_observation.txt").exists())

    def test_guarded_execution_v3_denies_initial_plan_repairs_once_and_executes(self):
        result = self.run_execution()
        report = load_json(self.output)
        ledger = load_json(self.ledger)
        repair_request = load_json(self.run_dir / "artifacts" / "guarded_execution_v3_repair_request.json")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V3_PASS")
        self.assertFalse(report["repair_loop"]["initial_plan_valid"])
        self.assertFalse(report["repair_loop"]["initial_plan_executed"])
        self.assertTrue(report["repair_loop"]["repair_request_written"])
        self.assertEqual(report["repair_loop"]["repair_attempt_count"], 1)
        self.assertTrue(report["repair_loop"]["repaired_plan_valid"])
        self.assertEqual(ledger["action_count_executed"], 3)
        self.assertEqual(len(ledger["initial_denied_actions"]), 3)
        self.assertEqual([item["status"] for item in ledger["final_action_order"]], ["EXECUTED", "EXECUTED", "EXECUTED"])
        self.assertIn("does not match expected_artifacts", "\n".join(repair_request["violations"]))
        self.assertFalse((self.run_dir / "artifacts" / "guarded_execution_v3_wrong_observation.txt").exists())
        for rel_path in FINAL_PATHS:
            artifact = self.run_dir / rel_path
            self.assertTrue(artifact.is_file(), artifact)
            self.assertIn(rel_path, ledger["artifact_hashes"])
        self.assertFalse(ledger["goal_execution_attempted"])
        self.assertFalse(ledger["arbitrary_command_attempted"])
        self.assertFalse(ledger["protected_status_write_attempted"])
        self.assertFalse(ledger["can_certify_done"])
        self.assertEqual(ledger["status_authority"], "certifier_only")

    def test_guarded_execution_v3_refuses_missing_preflight_without_repair_request(self):
        self.preflight.unlink()

        result = self.run_execution()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("preflight report missing", result.stdout)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.ledger.exists())
        self.assertFalse((self.run_dir / "artifacts" / "guarded_execution_v3_repair_request.json").exists())
        self.assert_no_final_artifacts_written()

    def test_guarded_execution_v3_refuses_failed_preflight_without_repair_request(self):
        preflight = load_json(self.preflight)
        preflight["status"] = "STAGE3_RUNTIME_PREFLIGHT_FAIL"
        preflight["runtime_preflight"]["may_consume_planning_evidence"] = False
        write_json(self.preflight, preflight)

        result = self.run_execution()
        report = load_json(self.output)
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V3_FAIL")
        self.assertFalse(ledger["repair_request_written"])
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertFalse((self.run_dir / "artifacts" / "guarded_execution_v3_repair_request.json").exists())
        self.assert_no_final_artifacts_written()

    def test_guarded_execution_v3_refuses_missing_repair_plan(self):
        self.repair.unlink()

        result = self.run_execution()
        report = load_json(self.output)
        ledger = load_json(self.ledger)
        repair_request = load_json(self.run_dir / "artifacts" / "guarded_execution_v3_repair_request.json")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V3_FAIL")
        self.assertTrue(ledger["repair_request_written"])
        self.assertEqual(ledger["repair_attempt_count"], 0)
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertIn("does not match expected_artifacts", "\n".join(repair_request["violations"]))
        self.assert_no_final_artifacts_written()

    def test_guarded_execution_v3_refuses_multiple_repair_attempts(self):
        repair = load_json(self.repair)
        repair["repair_attempts"].append(repair["repair_attempts"][0])
        write_json(self.repair, repair)

        result = self.run_execution()
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(ledger["multiple_repair_attempts_denied"])
        self.assertEqual(ledger["repair_attempt_count"], 2)
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertIn("multiple repair attempts are not allowed", result.stdout)
        self.assert_no_final_artifacts_written()

    def test_guarded_execution_v3_refuses_repaired_protected_path(self):
        repair = load_json(self.repair)
        repair["repair_attempts"][0]["plan"]["actions"][1]["artifact_path"] = "artifacts/final_status.json"
        write_json(self.repair, repair)

        result = self.run_execution()
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(ledger["protected_status_write_attempted"])
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertFalse((self.run_dir / "artifacts" / "final_status.json").exists())
        self.assert_no_final_artifacts_written()

    def test_guarded_execution_v3_refuses_repaired_command_shape(self):
        repair = load_json(self.repair)
        repair["repair_attempts"][0]["plan"]["actions"][0]["command"] = "python -c print('unsafe')"
        write_json(self.repair, repair)

        result = self.run_execution()
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(ledger["arbitrary_command_attempted"])
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertIn("raw command", result.stdout)
        self.assert_no_final_artifacts_written()

    def test_guarded_execution_v3_refuses_repaired_over_budget_plan(self):
        repair = load_json(self.repair)
        plan = repair["repair_attempts"][0]["plan"]
        expected = load_json(self.expected)
        for index in range(3, 6):
            artifact_id = f"A.GE3_EXTRA_{index}"
            path = f"artifacts/guarded_execution_v3_extra_{index}.txt"
            plan["actions"].append({
                "action_id": f"A.WRITE_GE3_EXTRA_{index}",
                "action_type": "write_text_artifact",
                "artifact_id": artifact_id,
                "artifact_path": path,
                "content": f"extra repaired artifact {index} should trigger over budget rejection",
            })
            expected["artifacts"].append({
                "artifact_id": artifact_id,
                "expected_path": path,
                "required": True,
                "allowed_actions": ["write_text_artifact"],
                "min_size_bytes": 10,
                "max_size_bytes": 1000,
            })
        write_json(self.repair, repair)
        write_json(self.expected, expected)

        result = self.run_execution()
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("plan action count exceeds budget", result.stdout)
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assert_no_final_artifacts_written()

    def test_guarded_execution_v3_refuses_repaired_final_status_language(self):
        repair = load_json(self.repair)
        repair["repair_attempts"][0]["plan"]["actions"][2]["content"] = "This tries to claim certified done inside repaired content."
        write_json(self.repair, repair)

        result = self.run_execution()
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(ledger["final_status_language_denied"])
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertIn("final-status authority language", result.stdout)
        self.assert_no_final_artifacts_written()

    def test_guarded_execution_v3_refuses_initial_plan_that_needs_no_repair(self):
        repaired_plan = load_json(self.repair)["repair_attempts"][0]["plan"]
        write_json(self.initial, repaired_plan)

        result = self.run_execution()
        report = load_json(self.output)
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V3_FAIL")
        self.assertTrue(ledger["initial_plan_valid"])
        self.assertFalse(ledger["repair_request_written"])
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assert_no_final_artifacts_written()

    def test_guarded_execution_v3_refuses_protected_report_ledger_or_repair_request_output(self):
        protected_report = self.run_execution("--output", str(self.tmpdir / "policy_decision.json"))
        self.assertNotEqual(protected_report.returncode, 0, protected_report.stdout)
        self.assertIn("refusing to write protected status artifact", protected_report.stdout)

        protected_ledger = self.run_execution("--ledger-output", str(self.tmpdir / "certification.json"))
        self.assertNotEqual(protected_ledger.returncode, 0, protected_ledger.stdout)
        self.assertIn("refusing to write protected status artifact", protected_ledger.stdout)

        protected_repair = self.run_execution("--repair-request-output", str(self.run_dir / "artifacts" / "final_status.json"))
        self.assertNotEqual(protected_repair.returncode, 0, protected_repair.stdout)
        self.assertIn("refusing to write protected status artifact", protected_repair.stdout)

    def test_guarded_execution_v3_report_validator_rejects_goal_execution_claim(self):
        module = load_execution_module()
        report, ledger, repair_request, _ = module.build_execution_report(
            load_json(self.preflight),
            self.preflight,
            load_json(self.initial),
            self.initial,
            load_json(self.repair),
            self.repair,
            [],
            load_json(self.expected),
            self.expected,
            self.run_id,
            "bounded_repair_then_artifact_writes",
        )
        report["runtime_execution"]["goal_execution_attempted"] = True

        errors = module.validate_execution_report(report, ledger, repair_request)

        self.assertIn("runtime_execution.goal_execution_attempted must not be true", errors)

    def test_guarded_execution_v3_tool_has_no_live_model_or_command_runner_calls(self):
        combined = (ROOT / GUARDED_EXECUTION).read_text(encoding="utf-8").lower()
        for token in ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
