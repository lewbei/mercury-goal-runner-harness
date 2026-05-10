#!/usr/bin/env python3
"""Vertical slice test for VS.004: Always-pass generated validator rejected.

Proves the full validator certification pipeline rejects a validator
that always returns PASS:
1. Validator spec created at V0_PROPOSED
2. Meta-check detects the always-return-True pattern
3. Fixture tests run (must also test negative fixtures)
4. Mutation tests detect the validator can't distinguish PASS from FAIL
5. Full certification pipeline returns FAILED
6. Validator stays at V0_PROPOSED — never promoted to V1 or V2
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VF_DIR = ROOT / ".agentic-pi" / "validator_factory"
RUNTIME_DIR = VF_DIR / "runtime"

for d in [str(VF_DIR), str(RUNTIME_DIR)]:
    if d not in sys.path:
        sys.path.insert(0, d)


def load_module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestVerticalSlice004_AlwaysPassValidator(unittest.TestCase):
    """VS.004: Always-pass validator stays V0_PROPOSED."""

    def setUp(self):
        self.mc = load_module("run_validator_meta_check",
                              RUNTIME_DIR / "run_validator_meta_check.py")
        self.fr = load_module("run_validator_fixtures",
                              RUNTIME_DIR / "run_validator_fixtures.py")
        self.mr = load_module("run_validator_mutations",
                              RUNTIME_DIR / "run_validator_mutations.py")
        self.cert = load_module("certify_generated_validator",
                                RUNTIME_DIR / "certify_generated_validator.py")

    # ── Test 1: Meta-check catches always-return-True ─────────────────────

    def test_meta_check_catches_always_pass(self):
        """Meta-check detects a validator with no return False path."""
        spec = {
            "schema_version": "validator_spec_v1",
            "validator_id": "V.ALWAYSPASS",
            "authority_level": "V0_PROPOSED",
            "success_criteria": ["SC.001"],
            "check_type": "file_exists",
            "runtime_command": "python always_pass.py",
        }

        with tempfile.TemporaryDirectory() as tmp:
            code_path = Path(tmp) / "always_pass.py"
            code_path.write_text(
                "def check(path):\n"
                "    return True  # never returns False\n"
            )
            results = self.mc.run_meta_check(spec, code_path)

        always_pass_check = [r for r in results if r["check"] == "code_always_pass"]
        self.assertGreater(len(always_pass_check), 0,
                          "Meta-check must detect always-pass code")
        self.assertFalse(always_pass_check[0]["passed"],
                        "always-pass check must fail")

    # ── Test 2: Mutation tests detect always-pass ─────────────────────────

    def test_mutation_detects_always_pass(self):
        """Mutation runner detects that always-return-PASS is not trustworthy."""
        spec = {"validator_id": "V.ALWAYSPASS.MUT"}
        suite = {
            "fixtures": [
                {"fixture_id": "F.POS", "type": "positive", "input": {"path": "/tmp/real"}, "expected_verdict": "PASS"},
                {"fixture_id": "F.NEG", "type": "negative", "input": {"path": "/nonexistent"}, "expected_verdict": "FAIL"},
            ],
        }

        # Run all mutation types
        result = self.mr.run_mutations(spec, suite)

        # At least one mutation must be detected (should be the negative fixture)
        detected = [r for r in result["mutation_results"] if r["detected"]]
        self.assertGreater(len(detected), 0,
                          "At least one mutation must be detected")

        # The negative fixture with return_always_pass should be detected
        neg_rap = [
            r for r in result["mutation_results"]
            if r["fixture_id"] == "F.NEG" and r["mutation_type"] == "return_always_pass"
        ]
        self.assertGreater(len(neg_rap), 0)
        self.assertTrue(neg_rap[0]["detected"],
                       "return_always_pass mutation on negative fixture must be detected")

    # ── Test 3: Full certification pipeline rejects always-pass ───────────

    def test_full_certification_rejects_always_pass(self):
        """Full certification pipeline must NOT certify an always-pass validator."""
        spec = {
            "schema_version": "validator_spec_v1",
            "validator_id": "V.ALWAYSPASS.CERT",
            "authority_level": "V0_PROPOSED",
            "success_criteria": ["SC.001"],
            "check_type": "file_exists",
            "runtime_command": "python always_pass.py",
        }
        suite = {
            "schema_version": "fixture_suite_v1",
            "suite_id": "S.ALWAYSPASS.001",
            "validator_id": "V.ALWAYSPASS.CERT",
            "fixtures": [
                {"fixture_id": "F.POS", "type": "positive", "input": {"path": "/tmp/real"}, "expected_verdict": "PASS"},
                {"fixture_id": "F.NEG", "type": "negative", "input": {"path": "/nonexistent"}, "expected_verdict": "FAIL"},
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            code_path = Path(tmp) / "always_pass.py"
            code_path.write_text(
                "def check(path):\n"
                "    return True\n"
            )
            result = self.cert.certify_validator(spec, fixture_suite=suite, validator_code_path=code_path)

        # Must NOT be certified
        self.assertFalse(self.cert.is_certified(result),
                        "Always-pass validator must NOT be certified")
        self.assertEqual(result["new_level"], "V0_PROPOSED",
                        "Validator must stay at V0_PROPOSED")

        # Meta-check must have failed
        self.assertFalse(result["meta_check"]["passed"],
                        "Meta-check must fail for always-pass validator")

        # Failure reason should mention always-pass
        always_pass_failure = any(
            "always_pass" in str(c).lower() or "return True" in str(c)
            for c in result["meta_check"]["details"]
        )
        self.assertTrue(always_pass_failure,
                       "Failure must reference always-pass detection")

    # ── Test 4: Honest validator (has both True and False paths) IS certified ──

    def test_honest_validator_is_certified(self):
        """A validator with proper True/False logic IS certified to V1."""
        spec = {
            "schema_version": "validator_spec_v1",
            "validator_id": "V.HONEST",
            "authority_level": "V0_PROPOSED",
            "success_criteria": ["SC.001"],
            "check_type": "structural",
            "runtime_command": "python honest.py",
        }
        suite = {
            "schema_version": "fixture_suite_v1",
            "suite_id": "S.HONEST.001",
            "validator_id": "V.HONEST",
            "fixtures": [
                {"fixture_id": "F.POS", "type": "positive", "input": {"value": "exists"}, "expected_verdict": "PASS"},
                {"fixture_id": "F.NEG", "type": "negative", "input": {"value": "missing"}, "expected_verdict": "FAIL"},
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            code_path = Path(tmp) / "honest.py"
            code_path.write_text(
                "import os\n"
                "def check(path):\n"
                "    return os.path.exists(path)\n"
            )
            result = self.cert.certify_validator(spec, fixture_suite=suite, validator_code_path=code_path)

        # Must be certified
        self.assertTrue(self.cert.is_certified(result),
                       "Honest validator must be certified")
        self.assertIn(result["new_level"], ["V1_LOCAL_TESTED", "V2_INDEPENDENT_TESTED"],
                     "Honest validator must reach V1 or V2")


if __name__ == "__main__":
    unittest.main()
