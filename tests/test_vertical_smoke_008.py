#!/usr/bin/env python3
"""Unittest for VS.008: Full vertical smoke CLI.

Proves that `run_vertical_smoke.py` runs all 10 steps of the
harness pipeline and returns exit code 0.
"""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = ROOT / ".agentic-pi" / "diagnostics" / "vertical_smoke" / "run_vertical_smoke.py"


class TestVerticalSmokeCLI(unittest.TestCase):
    """VS.008: run_vertical_smoke.py passes all 10 steps."""

    def test_cli_returns_zero(self):
        """CLI exits with code 0 (all steps pass)."""
        result = subprocess.run(
            [sys.executable, str(SMOKE_PATH)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True,
        )
        output = result.stdout

        # Must show VERTICAL_SMOKE_PASSED
        self.assertIn("VERTICAL_SMOKE_PASSED", output,
                     "CLI must report VERTICAL_SMOKE_PASSED")
        self.assertEqual(result.returncode, 0,
                        f"CLI must exit 0, got {result.returncode}")

    def test_all_10_steps_reported(self):
        """All 10 steps appear in the output."""
        result = subprocess.run(
            [sys.executable, str(SMOKE_PATH)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True,
        )

        expected_steps = [
            "CREATE_RUN", "SETUP_RUN", "TRANSITION_INTAKE",
            "DISPATCH_PACKET", "RECEIVE_RESULT", "ACCEPT_PACKET",
            "FREEZE_EVIDENCE", "REPLAY", "CERTIFY", "DISPATCH_LOG",
        ]
        for step in expected_steps:
            self.assertIn(step, result.stdout,
                         f"Step '{step}' must appear in CLI output")

    def test_all_steps_pass(self):
        """Every step shows PASS result."""
        result = subprocess.run(
            [sys.executable, str(SMOKE_PATH)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True,
        )

        lines = result.stdout.splitlines()
        step_lines = [l for l in lines if "PASS" in l and "Result" not in l]
        fail_lines = [l for l in lines if "FAIL" in l and "status=DONE_FAIL" not in l]

        self.assertGreater(len(step_lines), 0,
                          "There should be PASS lines in the output")
        self.assertEqual(len(fail_lines), 0,
                        f"There should be no FAIL lines: {fail_lines}")


if __name__ == "__main__":
    unittest.main()
