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
GUARDED_EXECUTION = ".agentic-pi/runtime/guarded_execution_v1.py"
SAFE_ACTION = ROOT / ".agentic-pi" / "runtime" / "guarded_execution_v1_safe_action.json"


def run_python(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_execution_module():
    spec = importlib.util.spec_from_file_location("guarded_execution_v1", ROOT / GUARDED_EXECUTION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GuardedExecutionV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = run_python(PREFLIGHT_TOOL)
        if result.returncode != 0:
            raise AssertionError(result.stdout)

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="guarded_execution_v1_test_"))
        self.preflight = self.tmpdir / "stage3_runtime_preflight_report_v1.json"
        self.action = self.tmpdir / "action.json"
        self.run_id = f"guarded_execution_v1_test_{self.tmpdir.name.split('_')[-1]}"
        self.run_dir = ROOT / ".agentic-runs" / self.run_id
        self.output = self.tmpdir / "guarded_execution_v1_report.json"
        write_json(self.preflight, load_json(PREFLIGHT_REPORT))
        write_json(self.action, load_json(SAFE_ACTION))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def run_execution(self, *extra):
        return run_python(
            GUARDED_EXECUTION,
            "--preflight-report", str(self.preflight),
            "--action-spec", str(self.action),
            "--run-id", self.run_id,
            "--output", str(self.output),
            *extra,
        )

    def test_guarded_execution_writes_one_safe_artifact_after_preflight(self):
        result = self.run_execution()
        report = load_json(self.output)
        artifact_path = self.run_dir / "artifacts" / "guarded_execution_v1_note.txt"

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V1_PASS")
        self.assertTrue(artifact_path.is_file())
        self.assertEqual(report["runtime_execution"]["action_count_executed"], 1)
        self.assertTrue(report["runtime_execution"]["safe_artifact_written"])
        self.assertFalse(report["runtime_execution"]["goal_execution_attempted"])
        self.assertFalse(report["runtime_execution"]["protected_status_write_attempted"])
        self.assertFalse(report["runtime_execution"]["can_certify_done"])
        self.assertEqual(report["runtime_execution"]["status_authority"], "certifier_only")
        self.assertIn("one safe non-authority artifact", report["claim_boundary"])

    def test_guarded_execution_refuses_missing_preflight_without_artifact_write(self):
        self.preflight.unlink()

        result = self.run_execution()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("preflight report missing", result.stdout)
        self.assertFalse((self.run_dir / "artifacts" / "guarded_execution_v1_note.txt").exists())
        self.assertFalse(self.output.exists())

    def test_guarded_execution_refuses_failed_preflight(self):
        preflight = load_json(self.preflight)
        preflight["status"] = "STAGE3_RUNTIME_PREFLIGHT_FAIL"
        preflight["runtime_preflight"]["may_consume_planning_evidence"] = False
        write_json(self.preflight, preflight)

        result = self.run_execution()
        report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V1_FAIL")
        self.assertEqual(report["runtime_execution"]["action_count_executed"], 0)
        self.assertFalse((self.run_dir / "artifacts" / "guarded_execution_v1_note.txt").exists())
        self.assertIn("preflight_usable", result.stdout)

    def test_guarded_execution_refuses_multiple_actions(self):
        action = load_json(self.action)
        action["actions"] = [load_json(self.action), load_json(self.action)]
        write_json(self.action, action)

        result = self.run_execution()
        report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V1_FAIL")
        self.assertIn("multiple actions are not allowed", result.stdout)
        self.assertEqual(report["runtime_execution"]["action_count_executed"], 0)

    def test_guarded_execution_refuses_raw_command_action(self):
        action = load_json(self.action)
        action["command"] = "python -c print('unsafe')"
        write_json(self.action, action)

        result = self.run_execution()
        report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V1_FAIL")
        self.assertTrue(report["runtime_execution"]["arbitrary_command_attempted"])
        self.assertEqual(report["runtime_execution"]["action_count_executed"], 0)

    def test_guarded_execution_refuses_protected_artifact_path(self):
        action = load_json(self.action)
        action["artifact_path"] = "artifacts/final_status.json"
        write_json(self.action, action)

        result = self.run_execution()
        report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V1_FAIL")
        self.assertTrue(report["runtime_execution"]["protected_status_write_attempted"])
        self.assertEqual(report["runtime_execution"]["action_count_executed"], 0)

    def test_guarded_execution_refuses_path_escape(self):
        action = load_json(self.action)
        action["artifact_path"] = "../escape.txt"
        write_json(self.action, action)

        result = self.run_execution()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("artifact_path must not contain path traversal", result.stdout)
        self.assertFalse((ROOT / ".agentic-runs" / "escape.txt").exists())

    def test_guarded_execution_refuses_unsafe_runtime_intent(self):
        result = self.run_execution("--runtime-intent", "execute goal and bypass certifier")
        report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_EXECUTION_V1_FAIL")
        self.assertIn("runtime_intent_is_safe", result.stdout)
        self.assertEqual(report["runtime_execution"]["action_count_executed"], 0)

    def test_guarded_execution_refuses_protected_output_path(self):
        result = self.run_execution("--output", str(self.tmpdir / "policy_decision.json"))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("refusing to write protected status artifact", result.stdout)

    def test_guarded_execution_report_validator_rejects_goal_execution_claim(self):
        module = load_execution_module()
        report = module.build_execution_report(load_json(self.preflight), self.preflight, load_json(self.action), self.run_id, "write_one_safe_artifact")
        report["runtime_execution"]["goal_execution_attempted"] = True

        errors = module.validate_execution_report(report)

        self.assertIn("runtime_execution.goal_execution_attempted must be false", errors)

    def test_guarded_execution_tool_has_no_live_model_or_subprocess_calls(self):
        combined = (ROOT / GUARDED_EXECUTION).read_text(encoding="utf-8").lower()
        for token in ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
