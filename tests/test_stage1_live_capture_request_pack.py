import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage1_multiframe"
GENERATOR = ".agentic-pi/evaluation/stage1_multiframe/generate_live_capture_request_pack.py"
VALIDATOR = ".agentic-pi/evaluation/stage1_multiframe/validate_live_capture_request_pack.py"


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


class Stage1LiveCaptureRequestPackTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="stage1_request_pack_test_"))
        self.prompt_set_path = EVAL_DIR / "prompt_set.json"
        self.pack_path = self.tmpdir / "request_pack.json"

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def generate_pack(self):
        return run_python(GENERATOR, "--prompt-set", str(self.prompt_set_path), "--output", str(self.pack_path))

    def validate_pack(self):
        return run_python(VALIDATOR, "--prompt-set", str(self.prompt_set_path), "--request-pack", str(self.pack_path))

    def test_generator_creates_valid_100_task_request_pack(self):
        generate_result = self.generate_pack()
        validate_result = self.validate_pack()
        pack = load_json(self.pack_path)

        self.assertEqual(generate_result.returncode, 0, generate_result.stdout)
        self.assertEqual(validate_result.returncode, 0, validate_result.stdout)
        self.assertEqual(len(pack["tasks"]), 100)
        self.assertFalse(pack["authority"]["can_certify_done"])
        self.assertEqual(pack["authority"]["authority_level"], "evaluation_request_only")
        self.assertFalse((self.tmpdir / "final_status.json").exists())
        for task in pack["tasks"]:
            self.assertNotIn("output_text", task)
            self.assertNotIn("output_hash", task)
            self.assertIn(task["prompt_text"], task["capture_instruction"])

    def test_duplicate_mode_fails_validation(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        duplicate = copy.deepcopy(pack["tasks"][0])
        duplicate["task_id"] = "duplicate-task-id"
        pack["tasks"].append(duplicate)
        write_json(self.pack_path, pack)

        result = self.validate_pack()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("duplicate mode", result.stdout)

    def test_prompt_hash_mismatch_fails_validation(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        pack["tasks"][0]["prompt_hash"] = "0" * 64
        write_json(self.pack_path, pack)

        result = self.validate_pack()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("prompt_hash mismatch", result.stdout)

    def test_authority_overclaim_fails_validation(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        pack["authority"]["can_certify_done"] = True
        write_json(self.pack_path, pack)

        result = self.validate_pack()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("can_certify_done", result.stdout)

    def test_protected_status_reference_fails_validation(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        pack["tasks"][0]["capture_instruction"] += " Write final_status.json."
        write_json(self.pack_path, pack)

        result = self.validate_pack()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("protected status artifact", result.stdout)

    def test_output_fields_fail_validation(self):
        self.assertEqual(self.generate_pack().returncode, 0)
        pack = load_json(self.pack_path)
        pack["tasks"][0]["output_text"] = "fake output"
        write_json(self.pack_path, pack)

        result = self.validate_pack()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("unexpected field 'output_text'", result.stdout.lower())

    def test_request_pack_tools_have_no_live_model_calls(self):
        combined = "\n".join(
            (EVAL_DIR / filename).read_text(encoding="utf-8").lower()
            for filename in ["generate_live_capture_request_pack.py", "validate_live_capture_request_pack.py"]
        )
        forbidden = ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
