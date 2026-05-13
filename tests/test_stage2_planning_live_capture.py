import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage2_planning"
GENERATOR = ".agentic-pi/evaluation/stage2_planning/generate_stage2_planning_request_pack.py"
REQUEST_VALIDATOR = ".agentic-pi/evaluation/stage2_planning/validate_stage2_planning_request_pack.py"
CAPTURE_VALIDATOR = ".agentic-pi/evaluation/stage2_planning/validate_stage2_live_planning_capture.py"
RUNNER_PATH = EVAL_DIR / "run_mercury_stage2_planning_capture.py"


def run_python(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_runner_module():
    spec = importlib.util.spec_from_file_location("stage2_mercury_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Stage2PlanningLiveCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="stage2_planning_live_test_"))
        self.prompt_path = EVAL_DIR / "planning_prompt_set.json"
        self.pack_path = self.tmpdir / "request_pack.json"
        self.capture_path = self.tmpdir / "capture.json"

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def generate_pack(self):
        return run_python(GENERATOR, "--prompt-set", str(self.prompt_path), "--output", str(self.pack_path))

    def validate_pack(self):
        return run_python(REQUEST_VALIDATOR, "--prompt-set", str(self.prompt_path), "--request-pack", str(self.pack_path))

    def validate_capture(self, *extra):
        return run_python(CAPTURE_VALIDATOR, "--prompt-set", str(self.prompt_path), "--capture", str(self.capture_path), *extra)

    def make_capture(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        tasks = load_runner_module().selected_tasks(pack, 2)
        captures = []
        system_prompt = "stage2 planning test system prompt"
        for task in tasks:
            output = f"Fixture-only live planning output for {task['task_id']}. This is not certification."
            captures.append({
                "case_id": task["case_id"],
                "mode": task["mode"],
                "provider": "fixture-provider",
                "model": "fixture-model",
                "model_version": "fixture-version",
                "prompt_text": task["prompt_text"],
                "prompt_hash": task["prompt_hash"],
                "system_prompt_hash": sha256_text(system_prompt),
                "output_text": output,
                "output_hash": sha256_text(output),
                "captured_at": "2026-05-13T00:00:00Z",
                "capture_method": "fixture_only_not_live_evidence",
                "provenance": {
                    "temperature": None,
                    "max_output_tokens": None,
                    "attempt_number": 1,
                    "provider_request_id": "fixture-request",
                    "session_ref": "fixture-session",
                    "tool_calls_allowed": False,
                    "tool_call_count": 0,
                    "notes": "Fixture shape only; not live model evidence.",
                },
            })
        capture = {
            "schema_version": "stage2_live_planning_capture_v1",
            "capture_id": "stage2_live_planning_capture_subset_fixture_v1",
            "prompt_set_id": pack["prompt_set_id"],
            "request_pack_id": pack["request_pack_id"],
            "capture_scope": "subset_fixture_only",
            "authority": {"authority_level": "evaluation_capture_only", "final_status_authority": "certifier_only", "can_certify_done": False},
            "capture_environment": {"captured_by": "test-fixture", "capture_tool": "fixture", "notes": "subset fixture only"},
            "captures": captures,
        }
        write_json(self.capture_path, capture)
        return capture

    def test_generator_creates_valid_20_task_request_pack(self):
        generate_result = self.generate_pack()
        validate_result = self.validate_pack()
        pack = load_json(self.pack_path)

        self.assertEqual(generate_result.returncode, 0, generate_result.stdout)
        self.assertEqual(validate_result.returncode, 0, validate_result.stdout)
        self.assertEqual(len(pack["tasks"]), 20)
        self.assertFalse(pack["authority"]["can_certify_done"])
        for task in pack["tasks"]:
            self.assertNotIn("output_text", task)
            self.assertIn(task["prompt_text"], task["capture_instruction"])

    def test_bounded_instruction_contains_planning_gate_discipline(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        bounded = [task for task in pack["tasks"] if task["mode"] == "bounded_multi_plan_gate"]
        self.assertEqual(len(bounded), 10)
        for phrase in ["Known facts from the goal only", "At least three candidate plans", "Rejected bad plans", "Evidence required before execution", "NEED_USER / BLOCKED"]:
            for task in bounded:
                with self.subTest(task_id=task["task_id"], phrase=phrase):
                    self.assertIn(phrase, task["capture_instruction"])

    def test_request_pack_missing_mode_fails(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        for task in pack["tasks"]:
            if task["mode"] == "bounded_multi_plan_gate":
                task["mode"] = "normal_planning"
                task["task_id"] += "-mutated"
                break
        write_json(self.pack_path, pack)

        result = self.validate_pack()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("expected exactly modes", result.stdout)

    def test_request_pack_hash_mismatch_fails(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        pack["tasks"][0]["prompt_hash"] = "0" * 64
        write_json(self.pack_path, pack)

        result = self.validate_pack()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("prompt_hash mismatch", result.stdout)

    def test_request_pack_output_key_fails_schema(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        pack["tasks"][0]["output_text"] = "fake output"
        write_json(self.pack_path, pack)

        result = self.validate_pack()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("unexpected field 'output_text'", result.stdout.lower())

    def test_ungrounded_bounded_instruction_fails(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        for task in pack["tasks"]:
            if task["mode"] == "bounded_multi_plan_gate":
                task["capture_instruction"] = f"Plan this.\n{task['prompt_text']}"
                break
        write_json(self.pack_path, pack)

        result = self.validate_pack()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("missing planning phrases", result.stdout)

    def test_valid_subset_capture_fixture_passes_with_test_flag(self):
        self.make_capture()
        result = self.validate_capture("--allow-subset-for-tests")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("OK: stage2 live planning capture valid", result.stdout)

    def test_subset_capture_fails_without_test_flag(self):
        self.make_capture()
        result = self.validate_capture()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("subset_fixture_only captures require --allow-subset-for-tests", result.stdout)

    def test_capture_output_hash_duplicate_missing_and_unknown_fail(self):
        capture = self.make_capture()
        capture["captures"][0]["output_text"] += " changed"
        capture["captures"].append(copy.deepcopy(capture["captures"][1]))
        capture["captures"] = [record for record in capture["captures"] if not (record["case_id"] == capture["captures"][2]["case_id"] and record["mode"] == "bounded_multi_plan_gate")]
        capture["captures"][0]["case_id"] = "unknown_case"
        write_json(self.capture_path, capture)

        result = self.validate_capture("--allow-subset-for-tests")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("unknown case_id", result.stdout)
        self.assertIn("duplicate mode", result.stdout)
        self.assertIn("expected exactly modes", result.stdout)

    def test_capture_authority_overclaim_fails(self):
        capture = self.make_capture()
        capture["captures"][0]["output_text"] = "I certify this as CERTIFIED_DONE."
        capture["captures"][0]["output_hash"] = sha256_text(capture["captures"][0]["output_text"])
        write_json(self.capture_path, capture)

        result = self.validate_capture("--allow-subset-for-tests")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("final status value", result.stdout)

    def test_runner_selection_and_protected_output_guard(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        runner = load_runner_module()
        tasks = runner.selected_tasks(pack, 3)
        self.assertEqual(len(tasks), 6)
        self.assertEqual([task["mode"] for task in tasks[:2]], ["normal_planning", "bounded_multi_plan_gate"])
        with self.assertRaises(ValueError):
            runner.write_json(self.tmpdir / "final_status.json", {"bad": True})

    def test_stage2_live_tools_have_no_unintended_live_model_calls(self):
        combined = "\n".join(
            (EVAL_DIR / filename).read_text(encoding="utf-8").lower()
            for filename in ["generate_stage2_planning_request_pack.py", "validate_stage2_planning_request_pack.py", "validate_stage2_live_planning_capture.py"]
        )
        for token in ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
