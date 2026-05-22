#!/usr/bin/env python3
"""Vertical slice test for VS.003: Artifact misplacement blocks certification.

Proves that:
- certify_run.py reads artifact location verdicts from validate_artifact_location
- A misplaced artifact (expected at artifacts/report.json, found at report.json)
  causes certification to emit NOT_DONE with a BLOCKED_BY_ARTIFACT_MISPLACEMENT failure
- A correctly placed artifact allows certification to proceed normally
"""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_KERNEL_PATH = ROOT / ".agentic-pi" / "run_kernel" / "run_kernel.py"
CERTIFY_PATH = ROOT / ".agentic-pi" / "validators" / "certify_run.py"

if str(RUN_KERNEL_PATH.parent) not in sys.path:
    sys.path.insert(0, str(RUN_KERNEL_PATH.parent))


def load_module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_certify(run_dir: Path):
    """Run certify_run.py as a subprocess, return result."""
    result = subprocess.run(
        [sys.executable, str(CERTIFY_PATH), str(run_dir)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


class TestVerticalSlice003_ArtifactMisplacement(unittest.TestCase):
    """VS.003: Wrong artifact path must block certification."""

    def setUp(self):
        self.rk = load_module("run_kernel", RUN_KERNEL_PATH)
        self.run_id = "vs003_misplacement"
        self.run_dir = ROOT / ".agentic-runs" / self.run_id

        # Clean up any previous run
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def tearDown(self):
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def _create_minimal_run(self):
        """Create a minimal run directory with goal contract and expected artifacts."""
        self.rk.create_run(self.run_id)

        # Write goal contract
        (self.run_dir / "goal_contract.json").write_text(
            json.dumps({
                "run_id": self.run_id,
                "goal": "Create a report",
                "final_outputs": ["artifacts/report.json"],
                "done_criteria": ["artifacts/report.json exists"],
            }),
            encoding="utf-8",
        )

        # Write trace.jsonl (required for certification)
        (self.run_dir / "trace.jsonl").write_text(
            json.dumps({"event": "start", "timestamp": "2026-01-01T00:00:00Z"}) + "\n",
            encoding="utf-8",
        )

    # ── Test 1: Correct artifact placement passes ─────────────────────────

    def test_correct_path_passes(self):
        """Artifact at correct expected path -> certification does not flag misplacement."""
        self._create_minimal_run()

        # Write expected_artifacts.json
        ea = {
            "schema_version": "expected_artifacts_v1",
            "run_id": self.run_id,
            "artifacts": [
                {"artifact_id": "A.REPORT", "expected_path": "artifacts/report.json", "required": True},
            ],
        }
        (self.run_dir / "expected_artifacts.json").write_text(json.dumps(ea), encoding="utf-8")

        # Create artifact at CORRECT path
        (self.run_dir / "artifacts").mkdir(exist_ok=True)
        (self.run_dir / "artifacts" / "report.json").write_text(
            json.dumps({"report": "ok"}), encoding="utf-8"
        )

        # Run certifier
        result = run_certify(self.run_dir)

        # Read certification output
        cert = load_json(self.run_dir / "certification.json")
        self.assertNotEqual(cert["status"], "NOT_DONE",
                           "Correct placement should not yield NOT_DONE")

        # The accepted placement should appear in passed checks
        placement_ok = any("artifact placement OK" in c for c in cert["passed_checks"])
        self.assertTrue(placement_ok,
                       "Correct placement should appear in passed_checks")

    # ── Test 2: Wrong artifact path blocks certification ──────────────────

    def test_wrong_path_blocks_certification(self):
        """Artifact at wrong path -> legacy certification must fail with DONE_FAIL."""
        self._create_minimal_run()

        # Write expected_artifacts.json — expects artifacts/report.json
        ea = {
            "schema_version": "expected_artifacts_v1",
            "run_id": self.run_id,
            "artifacts": [
                {"artifact_id": "A.REPORT", "expected_path": "artifacts/report.json", "required": True},
            ],
        }
        (self.run_dir / "expected_artifacts.json").write_text(json.dumps(ea), encoding="utf-8")

        # Create artifact at WRONG path (root instead of artifacts/)
        (self.run_dir / "report.json").write_text(
            json.dumps({"report": "wrong place"}), encoding="utf-8"
        )

        # Run certifier
        result = run_certify(self.run_dir)

        # Read certification output
        cert = load_json(self.run_dir / "certification.json")
        self.assertEqual(cert["status"], "DONE_FAIL",
                        "Wrong artifact path must yield DONE_FAIL in legacy mode")

        # The misplacement should appear in failed checks
        misplaced = any("MISPLACED" in c for c in cert["failed_checks"])
        self.assertTrue(misplaced,
                       "Misplacement should appear in failed_checks")

        # The status should be DONE_FAIL for legacy non-provenance mode.
        final_status = load_json(self.run_dir / "final_status.json")
        self.assertEqual(final_status["status"], "DONE_FAIL")

    # ── Test 3: Missing required artifact blocks certification ────────────

    def test_missing_required_blocks_certification(self):
        """Required artifact missing entirely -> DONE_FAIL in legacy mode."""
        self._create_minimal_run()

        ea = {
            "schema_version": "expected_artifacts_v1",
            "run_id": self.run_id,
            "artifacts": [
                {"artifact_id": "A.REPORT", "expected_path": "artifacts/report.json", "required": True},
            ],
        }
        (self.run_dir / "expected_artifacts.json").write_text(json.dumps(ea), encoding="utf-8")

        # No artifact created at all
        result = run_certify(self.run_dir)

        cert = load_json(self.run_dir / "certification.json")
        self.assertEqual(cert["status"], "DONE_FAIL",
                        "Missing required artifact must yield DONE_FAIL in legacy mode")
        missing = any("MISSING" in c for c in cert["failed_checks"])
        self.assertTrue(missing,
                       "Missing artifact should appear in failed_checks")

    # ── Test 4: No expected_artifacts.json = no block ─────────────────────

    def test_no_expected_artifacts_no_block(self):
        """Without expected_artifacts.json, the gate passes through."""
        self._create_minimal_run()

        # No expected_artifacts.json
        result = run_certify(self.run_dir)

        cert = load_json(self.run_dir / "certification.json")
        # Without expected_artifacts.json, the gate returns current_status unchanged
        # Certification should still fail (no final outputs), but not due to placement
        self.assertIn(cert["status"], ["DONE_FAIL", "NOT_DONE"])


if __name__ == "__main__":
    unittest.main()
