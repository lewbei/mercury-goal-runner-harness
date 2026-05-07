import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / ".agentic-runs"
SOURCE_DIR = ROOT / ".agentic-pi" / "diagnostics" / "evaluation" / "cases" / "p2_strong"


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


class V1PackageFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.setup = load_module("setup_pi_smoke_for_v1_tests", ROOT / ".agentic-pi" / "runtime" / "setup_pi_smoke.py")

    def setUp(self):
        self.run_id = f"pi_smoke_v1_{self._testMethodName}"
        self.run_dir = RUN_ROOT / self.run_id
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def tearDown(self):
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def test_local_harness_helper_help_exposes_stable_command_surface(self):
        result = run_python(".agentic-pi/runtime/pi_cli.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Repo-local Verifier-Provenance harness helper", result.stdout)
        normalized_stdout = " ".join(result.stdout.split())
        self.assertIn("not the external Pi agent", normalized_stdout)
        for command in [
            "goal-init",
            "goal-compile",
            "goal-run",
            "goal-plan-proof",
            "goal-strategy-proof",
            "goal-milestone-proof",
            "goal-drift-proof",
            "goal-certify",
            "goal-status",
            "goal-replay",
            "goal-audit",
            "goal-rollback",
        ]:
            self.assertIn(command, result.stdout)
        self.assertIn("Final status comes only from", result.stdout)

    def test_pyproject_exposes_console_entrypoint(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn("mercury-goal = \"agentic_pi_cli:main\"", pyproject)
        self.assertIn("mercury-goal-runner-harness", pyproject)

    def test_cli_certify_status_audit_replay_and_rollback_dry_run(self):
        self.setup.setup_pi_smoke(SOURCE_DIR, self.run_id, clean=True)

        certify = run_python(".agentic-pi/runtime/pi_cli.py", "goal-certify", self.run_id)
        self.assertEqual(certify.returncode, 0, certify.stdout)
        self.assertEqual(load_json(self.run_dir / "certification.json")["status"], "CERTIFIED_DONE")

        status = run_python(".agentic-pi/runtime/pi_cli.py", "goal-status", self.run_id, "--fail-on-missing")
        self.assertEqual(status.returncode, 0, status.stdout)
        self.assertIn("CERTIFIED_DONE", status.stdout)

        audit = run_python(".agentic-pi/runtime/pi_cli.py", "goal-audit", self.run_id)
        self.assertEqual(audit.returncode, 0, audit.stdout)
        self.assertTrue(load_json(self.run_dir / "audit_report.json")["valid"])
        self.assertTrue(load_json(self.run_dir / "run_manifest.json")["provenance_mode"])

        replay = run_python(".agentic-pi/runtime/pi_cli.py", "goal-replay", self.run_id)
        self.assertEqual(replay.returncode, 0, replay.stdout)
        self.assertTrue(load_json(self.run_dir / "replay_report.json")["valid"])

        target_rel = "artifacts/output.txt"
        target = self.run_dir / target_rel
        backup = self.run_dir / "backups" / target_rel
        backup.parent.mkdir(parents=True)
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        rollback_module = load_module("rollback_run_for_v1_tests", ROOT / ".agentic-pi" / "runtime" / "rollback_run.py")
        backup_hash = rollback_module.sha256_file(backup)
        manifest = {
            "run_id": self.run_id,
            "target_path": target_rel,
            "backup_path": f"backups/{target_rel}",
            "original_hash": rollback_module.sha256_file(target),
            "backup_hash": backup_hash,
            "creator": "test",
            "timestamp": "2026-05-07T00:00:00Z",
            "phase": "v1_package_freeze",
            "reason": "dry-run sample",
        }
        manifest_path = self.run_dir / "backups" / f"{target_rel}.backup_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        rollback = run_python(".agentic-pi/runtime/pi_cli.py", "goal-rollback", self.run_id, "--file", target_rel)
        self.assertEqual(rollback.returncode, 0, rollback.stdout)
        rollback_report = load_json(self.run_dir / "rollback_report.json")
        self.assertEqual(rollback_report["mode"], "dry-run")
        self.assertFalse(rollback_report["applied"])

    def test_cli_status_does_not_require_policy_decision_for_legacy_run(self):
        init_result = run_python(".agentic-pi/runtime/pi_cli.py", "goal-init", self.run_id)
        self.assertEqual(init_result.returncode, 0, init_result.stdout)
        write_contract = run_python(
            ".agentic-pi/runtime/write_goal_contract.py",
            "--run-id",
            self.run_id,
            "--input",
            ".agentic-pi/benchmark/goals/simple_goal.json",
        )
        self.assertEqual(write_contract.returncode, 0, write_contract.stdout)
        self.assertEqual(load_json(self.run_dir / "goal_contract.json")["run_id"], self.run_id)
        run_result = run_python(
            ".agentic-pi/runtime/pi_cli.py",
            "goal-run",
            self.run_id,
            "--skip-memory-update",
        )
        self.assertEqual(run_result.returncode, 0, run_result.stdout)

        status = run_python(".agentic-pi/runtime/pi_cli.py", "goal-status", self.run_id, "--fail-on-missing")

        self.assertEqual(status.returncode, 0, status.stdout)
        self.assertIn("DONE_PASS", status.stdout)
        self.assertIn("SKIPPED_LEGACY", status.stdout)
        self.assertFalse((self.run_dir / "policy_decision.json").is_file())

    def test_v1_docs_lock_practical_package_boundary(self):
        freeze = (ROOT / "docs" / "V1_0_PRACTICAL_PACKAGE_FREEZE.md").read_text(encoding="utf-8")
        examples = (ROOT / "docs" / "V1_0_EXAMPLES.md").read_text(encoding="utf-8")

        self.assertIn("PRACTICAL PACKAGE FREEZE IMPLEMENTED", freeze)
        self.assertIn("goal-replay", freeze)
        self.assertIn("goal-audit", freeze)
        self.assertIn("goal-rollback", freeze)
        self.assertIn("The full Pi goal-runner chain is autonomously verified", freeze)
        self.assertIn("Final status still comes only from", examples)
        self.assertIn("PROVISIONAL_DONE", examples)
        self.assertIn("CERTIFIED_DONE", examples)
        self.assertIn("False-PASS Rejection", examples)


if __name__ == "__main__":
    unittest.main()
