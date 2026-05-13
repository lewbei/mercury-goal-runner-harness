import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage1_multiframe"
VALIDATOR = ".agentic-pi/evaluation/stage1_multiframe/validate_stage1_eval.py"
SCORER = ".agentic-pi/evaluation/stage1_multiframe/score_stage1_eval.py"


EXPECTED_50_CATEGORY_DISTRIBUTION = {
    "harness_governance": 8,
    "coding_tool_use": 7,
    "research_paper_novelty": 7,
    "repo_product_readiness": 6,
    "model_routing": 6,
    "self_improvement_evolution": 5,
    "memory_reputation_trust": 5,
    "safety_security": 3,
    "ambiguous_user_intent": 3,
}


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
            "--run-id",
            "stage1_multiframe_settlement_50",
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

    def test_fixture_scoring_passes_50_prompt_settlement_gate(self):
        prompt_set, responses, prompt_path, response_path = self.copy_fixtures()
        report_path = self.tmpdir / "stage1_score_report.json"

        score_result = self.score_tmp(prompt_path, response_path, report_path)
        validate_result = self.validate_tmp(prompt_path, response_path, report_path)
        report = load_json(report_path)

        self.assertEqual(len(prompt_set["prompts"]), 50)
        self.assertEqual(len(responses["responses"]), 100)
        self.assertEqual(score_result.returncode, 0, score_result.stdout)
        self.assertEqual(validate_result.returncode, 0, validate_result.stdout)
        self.assertEqual(report["prompt_count"], 50)
        self.assertEqual(report["starter_gate"]["status"], "NOT_APPLICABLE")
        self.assertEqual(report["settlement_50_gate"]["status"], "SETTLEMENT_50_PASS")
        self.assertGreaterEqual(report["settlement_50_gate"]["actual_prompt_wins"], 35)
        self.assertFalse(report["authority"]["can_certify_done"])
        self.assertFalse((self.tmpdir / "final_status.json").exists())
        self.assertEqual(prompt_set["category_distribution"], EXPECTED_50_CATEGORY_DISTRIBUTION)

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

    def test_duplicate_mode_fails_validation(self):
        _prompt_set, responses, prompt_path, response_path = self.copy_fixtures()
        responses["responses"].append(dict(responses["responses"][0]))
        write_json(response_path, responses)

        result = run_python(VALIDATOR, "--prompt-set", str(prompt_path), "--responses", str(response_path), "--no-report")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("duplicate mode", result.stdout)

    def test_authority_overclaim_fails_validation(self):
        _prompt_set, responses, prompt_path, response_path = self.copy_fixtures()
        responses["authority"]["can_certify_done"] = True
        write_json(response_path, responses)

        result = run_python(VALIDATOR, "--prompt-set", str(prompt_path), "--responses", str(response_path), "--no-report")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("can_certify_done", result.stdout)

    def test_bad_settlement_gate_calculation_fails_validation(self):
        _prompt_set, _responses, prompt_path, response_path = self.copy_fixtures()
        report_path = self.tmpdir / "stage1_score_report.json"
        self.assertEqual(self.score_tmp(prompt_path, response_path, report_path).returncode, 0)
        report = load_json(report_path)
        report["settlement_50_gate"]["actual_prompt_wins"] = 0
        write_json(report_path, report)

        result = self.validate_tmp(prompt_path, response_path, report_path)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("settlement_50_gate.actual_prompt_wins", result.stdout)

    def test_normal_beats_multiframe_negative_fixture_fails_50_gate(self):
        prompt_set, responses, prompt_path, response_path = self.copy_fixtures()
        for response in responses["responses"]:
            prompt = next(item for item in prompt_set["prompts"] if item["prompt_id"] == response["prompt_id"])
            if response["mode"] == "normal_prompt":
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
        self.assertEqual(report["settlement_50_gate"]["status"], "SETTLEMENT_50_FAIL")
        self.assertEqual(report["settlement_50_gate"]["actual_prompt_wins"], 0)

    def test_34_multiframe_wins_fails_50_gate(self):
        prompt_set, responses, prompt_path, response_path = self.copy_fixtures()
        prompt_ids = [prompt["prompt_id"] for prompt in prompt_set["prompts"]]
        force_normal_win = set(prompt_ids[:16])
        for response in responses["responses"]:
            if response["prompt_id"] in force_normal_win:
                prompt = next(item for item in prompt_set["prompts"] if item["prompt_id"] == response["prompt_id"])
                if response["mode"] == "normal_prompt":
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

        self.assertEqual(self.score_tmp(prompt_path, response_path, report_path).returncode, 0)
        report = load_json(report_path)

        self.assertEqual(report["settlement_50_gate"]["actual_prompt_wins"], 34)
        self.assertEqual(report["settlement_50_gate"]["status"], "SETTLEMENT_50_FAIL")

    def test_49_prompts_fail_validation(self):
        prompt_set, responses, prompt_path, response_path = self.copy_fixtures()
        removed = prompt_set["prompts"].pop()
        responses["responses"] = [r for r in responses["responses"] if r["prompt_id"] != removed["prompt_id"]]
        write_json(prompt_path, prompt_set)
        write_json(response_path, responses)

        result = run_python(VALIDATOR, "--prompt-set", str(prompt_path), "--responses", str(response_path), "--no-report")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("exactly 5 starter prompts or 50 settlement prompts", result.stdout)

    def test_wrong_category_distribution_fails_validation(self):
        prompt_set, _responses, prompt_path, response_path = self.copy_fixtures()
        prompt_set["prompts"][0]["category"] = "coding_tool_use"
        write_json(prompt_path, prompt_set)

        result = run_python(VALIDATOR, "--prompt-set", str(prompt_path), "--responses", str(response_path), "--no-report")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("category distribution mismatch", result.stdout)

    def test_missing_category_fails_validation(self):
        prompt_set, _responses, prompt_path, response_path = self.copy_fixtures()
        del prompt_set["prompts"][0]["category"]
        write_json(prompt_path, prompt_set)

        result = run_python(VALIDATOR, "--prompt-set", str(prompt_path), "--responses", str(response_path), "--no-report")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("unknown or missing category", result.stdout)

    def test_scorer_refuses_protected_output_path(self):
        _prompt_set, _responses, prompt_path, response_path = self.copy_fixtures()
        result = self.score_tmp(prompt_path, response_path, self.tmpdir / "final_status.json")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("refusing to write protected status artifact", result.stdout)

    def test_stage1_eval_has_no_live_model_calls(self):
        combined = "\n".join(
            (EVAL_DIR / filename).read_text(encoding="utf-8")
            for filename in ["score_stage1_eval.py", "validate_stage1_eval.py", "validate_stage1_live_capture.py"]
        ).lower()
        forbidden = ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
