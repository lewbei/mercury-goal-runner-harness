"""Regression tests for certifier gates (certifier_gates.py).

The golden behavior lock tests cover replay, evidence freeze, memory authority,
done criteria, and validator certification. These tests cover the remaining 5
gates that have no regression tests.

Gates tested here:
  apply_formal_verification_gate
  apply_cryptographic_signature_gate
  apply_artifact_location_gate
  apply_audit_report_gate
  apply_drift_report_gate
"""
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATORS = ROOT / ".agentic-pi" / "validators"


def _load_module():
    import importlib.util
    import sys
    # Add validators dir to path so certifier_gates can find certifier_io
    validators_dir = str(VALIDATORS)
    if validators_dir not in sys.path:
        sys.path.insert(0, validators_dir)
    spec = importlib.util.spec_from_file_location(
        "certifier_gates", VALIDATORS / "certifier_gates.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFormalVerificationGate(unittest.TestCase):
    """Tests for apply_formal_verification_gate."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.failed = []
        self.passed = []

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_artifacts_dir_is_informational(self):
        """Missing verifier_artifacts dir is informational, not blocking."""
        result = self.mod.apply_formal_verification_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "CERTIFIED_DONE")
        self.assertTrue(any("informational" in p for p in self.passed))

    def test_no_formal_artifacts_is_informational(self):
        """No F_*.json files is informational, not blocking."""
        (self.tmpdir / "verifier_artifacts").mkdir()
        result = self.mod.apply_formal_verification_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "CERTIFIED_DONE")

    def test_passing_formal_verification_keeps_status(self):
        """PASS verdict keeps current status."""
        va_dir = self.tmpdir / "verifier_artifacts"
        va_dir.mkdir()
        artifact = {
            "kind": "formal_verification",
            "verdict": "PASS",
            "formal_verification_detail": {"confidence": 0.95}
        }
        (va_dir / "F_TEST.json").write_text(json.dumps(artifact))

        result = self.mod.apply_formal_verification_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "CERTIFIED_DONE")
        self.assertTrue(any("PASS" in p for p in self.passed))

    def test_failing_formal_verification_downgrades_status(self):
        """FAIL verdict downgrades CERTIFIED_DONE to DONE_FAIL."""
        va_dir = self.tmpdir / "verifier_artifacts"
        va_dir.mkdir()
        artifact = {
            "kind": "formal_verification",
            "verdict": "FAIL",
            "formal_verification_detail": {"confidence": 0.0}
        }
        (va_dir / "F_TEST.json").write_text(json.dumps(artifact))

        result = self.mod.apply_formal_verification_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "DONE_FAIL")
        self.assertTrue(any("FAIL" in f for f in self.failed))


class TestCryptographicSignatureGate(unittest.TestCase):
    """Tests for apply_cryptographic_signature_gate."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.failed = []
        self.passed = []

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_signatures_is_informational(self):
        """No .sig files is informational, not blocking."""
        result = self.mod.apply_cryptographic_signature_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "CERTIFIED_DONE")
        self.assertTrue(any("informational" in p for p in self.passed))


class TestArtifactLocationGate(unittest.TestCase):
    """Tests for apply_artifact_location_gate."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.failed = []
        self.passed = []

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_expected_artifacts_is_pass_through(self):
        """No expected_artifacts.json means gate passes through."""
        result = self.mod.apply_artifact_location_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "CERTIFIED_DONE")


class TestAuditReportGate(unittest.TestCase):
    """Tests for apply_audit_report_gate."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.failed = []
        self.passed = []

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_audit_report_is_pass_through(self):
        """No audit_report.json means gate passes through."""
        result = self.mod.apply_audit_report_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "CERTIFIED_DONE")

    def test_valid_audit_report_passes(self):
        """Valid audit_report.json passes."""
        audit = {"valid": True}
        (self.tmpdir / "audit_report.json").write_text(json.dumps(audit))

        result = self.mod.apply_audit_report_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "CERTIFIED_DONE")
        self.assertTrue(any("valid" in p for p in self.passed))

    def test_invalid_audit_report_blocks(self):
        """audit_report.json with valid=False blocks certification."""
        audit = {"valid": False, "violations": ["test violation"]}
        (self.tmpdir / "audit_report.json").write_text(json.dumps(audit))

        result = self.mod.apply_audit_report_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "NOT_DONE")
        self.assertTrue(any("violation" in f for f in self.failed))


class TestDriftReportGate(unittest.TestCase):
    """Tests for apply_drift_report_gate."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.failed = []
        self.passed = []

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_drift_report_is_pass_through(self):
        """No drift_report.json means gate passes through."""
        result = self.mod.apply_drift_report_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "CERTIFIED_DONE")

    def test_valid_drift_report_passes(self):
        """Valid drift_report.json with drift_level=none passes."""
        drift = {
            "run_id": "test",
            "generated_by": "test",
            "generated_at": "2026-01-01T00:00:00Z",
            "valid": True,
            "drift_level": "none",
            "blocking": False,
            "recommended_action": "continue",
            "violations": []
        }
        (self.tmpdir / "drift_report.json").write_text(json.dumps(drift))

        result = self.mod.apply_drift_report_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "CERTIFIED_DONE")
        self.assertTrue(any("none" in p for p in self.passed))

    def test_fatal_drift_blocks(self):
        """drift_level=fatal blocks certification."""
        drift = {
            "run_id": "test",
            "generated_by": "test",
            "generated_at": "2026-01-01T00:00:00Z",
            "valid": True,
            "drift_level": "fatal",
            "blocking": True,
            "recommended_action": "abort_requires_user",
            "violations": ["data loss"]
        }
        (self.tmpdir / "drift_report.json").write_text(json.dumps(drift))

        result = self.mod.apply_drift_report_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "NOT_DONE")
        self.assertTrue(any("fatal" in f for f in self.failed))

    def test_blocking_drift_blocks(self):
        """blocking=True blocks certification."""
        drift = {
            "run_id": "test",
            "generated_by": "test",
            "generated_at": "2026-01-01T00:00:00Z",
            "valid": True,
            "drift_level": "repairable",
            "blocking": True,
            "recommended_action": "generate_delta_plan",
            "violations": []
        }
        (self.tmpdir / "drift_report.json").write_text(json.dumps(drift))

        result = self.mod.apply_drift_report_gate(
            self.tmpdir, True, self.failed, self.passed, "CERTIFIED_DONE"
        )
        self.assertEqual(result, "NOT_DONE")


if __name__ == "__main__":
    unittest.main()
