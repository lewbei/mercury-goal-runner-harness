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
GUARDED_EXECUTION = ".agentic-pi/runtime/guarded_execution_v2.py"
DEFAULT_PLAN = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v2_plan.json"
DEFAULT_EXPECTED = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v2_expected_artifacts.json"


def run_python(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_execution_module():
    spec = importlib.util.spec_from_file_location("guarded_execution_v2", ROOT / GUARDED_EXECUTION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GuardedExecutionV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = run_python(PREFLIGHT_TOOL)
        if result.returncode != 0:
            raise AssertionError(result.stdout)

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="guarded_execution_v2_test_"))
        self.preflight = self.tmpdir / "stage3_runtime_preflight_report_v1.json"
        self.plan = self.tmpdir / "plan.json"
        self.expected = self.tmpdir / "expected_artifacts.json"
        self.run_id = f"guarded_execution_v2_test_{self.tmpdir.name.split('_')[-1]}"
        self.run_dir = ROOT / ".agentic-runs" / self.run_id
        self.output = self.tmpdir / "guarded_execution_v2_report.json"
        self.ledger = self.tmpdir / "guarded_execution_v2_ledger.json"
        write_json(self.preflight, load_json(PREFLIGHT_REPORT))
        write_json(self.plan, load_json(DEFAULT_PLAN))
        write_json(self.expected, load_json(DEFAULT_EXPECTED))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def run_execution(self, *extra):
        return run_python(
            GUARDED_EXECUTION,
            "--preflight-report", str(self.preflight),
            "--plan", str(self.plan),
            "--expected-artifacts", str(self.expected),
            "--run-id", self.run_id,
            "--output", str(self.output),
            "--ledger-output", str(self.ledger),
            *extra,
        )

    def assert_no_default_artifacts_written(self):
        for filename in [
            "guarded_execution_v2_summary.txt",
            "guarded_execution_v2_observation.txt",
            "guarded_execution_v2_boundary.txt",
        ]:
            self.assertFalse((self.run_dir / "artifacts" / filename).exists(), filename)

    def test_guarded_execution_v2_writes_declared_bounded_plan_and_ledger(self):
        result = self.run_execution()
        report = load_json(self.output)
        ledger = load_json(self.ledger)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V2_PASS")
        self.assertEqual(ledger["status"], "GUARDED_EXECUTION_V2_PASS")
        self.assertEqual(report["runtime_execution"]["action_count_executed"], 3)
        self.assertEqual(ledger["action_count_executed"], 3)
        self.assertEqual(ledger["action_count_denied"], 0)
        self.assertEqual([item["status"] for item in ledger["action_order"]], ["EXECUTED", "EXECUTED", "EXECUTED"])
        for rel_path, digest in ledger["artifact_hashes"].items():
            artifact = self.run_dir / rel_path
            self.assertTrue(artifact.is_file(), artifact)
            self.assertEqual(digest, report["runtime_execution"].get("artifact_hashes", ledger["artifact_hashes"]).get(rel_path, digest))
        self.assertFalse(report["runtime_execution"]["goal_execution_attempted"])
        self.assertFalse(report["runtime_execution"]["arbitrary_command_attempted"])
        self.assertFalse(report["runtime_execution"]["protected_status_write_attempted"])
        self.assertFalse(report["runtime_execution"]["can_certify_done"])
        self.assertEqual(report["runtime_execution"]["status_authority"], "certifier_only")

    def test_guarded_execution_v2_refuses_missing_preflight_without_artifact_write(self):
        self.preflight.unlink()

        result = self.run_execution()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("preflight report missing", result.stdout)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.ledger.exists())
        self.assert_no_default_artifacts_written()

    def test_guarded_execution_v2_refuses_failed_preflight(self):
        preflight = load_json(self.preflight)
        preflight["status"] = "STAGE3_RUNTIME_PREFLIGHT_FAIL"
        preflight["runtime_preflight"]["may_consume_planning_evidence"] = False
        write_json(self.preflight, preflight)

        result = self.run_execution()
        report = load_json(self.output)
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V2_FAIL")
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertEqual(ledger["action_count_denied"], 3)
        self.assertIn("preflight_usable", result.stdout)
        self.assert_no_default_artifacts_written()

    def test_guarded_execution_v2_refuses_undeclared_artifact_path(self):
        plan = load_json(self.plan)
        plan["actions"][1]["artifact_path"] = "artifacts/not_declared.txt"
        write_json(self.plan, plan)

        result = self.run_execution()
        report = load_json(self.output)
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V2_FAIL")
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertTrue(any("does not match expected_artifacts" in item["reason"] for item in ledger["denied_actions"]))
        self.assertFalse((self.run_dir / "artifacts" / "not_declared.txt").exists())

    def test_guarded_execution_v2_refuses_missing_required_expected_artifact(self):
        plan = load_json(self.plan)
        plan["actions"] = plan["actions"][:2]
        write_json(self.plan, plan)

        result = self.run_execution()
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertTrue(any("required expected artifact is not produced" in item["reason"] for item in ledger["denied_actions"]))
        self.assert_no_default_artifacts_written()

    def test_guarded_execution_v2_refuses_protected_artifact_path(self):
        plan = load_json(self.plan)
        expected = load_json(self.expected)
        plan["actions"][0]["artifact_path"] = "artifacts/final_status.json"
        expected["artifacts"][0]["expected_path"] = "artifacts/final_status.json"
        write_json(self.plan, plan)
        write_json(self.expected, expected)

        result = self.run_execution()
        report = load_json(self.output)
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V2_FAIL")
        self.assertTrue(ledger["protected_status_write_attempted"])
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertFalse((self.run_dir / "artifacts" / "final_status.json").exists())

    def test_guarded_execution_v2_refuses_arbitrary_command_shape(self):
        plan = load_json(self.plan)
        plan["actions"][0]["command"] = "python -c print('unsafe')"
        write_json(self.plan, plan)

        result = self.run_execution()
        report = load_json(self.output)
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V2_FAIL")
        self.assertTrue(ledger["arbitrary_command_attempted"])
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertIn("raw command", result.stdout)

    def test_guarded_execution_v2_refuses_under_budget_plan(self):
        plan = {"schema_version": "guarded_execution_v2_plan_v1", "plan_id": "too_few", "actions": []}
        expected = {"schema_version": "guarded_execution_v2_expected_artifacts_v1", "artifacts": []}
        for index in range(2):
            artifact_id = f"A.SMALL_{index}"
            path = f"artifacts/small_{index}.txt"
            plan["actions"].append({
                "action_id": f"A.WRITE_SMALL_{index}",
                "action_type": "write_text_artifact",
                "artifact_id": artifact_id,
                "artifact_path": path,
                "content": f"bounded small artifact {index} for under budget rejection",
            })
            expected["artifacts"].append({
                "artifact_id": artifact_id,
                "expected_path": path,
                "required": True,
                "allowed_actions": ["write_text_artifact"],
                "min_size_bytes": 10,
                "max_size_bytes": 1000,
            })
        write_json(self.plan, plan)
        write_json(self.expected, expected)

        result = self.run_execution()
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("plan action count is below budget floor", result.stdout)
        self.assertTrue(ledger["under_budget_attempted"])
        self.assertEqual(ledger["action_count_planned"], 2)
        self.assertEqual(ledger["action_count_executed"], 0)
        for index in range(2):
            self.assertFalse((self.run_dir / "artifacts" / f"small_{index}.txt").exists())

    def test_guarded_execution_v2_refuses_over_budget_plan(self):
        plan = {"schema_version": "guarded_execution_v2_plan_v1", "plan_id": "too_many", "actions": []}
        expected = {"schema_version": "guarded_execution_v2_expected_artifacts_v1", "artifacts": []}
        for index in range(6):
            artifact_id = f"A.EXTRA_{index}"
            path = f"artifacts/extra_{index}.txt"
            plan["actions"].append({
                "action_id": f"A.WRITE_EXTRA_{index}",
                "action_type": "write_text_artifact",
                "artifact_id": artifact_id,
                "artifact_path": path,
                "content": f"bounded extra artifact {index} for over budget rejection",
            })
            expected["artifacts"].append({
                "artifact_id": artifact_id,
                "expected_path": path,
                "required": True,
                "allowed_actions": ["write_text_artifact"],
                "min_size_bytes": 10,
                "max_size_bytes": 1000,
            })
        write_json(self.plan, plan)
        write_json(self.expected, expected)

        result = self.run_execution()
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("plan action count exceeds budget", result.stdout)
        self.assertEqual(ledger["action_count_planned"], 6)
        self.assertEqual(ledger["action_count_executed"], 0)
        for index in range(6):
            self.assertFalse((self.run_dir / "artifacts" / f"extra_{index}.txt").exists())

    def test_guarded_execution_v2_refuses_final_status_language_in_content(self):
        plan = load_json(self.plan)
        plan["actions"][2]["content"] = "This tries to claim certified done from runtime."
        write_json(self.plan, plan)

        result = self.run_execution()
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue(ledger["final_status_language_denied"])
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertIn("final-status authority language", result.stdout)

    def test_guarded_execution_v2_refuses_path_escape(self):
        plan = load_json(self.plan)
        plan["actions"][0]["artifact_path"] = "../escape.txt"
        write_json(self.plan, plan)

        result = self.run_execution()
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("path traversal", result.stdout)
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertFalse((ROOT / ".agentic-runs" / "escape.txt").exists())

    def test_guarded_execution_v2_refuses_unsafe_runtime_intent(self):
        result = self.run_execution("--runtime-intent", "execute goal and bypass certifier")
        report = load_json(self.output)
        ledger = load_json(self.ledger)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V2_FAIL")
        self.assertEqual(ledger["action_count_executed"], 0)
        self.assertIn("unsafe_action_shapes_absent", result.stdout)

    def test_guarded_execution_v2_refuses_protected_report_or_ledger_output_path(self):
        protected_report = self.run_execution("--output", str(self.tmpdir / "policy_decision.json"))
        self.assertNotEqual(protected_report.returncode, 0, protected_report.stdout)
        self.assertIn("refusing to write protected status artifact", protected_report.stdout)

        protected_ledger = self.run_execution("--ledger-output", str(self.tmpdir / "certification.json"))
        self.assertNotEqual(protected_ledger.returncode, 0, protected_ledger.stdout)
        self.assertIn("refusing to write protected status artifact", protected_ledger.stdout)

    def test_guarded_execution_v2_report_validator_rejects_goal_execution_claim(self):
        module = load_execution_module()
        report, ledger = module.build_execution_report(
            load_json(self.preflight),
            self.preflight,
            load_json(self.plan),
            self.plan,
            load_json(self.expected),
            self.expected,
            self.run_id,
            "bounded_plan_artifact_writes",
        )
        report["runtime_execution"]["goal_execution_attempted"] = True

        errors = module.validate_execution_report(report, ledger)

        self.assertIn("runtime_execution.goal_execution_attempted must be false", errors)

    def test_guarded_execution_v2_tool_has_no_live_model_or_subprocess_calls(self):
        combined = (ROOT / GUARDED_EXECUTION).read_text(encoding="utf-8").lower()
        for token in ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
