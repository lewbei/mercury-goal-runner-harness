import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class ReplayAuditRollbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.setup = load_module("setup_pi_smoke_for_replay_tests", ROOT / ".agentic-pi" / "runtime" / "setup_pi_smoke.py")
        cls.rollback = load_module("rollback_run_for_tests", ROOT / ".agentic-pi" / "runtime" / "rollback_run.py")
        cls.validator = load_module("validate_schema_for_replay_tests", ROOT / ".agentic-pi" / "validators" / "validate_schema.py")

    def setUp(self):
        self.run_id = f"pi_smoke_replay_audit_{self._testMethodName}"
        self.run_dir = RUN_ROOT / self.run_id
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
        self.setup.setup_pi_smoke(SOURCE_DIR, self.run_id, clean=True)

    def tearDown(self):
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def certify(self):
        return run_python(".agentic-pi/validators/certify_run.py", str(self.run_dir))

    def validate_schema(self, instance, schema_name):
        schema = self.validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
        return self.validator.validate(instance, schema)

    def test_audit_and_replay_reports_are_valid(self):
        cert = self.certify()
        self.assertEqual(cert.returncode, 0, cert.stdout)

        audit = run_python(".agentic-pi/runtime/audit_run.py", str(self.run_dir))
        replay = run_python(".agentic-pi/runtime/replay_run.py", str(self.run_dir))

        self.assertEqual(audit.returncode, 0, audit.stdout)
        self.assertEqual(replay.returncode, 0, replay.stdout)
        audit_report = load_json(self.run_dir / "audit_report.json")
        run_manifest = load_json(self.run_dir / "run_manifest.json")
        replay_report = load_json(self.run_dir / "replay_report.json")
        self.assertTrue(audit_report["valid"])
        self.assertTrue(run_manifest["provenance_mode"])
        self.assertTrue(replay_report["valid"])
        self.assertTrue(replay_report["manifest_present"])
        self.assertIn("hash ok: artifacts/output.txt", replay_report["manifest_hash_checks"])
        self.assertEqual(self.validate_schema(audit_report, "audit_report.schema.json"), [])
        self.assertEqual(self.validate_schema(run_manifest, "run_manifest.schema.json"), [])
        self.assertEqual(self.validate_schema(replay_report, "replay_report.schema.json"), [])

    def test_invalid_audit_report_blocks_provenance_certification(self):
        write_json(
            self.run_dir / "audit_report.json",
            {
                "run_id": self.run_id,
                "valid": False,
                "checks": [],
                "violations": ["tampered output"],
                "artifact_hashes": [],
            },
        )

        cert = self.certify()

        self.assertNotEqual(cert.returncode, 0, cert.stdout)
        certification = load_json(self.run_dir / "certification.json")
        self.assertEqual(certification["status"], "NOT_DONE")
        self.assertIn("audit_report.json invalid blocks certification", certification["failed_checks"])

    def test_rollback_is_dry_run_by_default_and_apply_requires_valid_backup(self):
        target_rel = "artifacts/output.txt"
        target = self.run_dir / target_rel
        original = target.read_text(encoding="utf-8")
        backup = self.run_dir / "backups" / target_rel
        backup.parent.mkdir(parents=True)
        backup.write_text("rollback content\n", encoding="utf-8")
        backup_hash = self.rollback.sha256_file(backup)
        write_json(
            self.run_dir / "backups" / f"{target_rel}.backup_manifest.json",
            {
                "run_id": self.run_id,
                "target_path": target_rel,
                "backup_path": f"backups/{target_rel}",
                "original_hash": self.rollback.sha256_file(target),
                "backup_hash": backup_hash,
                "creator": "test",
                "timestamp": "2026-05-07T00:00:00Z",
                "phase": "rollback_test",
                "reason": "test rollback",
            },
        )
        self.assertEqual(
            self.validate_schema(
                load_json(self.run_dir / "backups" / f"{target_rel}.backup_manifest.json"),
                "backup_manifest.schema.json",
            ),
            [],
        )

        dry = run_python(".agentic-pi/runtime/rollback_run.py", str(self.run_dir), "--file", target_rel)
        self.assertEqual(dry.returncode, 0, dry.stdout)
        self.assertEqual(target.read_text(encoding="utf-8"), original)
        dry_report = load_json(self.run_dir / "rollback_report.json")
        self.assertFalse(dry_report["applied"])
        self.assertEqual(self.validate_schema(dry_report, "rollback_report.schema.json"), [])

        applied = run_python(".agentic-pi/runtime/rollback_run.py", str(self.run_dir), "--file", target_rel, "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout)
        self.assertEqual(target.read_text(encoding="utf-8"), "rollback content\n")

    def test_rollback_rejects_protected_status_artifact(self):
        result = run_python(".agentic-pi/runtime/rollback_run.py", str(self.run_dir), "--file", "final_status.md")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        report = load_json(self.run_dir / "rollback_report.json")
        self.assertIn("protected rollback target rejected", report["violations"])


if __name__ == "__main__":
    unittest.main()
