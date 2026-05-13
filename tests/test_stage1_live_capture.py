import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / ".agentic-pi" / "evaluation" / "stage1_multiframe"
VALIDATOR = ".agentic-pi/evaluation/stage1_multiframe/validate_stage1_live_capture.py"


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


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Stage1LiveCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="stage1_live_capture_test_"))
        self.prompt_set_path = EVAL_DIR / "prompt_set.json"
        self.fixture = load_json(EVAL_DIR / "live_capture_fixture.json")
        self.capture_path = self.tmpdir / "capture.json"
        write_json(self.capture_path, self.fixture)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def validate(self, *extra_args):
        return run_python(
            VALIDATOR,
            "--prompt-set",
            str(self.prompt_set_path),
            "--capture",
            str(self.capture_path),
            *extra_args,
        )

    def test_valid_subset_capture_fixture_passes_with_test_flag(self):
        result = self.validate("--allow-subset-for-tests")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("OK: stage1 live capture valid", result.stdout)
        self.assertFalse((self.tmpdir / "final_status.json").exists())

    def test_subset_capture_fails_without_test_flag(self):
        result = self.validate()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("subset_fixture_only captures require --allow-subset-for-tests", result.stdout)

    def test_missing_mode_fails(self):
        fixture = copy.deepcopy(self.fixture)
        first_prompt = fixture["captures"][0]["prompt_id"]
        fixture["captures"] = [
            record for record in fixture["captures"]
            if not (record["prompt_id"] == first_prompt and record["mode"] == "multiframe_harness")
        ]
        write_json(self.capture_path, fixture)

        result = self.validate("--allow-subset-for-tests")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("expected exactly modes", result.stdout)

    def test_duplicate_mode_fails(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["captures"].append(copy.deepcopy(fixture["captures"][0]))
        write_json(self.capture_path, fixture)

        result = self.validate("--allow-subset-for-tests")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("duplicate mode", result.stdout)

    def test_prompt_hash_tampering_fails(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["captures"][0]["prompt_text"] += " changed"
        write_json(self.capture_path, fixture)

        result = self.validate("--allow-subset-for-tests")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("prompt_text does not match", result.stdout)
        self.assertIn("prompt_hash mismatch", result.stdout)

    def test_output_hash_tampering_fails(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["captures"][0]["output_text"] += " changed"
        write_json(self.capture_path, fixture)

        result = self.validate("--allow-subset-for-tests")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("output_hash mismatch", result.stdout)

    def test_authority_overclaim_fails(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["authority"]["can_certify_done"] = True
        write_json(self.capture_path, fixture)

        result = self.validate("--allow-subset-for-tests")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("can_certify_done", result.stdout)

    def test_final_status_value_fails(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["captures"][0]["output_text"] = "This is CERTIFIED_DONE."
        fixture["captures"][0]["output_hash"] = sha256_text(fixture["captures"][0]["output_text"])
        write_json(self.capture_path, fixture)

        result = self.validate("--allow-subset-for-tests")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("final status value", result.stdout)

    def test_protected_artifact_reference_fails(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["captures"][0]["output_text"] = "See final_status.json for result."
        fixture["captures"][0]["output_hash"] = sha256_text(fixture["captures"][0]["output_text"])
        write_json(self.capture_path, fixture)

        result = self.validate("--allow-subset-for-tests")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("protected status artifact", result.stdout)

    def test_invalid_mode_fails_schema_validation(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["captures"][0]["mode"] = "single_prompt"
        write_json(self.capture_path, fixture)

        result = self.validate("--allow-subset-for-tests")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("schema", result.stdout)

    def test_full_capture_requires_all_prompts(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["capture_scope"] = "full_50_prompt_capture"
        write_json(self.capture_path, fixture)

        result = self.validate()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("missing prompt captures", result.stdout)

    def test_live_capture_validator_has_no_live_model_calls(self):
        source = (EVAL_DIR / "validate_stage1_live_capture.py").read_text(encoding="utf-8").lower()
        forbidden = ["requests", "urllib", "openai", "anthropic", "subprocess", " pi "]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
