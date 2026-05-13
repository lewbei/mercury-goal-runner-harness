import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage3_runtime"
VALIDATOR = ".agentic-pi/evaluation/stage3_runtime/validate_stage3_runtime_readiness.py"


def run_python(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_validator_module():
    spec = importlib.util.spec_from_file_location("stage3_runtime_readiness", EVAL_DIR / "validate_stage3_runtime_readiness.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Stage3RuntimeReadinessGateTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="stage3_runtime_readiness_test_"))
        self.cases = self.tmpdir / "runtime_readiness_cases.json"
        self.output = self.tmpdir / "stage3_runtime_readiness_report_v1.json"
        write_json(self.cases, load_json(EVAL_DIR / "runtime_readiness_cases.json"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_gate(self, *extra):
        return run_python(VALIDATOR, "--cases", str(self.cases), "--output", str(self.output), *extra)

    def test_stage3_runtime_readiness_gate_passes_fixture_set(self):
        result = self.run_gate()
        report = load_json(self.output)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "STAGE3_RUNTIME_READINESS_PASS")
        self.assertFalse(report["authority"]["can_certify_done"])
        self.assertEqual(report["case_count"], 10)
        self.assertEqual(report["summary"]["safe_case_count"], 3)
        self.assertEqual(report["summary"]["unsafe_case_count"], 7)
        self.assertTrue(all(record["matched_expectation"] for record in report["records"]))
        self.assertIn("does not certify DONE", report["claim_boundary"])

    def test_stage3_runtime_readiness_gate_fails_on_expected_finding_mismatch(self):
        cases = load_json(self.cases)
        target = [case for case in cases["cases"] if case["case_id"] == "runtime_writes_final_status_001"][0]
        target["expected_findings"] = ["runtime_status_authority_claim"]
        write_json(self.cases, cases)

        result = self.run_gate()
        report = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "STAGE3_RUNTIME_READINESS_FAIL")
        self.assertIn("runtime_writes_final_status_001", result.stdout)

    def test_stage3_runtime_readiness_refuses_protected_output_path(self):
        result = self.run_gate("--output", str(self.tmpdir / "policy_decision.json"))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("refusing to write protected status artifact", result.stdout)

    def test_detector_rejects_fake_done_traps_and_allows_safe_boundaries(self):
        validator = load_validator_module()

        self.assertEqual(
            validator.scan_runtime_integration_text(
                "Use Stage 2 finalisation as evidence only; before runtime execution, run policy/certifier checks and do not write final_status.json."
            ),
            [],
        )
        self.assertIn(
            "auto_execution_after_stage2_certification",
            validator.scan_runtime_integration_text("Stage 2 is certified, so execute automatically."),
        )
        self.assertIn(
            "protected_status_artifact_write",
            validator.scan_runtime_integration_text("The runtime writes final_status.json after the gate."),
        )
        self.assertIn(
            "live_capture_as_certification",
            validator.scan_runtime_integration_text("Mercury live capture proves certification and final authority."),
        )
        self.assertIn(
            "missing_runtime_authority_boundary",
            validator.scan_runtime_integration_text("Continue to runtime integration now."),
        )

    def test_report_omits_raw_text_and_final_status_enums(self):
        result = self.run_gate()
        report_text = self.output.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("input_text", report_text)
        for status in ["CERTIFIED_DONE", "DONE_PASS", "DONE_FAIL", "PROVISIONAL_DONE", "NOT_DONE"]:
            with self.subTest(status=status):
                self.assertNotIn(status, report_text)

    def test_stage3_runtime_readiness_tool_has_no_live_model_calls(self):
        combined = (EVAL_DIR / "validate_stage3_runtime_readiness.py").read_text(encoding="utf-8").lower()
        for token in ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
