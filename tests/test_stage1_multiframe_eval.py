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
EVAL_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage1_multiframe"
SCORER_PATH = EVAL_DIR / "score_stage1_eval.py"
VALIDATOR = ".agentic-pi/evaluation/stage1_multiframe/validate_stage1_eval.py"
SCORER = ".agentic-pi/evaluation/stage1_multiframe/score_stage1_eval.py"


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_scorer_module():
    spec = importlib.util.spec_from_file_location("stage1_scorer", SCORER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Stage1MultiframeEvalTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="stage1_multiframe_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def copy_fixtures(self):
        prompt_set = load_json(EVAL_DIR / "prompt_set.json")
        responses = load_json(EVAL_DIR / "response_fixtures.json")
        prompt_path = self.tmpdir / "prompt_set.json"
        response_path = self.tmpdir / "response_fixtures.json"
        write_json(prompt_path, prompt_set)
        write_json(response_path, responses)
        return prompt_set, responses, prompt_path, response_path

    def score_tmp(self, prompt_path: Path, response_path: Path, report_path: Path):
        return run_python(
            SCORER,
            "--prompt-set",
            str(prompt_path),
            "--responses",
            str(response_path),
            "--output",
            str(report_path),
        )

    def validate_tmp(self, prompt_path: Path, response_path: Path, report_path: Path):
        return run_python(
            VALIDATOR,
            "--prompt-set",
            str(prompt_path),
            "--responses",
            str(response_path),
            "--report",
            str(report_path),
        )

    def test_fixture_scoring_passes_starter_gate(self):
        _prompt_set, _responses, prompt_path, response_path = self.copy_fixtures()
        report_path = self.tmpdir / "stage1_score_report.json"

        score_result = self.score_tmp(prompt_path, response_path, report_path)
        validate_result = self.validate_tmp(prompt_path, response_path, report_path)
        report = load_json(report_path)

        self.assertEqual(score_result.returncode, 0, score_result.stdout)
        self.assertEqual(validate_result.returncode, 0, validate_result.stdout)
        self.assertEqual(report["starter_gate"]["status"], "STARTER_GATE_PASS")
        self.assertEqual(report["starter_gate"]["actual_prompt_wins"], 5)
        self.assertFalse(report["authority"]["can_certify_done"])
        self.assertFalse((self.tmpdir / "final_status.json").exists())
        self.assertEqual(report["future_50_prompt_gate_policy"]["status"], "NOT_EVALUATED_BY_STARTER_5")

    def test_missing_mode_fails_validation(self):
        prompt_set, responses, prompt_path, response_path = self.copy_fixtures()
        responses["responses"] = [
            response
            for response in responses["responses"]
            if not (response["prompt_id"] == prompt_set["prompts"][0]["prompt_id"] and response["mode"] == "multiframe_harness")
        ]
        write_json(response_path, responses)

        result = run_python(VALIDATOR, "--prompt-set", str(prompt_path), "--responses", str(response_path), "--no-report")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("expected exactly modes", result.stdout)

    def test_authority_overclaim_fails_validation(self):
        _prompt_set, responses, prompt_path, response_path = self.copy_fixtures()
        responses["authority"]["can_certify_done"] = True
        write_json(response_path, responses)

        result = run_python(VALIDATOR, "--prompt-set", str(prompt_path), "--responses", str(response_path), "--no-report")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("can_certify_done", result.stdout)

    def test_bad_pass_gate_calculation_fails_validation(self):
        _prompt_set, _responses, prompt_path, response_path = self.copy_fixtures()
        report_path = self.tmpdir / "stage1_score_report.json"
        self.assertEqual(self.score_tmp(prompt_path, response_path, report_path).returncode, 0)
        report = load_json(report_path)
        report["starter_gate"]["actual_prompt_wins"] = 0
        write_json(report_path, report)

        result = self.validate_tmp(prompt_path, response_path, report_path)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("does not match prompt results", result.stdout)

    def test_normal_beats_multiframe_negative_fixture_fails_gate(self):
        prompt_set, responses, prompt_path, response_path = self.copy_fixtures()
        for response in responses["responses"]:
            if response["mode"] == "normal_prompt":
                prompt = next(item for item in prompt_set["prompts"] if item["prompt_id"] == response["prompt_id"])
                response["frames_found"] = list(prompt["expected_frames"])
                response["assumptions_found"] = list(prompt["expected_assumptions"])
                response["failure_modes_found"] = list(prompt["expected_failure_modes"])
                response["bad_frames_rejected"] = list(prompt["bad_frames_to_reject"])
                response["final_answer_quality"] = 1.0
            else:
                response["frames_found"] = []
                response["assumptions_found"] = []
                response["failure_modes_found"] = []
                response["bad_frames_rejected"] = []
                response["final_answer_quality"] = 0.0
        write_json(response_path, responses)
        report_path = self.tmpdir / "stage1_score_report.json"

        score_result = self.score_tmp(prompt_path, response_path, report_path)
        validate_result = self.validate_tmp(prompt_path, response_path, report_path)
        report = load_json(report_path)

        self.assertEqual(score_result.returncode, 0, score_result.stdout)
        self.assertEqual(validate_result.returncode, 0, validate_result.stdout)
        self.assertEqual(report["starter_gate"]["status"], "STARTER_GATE_FAIL")
        self.assertEqual(report["starter_gate"]["actual_prompt_wins"], 0)

    def test_scorer_refuses_protected_output_path(self):
        _prompt_set, _responses, prompt_path, response_path = self.copy_fixtures()
        result = self.score_tmp(prompt_path, response_path, self.tmpdir / "final_status.json")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("refusing to write protected status artifact", result.stdout)


if __name__ == "__main__":
    unittest.main()
