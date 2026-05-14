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
SMOKE = ".agentic-pi/runtime/guarded_runtime_smoke.py"


def run_python(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("guarded_runtime_smoke", ROOT / SMOKE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GuardedRuntimeSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = run_python(PREFLIGHT_TOOL)
        if result.returncode != 0:
            raise AssertionError(result.stdout)

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="guarded_runtime_smoke_test_"))
        self.preflight = self.tmpdir / "stage3_runtime_preflight_report_v1.json"
        self.output = self.tmpdir / "guarded_runtime_smoke_report_v1.json"
        write_json(self.preflight, load_json(PREFLIGHT_REPORT))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_smoke(self, *extra):
        return run_python(SMOKE, "--preflight-report", str(self.preflight), "--output", str(self.output), *extra)

    def test_guarded_runtime_smoke_passes_after_preflight(self):
        result = self.run_smoke()
        report = load_json(self.output)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "GUARDED_RUNTIME_SMOKE_PASS")
        self.assertFalse(report["authority"]["can_certify_done"])
        self.assertTrue(report["runtime_smoke"]["preflight_checked"])
        self.assertTrue(report["runtime_smoke"]["planning_evidence_consumed"])
        self.assertFalse(report["runtime_smoke"]["goal_execution_attempted"])
        self.assertFalse(report["runtime_smoke"]["protected_status_write_attempted"])
        self.assertEqual(report["runtime_smoke"]["status_authority"], "certifier_only")
        self.assertTrue(report["runtime_smoke"]["requires_policy_certifier_for_status"])
        self.assertIn("does not execute goals", report["claim_boundary"])

    def test_guarded_runtime_smoke_refuses_missing_preflight(self):
        self.preflight.unlink()

        result = self.run_smoke()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("preflight report missing", result.stdout)
        self.assertFalse(self.output.exists())

    def test_guarded_runtime_smoke_refuses_failed_preflight(self):
        report = load_json(self.preflight)
        report["status"] = "STAGE3_RUNTIME_PREFLIGHT_FAIL"
        report["runtime_preflight"]["may_consume_planning_evidence"] = False
        write_json(self.preflight, report)

        result = self.run_smoke()
        smoke = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(smoke["status"], "GUARDED_RUNTIME_SMOKE_FAIL")
        self.assertFalse(smoke["runtime_smoke"]["planning_evidence_consumed"])
        self.assertIn("preflight_passed", result.stdout)

    def test_guarded_runtime_smoke_refuses_preflight_execution_authority(self):
        report = load_json(self.preflight)
        report["runtime_preflight"]["may_execute_goals"] = True
        write_json(self.preflight, report)

        result = self.run_smoke()
        smoke = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(smoke["status"], "GUARDED_RUNTIME_SMOKE_FAIL")
        self.assertFalse(smoke["runtime_smoke"]["goal_execution_attempted"])
        self.assertIn("preflight_allows_planning_evidence_only", result.stdout)

    def test_guarded_runtime_smoke_refuses_authority_leaking_preflight(self):
        report = load_json(self.preflight)
        report["authority"]["can_certify_done"] = True
        write_json(self.preflight, report)

        result = self.run_smoke()
        smoke = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(smoke["status"], "GUARDED_RUNTIME_SMOKE_FAIL")
        self.assertIn("preflight_report_validates", result.stdout)
        self.assertFalse(smoke["runtime_smoke"]["planning_evidence_consumed"])

    def test_guarded_runtime_smoke_refuses_unsafe_runtime_intent(self):
        result = self.run_smoke("--runtime-intent", "execute goal and bypass certifier")
        smoke = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(smoke["status"], "GUARDED_RUNTIME_SMOKE_FAIL")
        self.assertIn("runtime_intent_is_non_executing", result.stdout)
        self.assertFalse(smoke["runtime_smoke"]["goal_execution_attempted"])

    def test_guarded_runtime_smoke_refuses_protected_output_path(self):
        result = self.run_smoke("--output", str(self.tmpdir / "certification.json"))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("refusing to write protected status artifact", result.stdout)

    def test_guarded_runtime_smoke_report_validator_rejects_execution_claim(self):
        smoke = load_smoke_module()
        report = smoke.build_smoke_report(load_json(self.preflight), self.preflight, "consume_planning_evidence_only")
        report["runtime_smoke"]["goal_execution_attempted"] = True

        errors = smoke.validate_smoke_report(report)

        self.assertIn("runtime_smoke.goal_execution_attempted must be false", errors)

    def test_guarded_runtime_smoke_tool_has_no_live_model_or_subprocess_calls(self):
        combined = (ROOT / SMOKE).read_text(encoding="utf-8").lower()
        for token in ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
