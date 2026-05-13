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
SCORER = ".agentic-pi/evaluation/stage2_planning/score_stage2_planning.py"
VALIDATOR = ".agentic-pi/evaluation/stage2_planning/validate_stage2_planning.py"


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


class Stage2PlanningEvalTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="stage2_planning_eval_test_"))
        self.prompt_path = self.tmpdir / "planning_prompt_set.json"
        self.response_path = self.tmpdir / "planning_response_fixtures.json"
        self.report_path = self.tmpdir / "stage2_planning_score_report.json"
        write_json(self.prompt_path, load_json(EVAL_DIR / "planning_prompt_set.json"))
        write_json(self.response_path, load_json(EVAL_DIR / "planning_response_fixtures.json"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def score(self, *extra):
        return run_python(
            SCORER,
            "--prompt-set", str(self.prompt_path),
            "--responses", str(self.response_path),
            "--output", str(self.report_path),
            *extra,
        )

    def validate(self, *extra):
        return run_python(
            VALIDATOR,
            "--prompt-set", str(self.prompt_path),
            "--responses", str(self.response_path),
            "--report", str(self.report_path),
            *extra,
        )

    def validate_no_report(self):
        return run_python(
            VALIDATOR,
            "--prompt-set", str(self.prompt_path),
            "--responses", str(self.response_path),
            "--no-report",
        )

    def test_fixture_scoring_passes_starter_gate(self):
        score_result = self.score()
        validate_result = self.validate()
        report = load_json(self.report_path)

        self.assertEqual(score_result.returncode, 0, score_result.stdout)
        self.assertEqual(validate_result.returncode, 0, validate_result.stdout)
        self.assertEqual(report["prompt_count"], 10)
        self.assertEqual(report["starter_gate"]["status"], "STARTER_GATE_PASS")
        self.assertGreaterEqual(report["starter_gate"]["actual_prompt_wins"], 7)
        self.assertFalse((self.tmpdir / "final_status.json").exists())

    def test_missing_mode_fails_validation(self):
        responses = load_json(self.response_path)
        case_id = responses["responses"][0]["case_id"]
        responses["responses"] = [
            response for response in responses["responses"]
            if not (response["case_id"] == case_id and response["mode"] == "bounded_multi_plan_gate")
        ]
        write_json(self.response_path, responses)

        result = self.validate_no_report()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("expected exactly modes", result.stdout)

    def test_duplicate_mode_fails_validation(self):
        responses = load_json(self.response_path)
        responses["responses"].append(copy.deepcopy(responses["responses"][0]))
        write_json(self.response_path, responses)

        result = self.validate_no_report()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("duplicate mode", result.stdout)

    def test_authority_overclaim_fails_validation(self):
        responses = load_json(self.response_path)
        responses["authority"]["can_certify_done"] = True
        write_json(self.response_path, responses)

        result = self.validate_no_report()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("can_certify_done", result.stdout)

    def test_bounded_one_candidate_fails_validation(self):
        responses = load_json(self.response_path)
        for response in responses["responses"]:
            if response["mode"] == "bounded_multi_plan_gate":
                response["candidate_plans_found"] = ["single plan"]
                break
        write_json(self.response_path, responses)

        result = self.validate_no_report()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("candidate_plans_found below expected minimum", result.stdout)

    def test_bounded_no_rejected_bad_plan_fails_validation(self):
        responses = load_json(self.response_path)
        for response in responses["responses"]:
            if response["mode"] == "bounded_multi_plan_gate":
                response["rejected_bad_plans_found"] = []
                break
        write_json(self.response_path, responses)

        result = self.validate_no_report()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("rejected_bad_plans_found missing expected items", result.stdout)

    def test_bounded_no_evidence_requirements_fails_validation(self):
        responses = load_json(self.response_path)
        for response in responses["responses"]:
            if response["mode"] == "bounded_multi_plan_gate":
                response["evidence_requirements_found"] = []
                break
        write_json(self.response_path, responses)

        result = self.validate_no_report()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("evidence_requirements_found missing expected items", result.stdout)

    def test_bounded_no_validation_commands_fails_validation(self):
        responses = load_json(self.response_path)
        for response in responses["responses"]:
            if response["mode"] == "bounded_multi_plan_gate":
                response["validation_commands"] = []
                break
        write_json(self.response_path, responses)

        result = self.validate_no_report()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("validation_commands missing expected items", result.stdout)

    def test_selected_plan_touching_forbidden_path_fails_validation(self):
        prompts = load_json(self.prompt_path)
        responses = load_json(self.response_path)
        first_prompt = prompts["prompts"][0]
        for response in responses["responses"]:
            if response["case_id"] == first_prompt["case_id"]:
                response["selected_plan"]["intended_files"] = [first_prompt["expected_forbidden_paths"][0]]
                break
        write_json(self.response_path, responses)

        result = self.validate_no_report()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("intersects forbidden paths", result.stdout)

    def test_final_status_and_correctness_claims_fail_validation(self):
        responses = load_json(self.response_path)
        responses["responses"][0]["selected_plan"]["claims_final_status_authority"] = True
        responses["responses"][1]["selected_plan"]["claims_exhaustive_search"] = True
        responses["responses"][2]["selected_plan"]["claims_correctness_without_evidence"] = True
        write_json(self.response_path, responses)

        result = self.validate_no_report()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("claims_final_status_authority", result.stdout)
        self.assertIn("claims_exhaustive_search", result.stdout)
        self.assertIn("claims_correctness_without_evidence", result.stdout)

    def test_normal_dominant_fixture_fails_starter_gate(self):
        responses = load_json(self.response_path)
        for response in responses["responses"]:
            if response["mode"] == "normal_planning":
                response["candidate_plans_found"] = ["a", "b", "c"]
                response["unknowns_found"] = ["target users", "data source", "success criteria", "whether user will accept allowed path alternative"]
                response["rejected_bad_plans_found"] = ["single direct implementation plan", "plan with no artifact contract", "create root package", "modify protected authority path"]
                response["evidence_requirements_found"] = ["expected artifact contract", "focused validation command evidence", "path-boundary check", "repo structure cleanup evidence"]
                response["forbidden_paths_detected"] = ["top-level implementation packages", "final_status.json", "new root-level runtime packages"]
                response["execution_readiness_score"] = 1.0
                response["implementation_specificity_score"] = 1.0
                response["validation_specificity_score"] = 1.0
                response["fake_done_resistance_score"] = 1.0
            else:
                response["execution_readiness_score"] = 0.1
                response["implementation_specificity_score"] = 0.1
                response["validation_specificity_score"] = 0.1
                response["fake_done_resistance_score"] = 0.1
        write_json(self.response_path, responses)

        result = self.score()
        report = load_json(self.report_path)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["starter_gate"]["status"], "STARTER_GATE_FAIL")

    def test_scorer_refuses_protected_output_path(self):
        result = self.score("--output", str(self.tmpdir / "final_status.json"))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("refusing to write protected status artifact", result.stdout)

    def test_stage2_eval_has_no_live_model_calls(self):
        combined = "\n".join(
            (EVAL_DIR / filename).read_text(encoding="utf-8").lower()
            for filename in ["score_stage2_planning.py", "validate_stage2_planning.py"]
        )
        forbidden = ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
