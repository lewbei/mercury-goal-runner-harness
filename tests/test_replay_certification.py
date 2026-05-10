#!/usr/bin/env python3
"""Unittest tests for RPG-Harness v5 Phase 6: Replay Certification.

Tests cover:
- replay_rules.json structure
- replay_certification.py evidence hashing, checks, verdicts
- validate_replay_matches_policy.py
- Integration with existing certification runs
- Mismatch detection for changed evidence
"""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLAY_DIR = ROOT / ".agentic-pi" / "replay"
REPLAY_VALIDATORS_DIR = REPLAY_DIR / "validators"

for d in [REPLAY_DIR, REPLAY_VALIDATORS_DIR]:
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_module(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


_RC = None
_RMP = None


def _get_rc():
    global _RC
    if _RC is None:
        _RC = load_module("replay_certification",
                          REPLAY_DIR / "replay_certification.py")
    return _RC


def _get_rmp():
    global _RMP
    if _RMP is None:
        _RMP = load_module("validate_replay_matches_policy",
                           REPLAY_VALIDATORS_DIR / "validate_replay_matches_policy.py")
    return _RMP


# ══════════════════════════════════════════════════════════════════════════════
#  Schema File Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaFiles(unittest.TestCase):
    """Verify all Phase 6 files exist."""

    def test_replay_rules(self):
        self.assertTrue((REPLAY_DIR / "replay_rules.json").exists())

    def test_replay_certification(self):
        self.assertTrue((REPLAY_DIR / "replay_certification.py").exists())

    def test_validate_replay_matches_policy(self):
        self.assertTrue((REPLAY_VALIDATORS_DIR / "validate_replay_matches_policy.py").exists())


# ══════════════════════════════════════════════════════════════════════════════
#  Replay Rules Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestReplayRules(unittest.TestCase):
    """Test replay_rules.json structure."""

    def setUp(self):
        self.rules = load_json(REPLAY_DIR / "replay_rules.json")

    def test_schema_version(self):
        self.assertEqual(self.rules["schema_version"], "replay_rules_v1")

    def test_has_rules(self):
        self.assertGreater(len(self.rules["rules"]), 0)

    def test_key_rules_present(self):
        rule_ids = {r["id"] for r in self.rules["rules"]}
        self.assertIn("evidence_freeze_exists", rule_ids)
        self.assertIn("evidence_hashes_match", rule_ids)
        self.assertIn("certification_exists", rule_ids)
        self.assertIn("policy_cert_match", rule_ids)
        self.assertIn("final_status_cert_match", rule_ids)

    def test_has_verdicts(self):
        self.assertIn("REPLAY_MATCH", self.rules["replay_verdicts"])
        self.assertIn("REPLAY_MISMATCH", self.rules["replay_verdicts"])
        self.assertIn("REPLAY_PARTIAL", self.rules["replay_verdicts"])

    def test_rule_severity(self):
        for rule in self.rules["rules"]:
            self.assertIn(rule["severity"], ["FAILED", "WARNING"])


# ══════════════════════════════════════════════════════════════════════════════
#  Evidence Hashing Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestEvidenceHashing(unittest.TestCase):
    """Test compute_evidence_hashes."""

    def setUp(self):
        self.rc = _get_rc()
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _make_file(self, path: str, content: str = "data"):
        full = self.tmp / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    def test_empty_dir_returns_empty(self):
        hashes = self.rc.compute_evidence_hashes(self.tmp)
        self.assertEqual(hashes, {})

    def test_core_files_hashed(self):
        self._make_file("goal_contract.json", '{"goal": "test"}')
        self._make_file("trace.jsonl", '{"event": "start"}\n')
        self._make_file("certification.json", '{"status": "DONE"}')
        hashes = self.rc.compute_evidence_hashes(self.tmp)
        self.assertIn("goal_contract.json", hashes)
        self.assertIn("trace.jsonl", hashes)
        self.assertIn("certification.json", hashes)

    def test_hashes_are_sha256(self):
        self._make_file("goal_contract.json", '{"goal": "test"}')
        hashes = self.rc.compute_evidence_hashes(self.tmp)
        self.assertEqual(len(hashes["goal_contract.json"]), 64)  # SHA256 hex length

    def test_step_logs_hashed(self):
        self._make_file("step_logs/001.json", '{"step": 1}')
        self._make_file("step_logs/002.json", '{"step": 2}')
        hashes = self.rc.compute_evidence_hashes(self.tmp)
        self.assertIn("step_logs/001.json", hashes)
        self.assertIn("step_logs/002.json", hashes)

    def test_verifier_artifacts_hashed(self):
        self._make_file("verifier_artifacts/V.PASS.json", '{"verdict": "PASS"}')
        hashes = self.rc.compute_evidence_hashes(self.tmp)
        self.assertIn("verifier_artifacts/V.PASS.json", hashes)

    def test_hash_stability(self):
        self._make_file("data.txt", "hello")
        h1 = self.rc.compute_evidence_hashes(self.tmp)
        h2 = self.rc.compute_evidence_hashes(self.tmp)
        self.assertEqual(h1, h2)

    def test_hash_changes_on_content_change(self):
        self._make_file("data.txt", "hello")
        h1 = self.rc.compute_evidence_hashes(self.tmp)
        self._make_file("data.txt", "world")
        h2 = self.rc.compute_evidence_hashes(self.tmp)
        self.assertNotEqual(h1["data.txt"], h2["data.txt"])


# ══════════════════════════════════════════════════════════════════════════════
#  Replay Certification Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestReplayCertification(unittest.TestCase):
    """Test run_replay_certification."""

    def setUp(self):
        self.rc = _get_rc()
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _make_file(self, path: str, content: str = "data"):
        full = self.tmp / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    def _make_minimal_valid_run(self):
        """Create a minimal run directory that would pass replay."""
        self._make_file("goal_contract.json", json.dumps({"run_id": "replay_test_001", "goal": "test"}))
        self._make_file("trace.jsonl", '{"event": "start", "timestamp": "2026-01-01T00:00:00Z"}\n')
        self._make_file("step_logs/001.json", json.dumps({"step": 1, "status": "PASSED"}))
        self._make_file("certification.json", json.dumps({"status": "CERTIFIED_DONE", "schema_version": "certification_v1"}))
        self._make_file("policy_decision.json", json.dumps({"status": "CERTIFIED_DONE", "schema_version": "policy_decision_v1"}))
        self._make_file("final_status.json", json.dumps({"status": "CERTIFIED_DONE", "final_status_authority": "certifier_only"}))

        # Create evidence freeze with current hashes
        current_hashes = self.rc.compute_evidence_hashes(self.tmp)
        self._make_file("evidence_freeze.json", json.dumps({
            "artifact_hashes": current_hashes,
            "frozen_at": "2026-05-08T00:00:00Z",
        }))

    def test_replay_match_on_valid_run(self):
        self._make_minimal_valid_run()
        report = self.rc.run_replay_certification(self.tmp)
        self.assertEqual(report["verdict"], "REPLAY_MATCH")
        self.assertTrue(all(c["passed"] for c in report["checks"].values()))

    def test_replay_mismatch_when_evidence_changes(self):
        self._make_minimal_valid_run()

        # Change a file after freeze
        self._make_file("goal_contract.json", json.dumps({"run_id": "CHANGED", "goal": "hacked"}))

        report = self.rc.run_replay_certification(self.tmp)
        self.assertEqual(report["verdict"], "REPLAY_MISMATCH")
        self.assertFalse(report["checks"]["evidence_hashes_match"]["passed"])

    def test_replay_mismatch_when_file_removed(self):
        self._make_minimal_valid_run()

        # Remove a file
        (self.tmp / "step_logs" / "001.json").unlink()

        report = self.rc.run_replay_certification(self.tmp)
        self.assertEqual(report["verdict"], "REPLAY_MISMATCH")

    def test_replay_mismatch_when_new_file_added(self):
        self._make_minimal_valid_run()

        # Add a file not in freeze
        self._make_file("unauthorized.txt", "sneaky data")

        report = self.rc.run_replay_certification(self.tmp)
        self.assertEqual(report["verdict"], "REPLAY_MISMATCH")
        self.assertFalse(report["checks"]["evidence_hashes_match"]["passed"])

    def test_no_evidence_freeze(self):
        """Without evidence_freeze.json, replay should still run but note the gap."""
        self._make_file("goal_contract.json", json.dumps({"run_id": "no_freeze"}))
        self._make_file("trace.jsonl", '{"event": "x"}\n')
        self._make_file("step_logs/001.json", '{}')
        self._make_file("certification.json", json.dumps({"status": "DONE_PASS"}))
        self._make_file("final_status.json", json.dumps({"status": "DONE_PASS"}))
        # Missing policy_decision.json is OK for legacy

        report = self.rc.run_replay_certification(self.tmp)
        # Should fail on evidence_freeze_exists, policy_decision_exists
        self.assertFalse(report["checks"]["evidence_freeze_exists"]["passed"])

    def test_missing_certification(self):
        self._make_minimal_valid_run()
        (self.tmp / "certification.json").unlink()

        report = self.rc.run_replay_certification(self.tmp)
        self.assertFalse(report["checks"]["certification_exists"]["passed"])
        self.assertEqual(report["verdict"], "REPLAY_MISMATCH")

    def test_policy_cert_mismatch(self):
        self._make_minimal_valid_run()
        # Change policy to disagree with certification
        self._make_file("policy_decision.json", json.dumps({"status": "NOT_DONE"}))

        # Re-freeze with new hashes (otherwise hash mismatch would also be detected)
        current_hashes = self.rc.compute_evidence_hashes(self.tmp)
        self._make_file("evidence_freeze.json", json.dumps({"artifact_hashes": current_hashes}))

        report = self.rc.run_replay_certification(self.tmp)
        self.assertFalse(report["checks"]["policy_cert_match"]["passed"])
        self.assertEqual(report["verdict"], "REPLAY_MISMATCH")

    def test_report_structure(self):
        self._make_minimal_valid_run()
        report = self.rc.run_replay_certification(self.tmp)
        self.assertIn("schema_version", report)
        self.assertIn("verdict", report)
        self.assertIn("checks", report)
        self.assertIn("failed_severity_checks", report)
        self.assertIn("warning_checks", report)
        self.assertIn("evidence_hash_count", report)
        self.assertIn("frozen_evidence_hash_count", report)

    def test_replay_report_written(self):
        self._make_minimal_valid_run()
        self.rc.run_replay_certification(self.tmp)
        report = load_json(self.tmp / "replay_report.json")
        self.assertIsNotNone(report)
        self.assertEqual(report["verdict"], "REPLAY_MATCH")


# ══════════════════════════════════════════════════════════════════════════════
#  Replay Matches Policy Validator Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestReplayMatchesPolicy(unittest.TestCase):
    """Test validate_replay_matches_policy.py."""

    def setUp(self):
        self.rmp = _get_rmp()
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _make_file(self, path: str, content: str):
        full = self.tmp / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    def test_match_when_all_consistent(self):
        self._make_file("replay_report.json", json.dumps({"verdict": "REPLAY_MATCH"}))
        self._make_file("policy_decision.json", json.dumps({"status": "CERTIFIED_DONE"}))
        self._make_file("certification.json", json.dumps({"status": "CERTIFIED_DONE"}))
        self._make_file("final_status.json", json.dumps({"status": "CERTIFIED_DONE"}))

        result = self.rmp.validate_replay_matches_policy(self.tmp)
        self.assertTrue(result["valid"])

    def test_mismatch_when_replay_mismatch_but_status_is_done(self):
        self._make_file("replay_report.json", json.dumps({"verdict": "REPLAY_MISMATCH"}))
        self._make_file("policy_decision.json", json.dumps({"status": "CERTIFIED_DONE"}))
        self._make_file("certification.json", json.dumps({"status": "CERTIFIED_DONE"}))
        self._make_file("final_status.json", json.dumps({"status": "CERTIFIED_DONE"}))

        result = self.rmp.validate_replay_matches_policy(self.tmp)
        self.assertFalse(result["valid"])

    def test_match_when_replay_mismatch_but_all_not_done(self):
        """Replay mismatch is expected when the run genuinely failed."""
        self._make_file("replay_report.json", json.dumps({"verdict": "REPLAY_MISMATCH"}))
        self._make_file("policy_decision.json", json.dumps({"status": "NOT_DONE"}))
        self._make_file("certification.json", json.dumps({"status": "NOT_DONE"}))
        self._make_file("final_status.json", json.dumps({"status": "NOT_DONE"}))

        result = self.rmp.validate_replay_matches_policy(self.tmp)
        self.assertTrue(result["valid"])

    def test_no_replay_report(self):
        result = self.rmp.validate_replay_matches_policy(self.tmp)
        self.assertFalse(result["valid"])

    def test_policy_cert_disagreement(self):
        self._make_file("replay_report.json", json.dumps({"verdict": "REPLAY_MATCH"}))
        self._make_file("policy_decision.json", json.dumps({"status": "CERTIFIED_DONE"}))
        self._make_file("certification.json", json.dumps({"status": "NOT_DONE"}))
        self._make_file("final_status.json", json.dumps({"status": "NOT_DONE"}))

        result = self.rmp.validate_replay_matches_policy(self.tmp)
        self.assertFalse(result["valid"])

    def test_partial_replay_is_match_if_consistent(self):
        self._make_file("replay_report.json", json.dumps({"verdict": "REPLAY_PARTIAL"}))
        self._make_file("policy_decision.json", json.dumps({"status": "PROVISIONAL_DONE"}))
        self._make_file("certification.json", json.dumps({"status": "PROVISIONAL_DONE"}))
        self._make_file("final_status.json", json.dumps({"status": "PROVISIONAL_DONE"}))

        result = self.rmp.validate_replay_matches_policy(self.tmp)
        self.assertTrue(result["valid"])


# ══════════════════════════════════════════════════════════════════════════════
#  Integration Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestReplayIntegration(unittest.TestCase):
    """Integration with existing run data."""

    def setUp(self):
        self.rc = _get_rc()
        self.rmp = _get_rmp()
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _make_file(self, path: str, content: str):
        full = self.tmp / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    def test_full_replay_pipeline(self):
        """Full pipeline: create run -> certify -> freeze -> replay -> validate."""
        # Simulate a full run
        self._make_file("goal_contract.json", json.dumps({"run_id": "integ_test_001", "goal": "test"}))
        self._make_file("trace.jsonl", '{"event": "start"}\n{"event": "end"}\n')
        self._make_file("step_logs/001.json", json.dumps({"step": 1, "status": "PASSED"}))
        self._make_file("certification.json", json.dumps({"status": "CERTIFIED_DONE"}))
        self._make_file("policy_decision.json", json.dumps({"status": "CERTIFIED_DONE"}))
        self._make_file("final_status.json", json.dumps({"status": "CERTIFIED_DONE"}))

        # Freeze evidence
        current_hashes = self.rc.compute_evidence_hashes(self.tmp)
        self._make_file("evidence_freeze.json", json.dumps({"artifact_hashes": current_hashes}))

        # Replay
        report = self.rc.run_replay_certification(self.tmp)
        self.assertEqual(report["verdict"], "REPLAY_MATCH")

        # Validate match
        match_result = self.rmp.validate_replay_matches_policy(self.tmp)
        self.assertTrue(match_result["valid"])

    def test_tampered_evidence_detected(self):
        """Tampered evidence leads to REPLAY_MISMATCH."""
        self._make_file("goal_contract.json", json.dumps({"run_id": "tamper_test", "goal": "original"}))
        self._make_file("trace.jsonl", '{"event": "start"}\n')
        self._make_file("step_logs/001.json", json.dumps({"step": 1, "status": "PASSED"}))
        self._make_file("certification.json", json.dumps({"status": "CERTIFIED_DONE"}))
        self._make_file("policy_decision.json", json.dumps({"status": "CERTIFIED_DONE"}))
        self._make_file("final_status.json", json.dumps({"status": "CERTIFIED_DONE"}))

        # Freeze
        current_hashes = self.rc.compute_evidence_hashes(self.tmp)
        self._make_file("evidence_freeze.json", json.dumps({"artifact_hashes": current_hashes}))

        # Tamper
        self._make_file("goal_contract.json", json.dumps({"run_id": "tamper_test", "goal": "TAMPERED"}))

        # Replay should detect
        report = self.rc.run_replay_certification(self.tmp)
        self.assertEqual(report["verdict"], "REPLAY_MISMATCH")

    def test_existing_replay_run_file(self):
        """Verify the original replay_run.py output conventions are compatible."""
        self._make_file("goal_contract.json", json.dumps({"run_id": "legacy_test"}))
        self._make_file("trace.jsonl", '{"event": "x"}\n')
        self._make_file("step_logs/001.json", '{}')
        self._make_file("certification.json", json.dumps({"status": "DONE_PASS"}))
        self._make_file("final_status.json", json.dumps({"status": "DONE_PASS"}))

        # No evidence_freeze.json - should still get a verdict
        report = self.rc.run_replay_certification(self.tmp)
        self.assertIn("verdict", report)


if __name__ == "__main__":
    unittest.main()
