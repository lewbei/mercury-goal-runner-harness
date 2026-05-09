#!/usr/bin/env python3
"""Tests for the Repair / Escalation Layer (.agentic-pi/repair/).

Tests:
- validate_repair_scope allows valid repair actions, denies forbidden
- validate_repair_budget detects exhaustion and escalation
- repair_packet.schema.json validates packet structure
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def import_validator(name):
    """Import a validator module from repair/validators/."""
    import importlib.util
    path = ROOT / ".agentic-pi" / "repair" / "validators" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def import_schema(name):
    """Import a schema file and parse it."""
    path = ROOT / ".agentic-pi" / "repair" / f"{name}.schema.json"
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


class RepairScopeTests(unittest.TestCase):
    def setUp(self):
        self.mod = import_validator("validate_repair_scope")

    def test_repairing_implementation_can_write_artifacts(self):
        result = self.mod.validate_repair_action(
            "write .agentic-runs/test_001/artifacts/fix.json",
            "REPAIRING_IMPLEMENTATION",
        )
        self.assertTrue(result["allowed"], result["reason"])

    def test_repair_cannot_write_final_status(self):
        result = self.mod.validate_repair_action(
            "write to final_status.json in .agentic-runs/test_001",
            "REPAIRING_IMPLEMENTATION",
        )
        self.assertFalse(result["allowed"], result["reason"])
        self.assertIn("forbidden", result["reason"].lower())

    def test_repair_cannot_write_certification(self):
        result = self.mod.validate_repair_action(
            "write to certification.json in .agentic-runs/test_001",
            "REPAIRING_PLAN",
        )
        self.assertFalse(result["allowed"], result["reason"])
        self.assertIn("forbidden", result["reason"].lower())

    def test_repairing_validator_can_write_verifier_artifacts(self):
        result = self.mod.validate_repair_action(
            "write .agentic-runs/test_001/verifier_artifacts/v2.json",
            "REPAIRING_VALIDATOR",
        )
        self.assertTrue(result["allowed"], result["reason"])

    def test_non_validator_repair_cannot_write_verifier_artifacts(self):
        result = self.mod.validate_repair_action(
            "write .agentic-runs/test_001/verifier_artifacts/v2.json",
            "REPAIRING_IMPLEMENTATION",
        )
        self.assertFalse(result["allowed"], result["reason"])
        self.assertIn("verifier_artifacts", result["reason"].lower())

    def test_unknown_repair_type_rejected(self):
        result = self.mod.validate_repair_action(
            "do anything",
            "REPAIRING_UNKNOWN",
        )
        self.assertFalse(result["allowed"], result["reason"])

    def test_repair_cannot_delete_frozen_evidence(self):
        result = self.mod.validate_repair_action(
            "delete frozen evidence from .agentic-runs/test_001",
            "REPAIRING_EVIDENCE",
        )
        self.assertFalse(result["allowed"], result["reason"])
        self.assertIn("forbidden", result["reason"].lower())


class RepairBudgetTests(unittest.TestCase):
    def setUp(self):
        self.mod = import_validator("validate_repair_budget")

    def test_budget_not_exhausted_below_max(self):
        result = self.mod.validate_repair_attempt("REPAIRING_PLAN", 0)
        self.assertFalse(result["budget_exhausted"], result["reason"])

    def test_budget_exhausted_at_max(self):
        """REPAIRING_PLAN max_attempts is 2; at 2 it should be exhausted."""
        result = self.mod.validate_repair_attempt("REPAIRING_PLAN", 2)
        self.assertTrue(result["budget_exhausted"], result["reason"])
        self.assertEqual(result["escalation_target"], "BLOCKED_BY_GOAL_AMBIGUITY")

    def test_implementation_budget_escalates_to_blocked(self):
        result = self.mod.validate_repair_attempt("REPAIRING_IMPLEMENTATION", 3)
        self.assertTrue(result["budget_exhausted"], result["reason"])
        self.assertEqual(result["escalation_target"], "BLOCKED")

    def test_validator_budget_escalates_to_validator_untrusted(self):
        """REPAIRING_VALIDATOR max_attempts is 3; exhaustion -> VALIDATOR_UNTRUSTED."""
        result = self.mod.validate_repair_attempt("REPAIRING_VALIDATOR", 3)
        self.assertTrue(result["budget_exhausted"], result["reason"])
        self.assertEqual(result["escalation_target"], "BLOCKED_BY_VALIDATOR_UNTRUSTED")

    def test_unknown_repair_type_exhausted_immediately(self):
        result = self.mod.validate_repair_attempt("REPAIRING_MYSTERY", 0)
        self.assertTrue(result["budget_exhausted"], result["reason"])

    def test_evidence_gap_escalation(self):
        """REPAIRING_EVIDENCE max_attempts is 2 -> exhaustion -> EVIDENCE_GAP."""
        result = self.mod.validate_repair_attempt("REPAIRING_EVIDENCE", 2)
        self.assertTrue(result["budget_exhausted"], result["reason"])
        self.assertEqual(result["escalation_target"], "BLOCKED_BY_EVIDENCE_GAP")

    def test_artifact_routing_escalation(self):
        """REPAIRING_ARTIFACT_ROUTING max_attempts is 2 -> ARTIFACT_MISPLACEMENT."""
        result = self.mod.validate_repair_attempt("REPAIRING_ARTIFACT_ROUTING", 2)
        self.assertTrue(result["budget_exhausted"], result["reason"])
        self.assertEqual(result["escalation_target"], "BLOCKED_BY_ARTIFACT_MISPLACEMENT")


class RepairPacketSchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = import_schema("repair_packet")

    def _validate(self, instance):
        import jsonschema
        try:
            jsonschema.validate(instance, self.schema)
            return None
        except jsonschema.ValidationError as e:
            return str(e)

    def test_valid_packet_passes_schema(self):
        packet = {
            "packet_id": "RP.PLAN.001",
            "run_id": "test_001",
            "repair_type": "REPAIRING_PLAN",
            "triggered_by": "validate_plan_graph",
            "max_attempts": 2,
            "attempt_count": 1,
            "allowed_actions": ["write plan_graph.json"],
            "forbidden_actions": ["write final_status.json"],
            "status": "IN_PROGRESS",
        }
        error = self._validate(packet)
        self.assertIsNone(error, error)

    def test_invalid_repair_type_fails_schema(self):
        packet = {
            "packet_id": "RP.PLAN.002",
            "run_id": "test_001",
            "repair_type": "INVALID_TYPE",
            "triggered_by": "something",
            "max_attempts": 2,
            "attempt_count": 0,
            "allowed_actions": [],
            "forbidden_actions": [],
            "status": "PENDING",
        }
        error = self._validate(packet)
        self.assertIsNotNone(error)

    def test_missing_required_field_fails_schema(self):
        packet = {
            "run_id": "test_001",
            "repair_type": "REPAIRING_PLAN",
        }
        error = self._validate(packet)
        self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
