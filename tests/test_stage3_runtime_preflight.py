import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE2_REPORT = ROOT / ".agentic-pi" / "evaluation" / "stage2_planning" / "stage2_finalisation_gate_report_v1.json"
STAGE3_REPORT = ROOT / ".agentic-pi" / "evaluation" / "stage3_runtime" / "stage3_runtime_readiness_report_v1.json"
PREFLIGHT = ".agentic-pi/runtime/stage3_runtime_preflight.py"


def run_python(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_preflight_module():
    spec = importlib.util.spec_from_file_location("stage3_runtime_preflight", ROOT / PREFLIGHT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Stage3RuntimePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="stage3_runtime_preflight_test_"))
        self.stage2 = self.tmpdir / "stage2_finalisation_gate_report_v1.json"
        self.stage3 = self.tmpdir / "stage3_runtime_readiness_report_v1.json"
        self.output = self.tmpdir / "stage3_runtime_preflight_report_v1.json"
        write_json(self.stage2, load_json(STAGE2_REPORT))
        write_json(self.stage3, load_json(STAGE3_REPORT))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_gate(self, *extra):
        return run_python(PREFLIGHT, "--stage2-report", str(self.stage2), "--stage3-report", str(self.stage3), "--output", str(self.output), *extra)

    def test_stage3_runtime_preflight_passes_current_gate_reports(self):
        result = self.run_gate()
        report = load_json(self.output)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "STAGE3_RUNTIME_PREFLIGHT_PASS")
        self.assertFalse(report["authority"]["can_certify_done"])
        self.assertTrue(report["runtime_preflight"]["may_consume_planning_evidence"])
        self.assertFalse(report["runtime_preflight"]["may_execute_goals"])
        self.assertFalse(report["runtime_preflight"]["may_certify_done"])
        self.assertTrue(report["runtime_preflight"]["requires_policy_certifier_for_status"])
        self.assertTrue(all(check["status"] == "PASS" for check in report["criteria"]))
        self.assertIn("does not execute goals", report["claim_boundary"])

    def test_stage3_runtime_preflight_fails_when_stage2_missing(self):
        self.stage2.unlink()

        result = self.run_gate()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("stage2 report missing", result.stdout)
        self.assertFalse(self.output.exists())

    def test_stage3_runtime_preflight_fails_when_stage2_not_passed(self):
        report = load_json(self.stage2)
        report["status"] = "STAGE2_FINALISATION_FAIL"
        write_json(self.stage2, report)

        result = self.run_gate()
        preflight = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(preflight["status"], "STAGE3_RUNTIME_PREFLIGHT_FAIL")
        self.assertIn("stage2_finalisation_passed", result.stdout)
        self.assertFalse(preflight["runtime_preflight"]["may_consume_planning_evidence"])

    def test_stage3_runtime_preflight_fails_when_stage3_authority_leaks(self):
        report = load_json(self.stage3)
        report["authority"]["can_certify_done"] = True
        write_json(self.stage3, report)

        result = self.run_gate()
        preflight = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(preflight["status"], "STAGE3_RUNTIME_PREFLIGHT_FAIL")
        self.assertIn("stage3_authority_boundary", result.stdout)

    def test_stage3_runtime_preflight_fails_when_fake_done_trap_not_rejected(self):
        report = load_json(self.stage3)
        for record in report["records"]:
            if record["case_id"] == "runtime_writes_final_status_001":
                record["actual_verdict"] = "PASS"
                record["finding_ids"] = []
        report["summary"]["finding_counts"].pop("protected_status_artifact_write", None)
        write_json(self.stage3, report)

        result = self.run_gate()
        preflight = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(preflight["status"], "STAGE3_RUNTIME_PREFLIGHT_FAIL")
        self.assertIn("stage3_fake_done_traps_rejected", result.stdout)

    def test_stage3_runtime_preflight_refuses_protected_output_path(self):
        result = self.run_gate("--output", str(self.tmpdir / "final_status.json"))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("refusing to write protected status artifact", result.stdout)

    def test_stage3_runtime_preflight_report_rejects_runtime_execution_authority(self):
        preflight = load_preflight_module()
        report = preflight.build_preflight_report(load_json(self.stage2), load_json(self.stage3), self.stage2, self.stage3)
        report["runtime_preflight"]["may_execute_goals"] = True

        errors = preflight.validate_preflight_report(report)

        self.assertIn("runtime_preflight.may_execute_goals must be false for this smoke gate", errors)

    def test_stage3_runtime_preflight_tool_has_no_live_model_or_subprocess_calls(self):
        combined = (ROOT / PREFLIGHT).read_text(encoding="utf-8").lower()
        for token in ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
