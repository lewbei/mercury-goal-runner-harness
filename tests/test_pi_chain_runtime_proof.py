import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agentic-pi" / "runtime" / "run_pi_chain_smoke.py"
OUTPUT_DIR = ROOT / ".agentic-runs" / "pi_chain_smoke_outputs"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_schema_validator():
    module_path = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
    spec = importlib.util.spec_from_file_location("validate_schema", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


class PiChainRuntimeProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_module("run_pi_chain_smoke_for_tests", SCRIPT)
        cls.validator = load_schema_validator()

    def tearDown(self):
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)

    def validate_schema(self, instance, schema_name):
        schema = self.validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
        return self.validator.validate(instance, schema)

    def test_step_definitions_lock_chain_roles_and_permissions(self):
        steps = self.runner.build_step_definitions("pi_smoke_chain_test")

        self.assertEqual(
            [step["agent"] for step in steps],
            ["verifier-generator", "verifier-reviewer", "goal-orchestrator"],
        )
        self.assertEqual(steps[0]["tools"], "read,ls")
        self.assertEqual(steps[1]["tools"], "read,ls")
        self.assertEqual(steps[2]["tools"], "bash,read,ls")
        for step in steps:
            self.assertFalse(step["allowed_to_write"])
            self.assertIn("Do not certify DONE yourself", step["prompt"])
            self.assertIn("Final status comes only from certify_run.py", step["prompt"])
        self.assertIn("Do not ask a follow-up question", steps[2]["prompt"])
        self.assertIn("You already have all required file paths", steps[2]["prompt"])
        self.assertEqual(
            steps[2]["allowed_bash_command"],
            "python .agentic-pi/validators/certify_run.py .agentic-runs/pi_smoke_chain_test",
        )

    def test_pi_commands_disable_extensions_and_do_not_enable_write_tools(self):
        steps = self.runner.build_step_definitions("pi_smoke_chain_test")

        for step in steps:
            command = self.runner.build_pi_command(step)
            joined = " ".join(command)

            self.assertIn("--no-extensions", command)
            self.assertIn("--no-skills", command)
            self.assertIn("--append-system-prompt", command)
            self.assertNotIn("write", step["tools"])
            self.assertNotIn("edit", step["tools"])
            self.assertNotIn("apply_patch", step["tools"])
            self.assertIn(step["system_prompt"], joined)

    def test_dry_run_result_is_schema_valid_and_non_certifying(self):
        result = self.runner.dry_run_result("pi_smoke_chain_test")

        self.assertEqual(self.validate_schema(result, "pi_chain_runtime_result.schema.json"), [])
        self.assertEqual(result["result_status"], "PLANNED")
        self.assertFalse(result["live"])
        self.assertFalse(result["can_certify_done"])
        self.assertEqual(result["final_status_authority"], "certifier_only")
        self.assertEqual(result["status_values"]["final_status.md"], "NOT_RUN")

    def test_dry_run_cli_writes_schema_valid_output_under_agentic_runs(self):
        result = run_python(
            ".agentic-pi/runtime/run_pi_chain_smoke.py",
            "--target-run-id",
            "pi_smoke_chain_test",
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        output_path = OUTPUT_DIR / "pi_chain_runtime_result.json"
        self.assertTrue(output_path.is_file())
        smoke_result = load_json(output_path)
        self.assertEqual(self.validate_schema(smoke_result, "pi_chain_runtime_result.schema.json"), [])
        self.assertEqual(smoke_result["result_status"], "PLANNED")
        self.assertIn(".agentic-runs", output_path.as_posix())

    def test_rejects_non_smoke_target(self):
        result = run_python(
            ".agentic-pi/runtime/run_pi_chain_smoke.py",
            "--target-run-id",
            "regular_chain_target",
        )

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("target run id must start with pi_smoke_", result.stdout)

    def test_v21_doc_locks_controlled_chain_boundary(self):
        doc = (ROOT / "docs" / "V2_1_CONTROLLED_PI_CHAIN_RUNTIME_PROOF.md").read_text(encoding="utf-8")

        self.assertIn("CONTROLLED PI CHAIN RUNTIME PROOF IMPLEMENTED", doc)
        self.assertIn("verifier-generator -> verifier-reviewer -> goal-orchestrator", doc)
        self.assertIn("certifier command", doc)
        self.assertIn("final_status_authority = certifier_only", doc)
        self.assertIn("can_certify_done = false", doc)
        self.assertIn("full Pi goal-runner chain is autonomously verified", doc)


if __name__ == "__main__":
    unittest.main()
