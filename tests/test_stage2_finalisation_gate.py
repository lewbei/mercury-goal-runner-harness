import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage2_planning"
FINALISATION = ".agentic-pi/evaluation/stage2_planning/validate_stage2_finalisation.py"


def run_python(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class Stage2FinalisationGateTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="stage2_finalisation_test_"))
        self.deterministic = self.tmpdir / "stage2_planning_score_report.json"
        self.full_live = self.tmpdir / "live_planning_feature_report_mercury_full_10_v7.json"
        self.adversarial = self.tmpdir / "adversarial_protected_feature_report_mercury_subset_5_v7.json"
        self.output = self.tmpdir / "stage2_finalisation_gate_report_v1.json"
        write_json(self.deterministic, load_json(EVAL_DIR / "stage2_planning_score_report.json"))
        write_json(self.full_live, load_json(EVAL_DIR / "live_planning_feature_report_mercury_full_10_v7.json"))
        write_json(self.adversarial, load_json(EVAL_DIR / "adversarial_protected_feature_report_mercury_subset_5_v7.json"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_gate(self, *extra):
        return run_python(
            FINALISATION,
            "--deterministic-report", str(self.deterministic),
            "--full-live-report", str(self.full_live),
            "--adversarial-report", str(self.adversarial),
            "--output", str(self.output),
            *extra,
        )

    def test_stage2_finalisation_gate_passes_current_evidence(self):
        result = self.run_gate()
        report = load_json(self.output)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["status"], "STAGE2_FINALISATION_PASS")
        self.assertFalse(report["authority"]["can_certify_done"])
        self.assertTrue(all(check["status"] == "PASS" for check in report["criteria"]))
        self.assertIn("does not certify DONE", report["claim_boundary"])

    def test_stage2_finalisation_gate_fails_if_full_live_is_subset(self):
        report = load_json(self.full_live)
        report["source_capture"]["capture_scope"] = "subset_fixture_only"
        write_json(self.full_live, report)

        result = self.run_gate()
        finalisation = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(finalisation["status"], "STAGE2_FINALISATION_FAIL")
        self.assertIn("full_live_capture_scope", result.stdout)

    def test_stage2_finalisation_gate_fails_on_protected_gate_failure(self):
        report = load_json(self.adversarial)
        report["records"][0]["protected_authority_gate"]["status"] = "FAIL"
        report["records"][0]["authority_findings"] = ["protected_gate_sample_payload"]
        write_json(self.adversarial, report)

        result = self.run_gate()
        finalisation = load_json(self.output)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(finalisation["status"], "STAGE2_FINALISATION_FAIL")
        self.assertIn("adversarial_all_protected_gate_pass", result.stdout)

    def test_stage2_finalisation_gate_fails_when_bounded_live_underperforms(self):
        report = load_json(self.full_live)
        report["aggregate_metrics"]["bounded_multi_plan_gate_pair_wins"] = 2
        report["aggregate_metrics"]["mode_averages"]["bounded_multi_plan_gate"]["composite_score"] = 0.1
        write_json(self.full_live, report)

        result = self.run_gate()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("full_live_bounded_pair_wins", result.stdout)
        self.assertIn("full_live_bounded_composite_beats_normal", result.stdout)

    def test_stage2_finalisation_refuses_protected_output_path(self):
        result = self.run_gate("--output", str(self.tmpdir / "final_status.json"))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("refusing to write protected status artifact", result.stdout)

    def test_stage2_finalisation_tool_has_no_live_model_calls(self):
        combined = (EVAL_DIR / "validate_stage2_finalisation.py").read_text(encoding="utf-8").lower()
        for token in ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
