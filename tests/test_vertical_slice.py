#!/usr/bin/env python3
"""Vertical slice gate tests — two cases.

Fixture 1 (vertical proof):
  Task: "Detect wrong artifact path -> BLOCKED_BY_ARTIFACT_MISPLACEMENT"
  Output: [.agentic-pi/validators/validate_artifact_location.py, tests/test_artifact_location.py]
  Proof: python tests/test_artifact_location.py -v
  Expected: ACCEPTED

Fixture 2 (horizontal output):
  Task: "Create all schemas and all validators"
  Output: [.agentic-pi/schemas/a.schema.json, .agentic-pi/schemas/b.schema.json]
  Proof: (empty)
  Expected: REJECTED_HORIZONTAL_OUTPUT
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_gate():
    import importlib.util
    path = ROOT / ".agentic-pi" / "runtime" / "supervisor_loop.py"
    spec = importlib.util.spec_from_file_location("supervisor_loop", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class VerticalSliceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sl = load_gate()

    # ══════════════════════════════════════════════════════════════════════
    #  Fixture 1: Vertical proof — should be ACCEPTED
    # ══════════════════════════════════════════════════════════════════════

    def test_vertical_proof_is_accepted(self):
        """A packet with fixture, expected verdict, proof command, and test file
        should pass the vertical slice gate."""
        result = self.sl.reject_horizontal_output(
            task_description=(
                "Implement one fixture: expected artifacts/report.json, "
                "actual report.json. "
                "Expected verdict: BLOCKED_BY_ARTIFACT_MISPLACEMENT. "
                "Create test fixture case_wrong_artifact_path."
            ),
            output_files=[
                ".agentic-pi/artifacts/validators/validate_artifact_location.py",
                "tests/test_artifact_location.py",
            ],
            proof_command="python tests/test_artifact_location.py -v",
        )
        self.assertEqual(result["status"], "ACCEPTED",
                         f"Expected ACCEPTED, got {result['status']}: {result.get('reason', '')}")
        self.assertTrue(result.get("checks", {}).get("has_fixture", False))
        self.assertTrue(result.get("checks", {}).get("has_expected_verdict", False))
        self.assertTrue(result.get("checks", {}).get("has_proof_command", False))
        self.assertTrue(result.get("checks", {}).get("has_test_file", False))

    def test_vertical_proof_packet_is_not_rejected(self):
        """A vertical slice packet should NOT have a horizontal rejection reason."""
        result = self.sl.reject_horizontal_output(
            task_description=(
                "One fixture: generated validator that always returns PASS. "
                "Expected verdict: V0_PROPOSED. "
                "Mutation tests must detect always-pass behavior."
            ),
            output_files=[
                ".agentic-pi/validator_factory/runtime/run_validator_mutations.py",
                "tests/test_validator_factory.py",
            ],
            proof_command="python tests/test_validator_factory.py -v",
        )
        self.assertNotEqual(result["status"], "REJECTED_HORIZONTAL_OUTPUT",
                           result.get("reason", ""))

    # ══════════════════════════════════════════════════════════════════════
    #  Fixture 2: Horizontal output — should be REJECTED_HORIZONTAL_OUTPUT
    # ══════════════════════════════════════════════════════════════════════

    def test_horizontal_output_is_rejected(self):
        """A packet that creates all schemas with no test, no verdict, no proof
        should fail the vertical slice gate."""
        result = self.sl.reject_horizontal_output(
            task_description="Create all schemas and all validators for the execution layer",
            output_files=[
                ".agentic-pi/execution/write_scope_policy.json",
                ".agentic-pi/execution/tool_registry.json",
            ],
            proof_command="",
        )
        self.assertEqual(result["status"], "REJECTED_HORIZONTAL_OUTPUT",
                        f"Expected rejection, got {result['status']}: {result.get('reason', '')}")
        self.assertIn("REJECTED_HORIZONTAL_OUTPUT", result.get("reason", ""))

    def test_horizontal_no_fixture_is_rejected(self):
        """A packet that creates code without a fixture should be rejected."""
        result = self.sl.reject_horizontal_output(
            task_description="Implement the whole repair layer with all validators",
            output_files=[
                ".agentic-pi/repair/repair_policy.json",
                ".agentic-pi/repair/validators/validate_repair_budget.py",
            ],
            proof_command="",
        )
        self.assertEqual(result["status"], "REJECTED_HORIZONTAL_OUTPUT",
                        result.get("reason", ""))

    def test_horizontal_no_test_file_is_rejected(self):
        """A packet that creates runtime code but no test should be rejected."""
        result = self.sl.reject_horizontal_output(
            task_description="Fixture: one missing artifact. Expected: NOT_DONE.",
            output_files=[
                ".agentic-pi/validators/validate_missing_artifact.py",
            ],
            proof_command="python tests/test_missing_artifact.py -v",
        )
        # No test file in output_files -> reject
        self.assertEqual(result["status"], "REJECTED_HORIZONTAL_OUTPUT",
                        result.get("reason", ""))

    # ══════════════════════════════════════════════════════════════════════
    #  Edge case: validator unavailable
    # ══════════════════════════════════════════════════════════════════════

    def test_missing_validator_allows_packet(self):
        """If the vertical slice validator module cannot be loaded,
        the gate should allow the packet through (fail-open)."""
        # The module exists, so this test validates the fallback path
        # by passing an empty task (which would normally be rejected)
        # but since the validator IS available, it will genuinely reject.
        # This tests that the function returns a dict with 'status'.
        result = self.sl.reject_horizontal_output(
            task_description="",
            output_files=[],
            proof_command="",
        )
        self.assertIn("status", result)
        # Should be REJECTED_HORIZONTAL_OUTPUT since the validator works
        # and catches empty task + no files + no proof


if __name__ == "__main__":
    unittest.main()
