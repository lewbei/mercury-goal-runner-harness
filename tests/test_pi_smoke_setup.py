import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = ROOT / ".agentic-pi" / "runtime" / "setup_pi_smoke.py"
SOURCE_DIR = ROOT / ".agentic-pi" / "diagnostics" / "evaluation" / "cases" / "p2_strong"
RUN_ROOT = ROOT / ".agentic-runs"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
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


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


class PiSmokeSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.setup_module = load_module("setup_pi_smoke_for_tests", SETUP_SCRIPT)

    def setUp(self):
        self.target_run_id = "pi_smoke_test_setup_p2_strong"
        self.target_dir = RUN_ROOT / self.target_run_id
        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)

    def tearDown(self):
        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)

    def test_setup_creates_disposable_run_and_preserves_source_hashes(self):
        before = self.setup_module.snapshot_source(SOURCE_DIR)
        report = self.setup_module.setup_pi_smoke(SOURCE_DIR, self.target_run_id)
        after = self.setup_module.snapshot_source(SOURCE_DIR)

        self.assertTrue(self.target_dir.is_dir())
        self.assertEqual(before, after)
        self.assertTrue(report["source_unchanged"])
        self.assertEqual(report["target_run_id"], self.target_run_id)
        self.assertEqual(
            report["next_certifier_command"],
            "python .agentic-pi/validators/certify_run.py "
            ".agentic-runs/pi_smoke_test_setup_p2_strong",
        )

        goal = load_json(self.target_dir / "goal_contract.json")
        verifier_contract = load_json(self.target_dir / "verifier_contract.json")
        step_log = load_json(self.target_dir / "step_logs" / "001.json")
        verifier_artifact = load_json(self.target_dir / "verifier_artifacts" / "V.P2_STRONG.json")

        self.assertEqual(goal["run_id"], self.target_run_id)
        self.assertEqual(verifier_contract["run_id"], self.target_run_id)
        self.assertEqual(step_log["run_id"], self.target_run_id)
        self.assertEqual(verifier_artifact["run_id"], self.target_run_id)
        self.assertTrue((self.target_dir / "artifacts" / "output.txt").is_file())

    def test_setup_removes_generated_certifier_outputs_only_in_target(self):
        self.setup_module.setup_pi_smoke(SOURCE_DIR, self.target_run_id)
        for rel_path in [
            "final_status.md",
            "certification.json",
            "policy_decision.json",
            "verifier_smell_reports",
            "verifier_strength_reports",
        ]:
            self.assertFalse((self.target_dir / rel_path).exists(), rel_path)

    def test_setup_rejects_non_smoke_target(self):
        with self.assertRaises(ValueError):
            self.setup_module.setup_pi_smoke(SOURCE_DIR, "regular_run_should_fail")

    def test_setup_cli_runs_and_is_idempotent_with_clean(self):
        result = run_python(
            str(SETUP_SCRIPT),
            "--source",
            ".agentic-pi/diagnostics/evaluation/cases/p2_strong",
            "--target-run-id",
            self.target_run_id,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('"status": "PASS"', result.stdout)

        second = run_python(
            str(SETUP_SCRIPT),
            "--source",
            ".agentic-pi/diagnostics/evaluation/cases/p2_strong",
            "--target-run-id",
            self.target_run_id,
        )
        self.assertEqual(second.returncode, 1, second.stdout)
        self.assertIn("pass --clean", second.stdout)

        clean = run_python(
            str(SETUP_SCRIPT),
            "--source",
            ".agentic-pi/diagnostics/evaluation/cases/p2_strong",
            "--target-run-id",
            self.target_run_id,
            "--clean",
        )
        self.assertEqual(clean.returncode, 0, clean.stdout)

    def test_prepared_run_certifies_after_setup(self):
        self.setup_module.setup_pi_smoke(SOURCE_DIR, self.target_run_id)
        result = run_python(
            ".agentic-pi/validators/certify_run.py",
            str(self.target_dir),
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            load_json(self.target_dir / "certification.json")["status"],
            "CERTIFIED_DONE",
        )
        self.assertEqual(
            load_json(self.target_dir / "policy_decision.json")["status"],
            "CERTIFIED_DONE",
        )


if __name__ == "__main__":
    unittest.main()
