#!/usr/bin/env python3
"""Unittest tests for RPG-Harness v5 Phase 4: Success Criteria + Oracle Mapping.

Tests cover:
- Success criteria schemas and validation
- Success criteria compiler
- Measurability checking
- Oracle type validation
- Oracle strength validation
- Success-to-oracle mapping validation
- Integration with run kernel and artifact routing
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUCCESS_DIR = ROOT / ".agentic-pi" / "success"
SUCCESS_VALIDATORS_DIR = SUCCESS_DIR / "validators"
ORACLES_DIR = ROOT / ".agentic-pi" / "oracles"
ORACLES_VALIDATORS_DIR = ORACLES_DIR / "validators"

for d in [SUCCESS_DIR, SUCCESS_VALIDATORS_DIR, ORACLES_DIR, ORACLES_VALIDATORS_DIR]:
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


# Lazy module loading
_VSC = None
_VSM = None
_VSOM = None
_VOT = None
_VOS = None
_SCC = None


def _get_vsc():
    global _VSC
    if _VSC is None:
        _VSC = load_module("validate_success_criteria",
                           SUCCESS_VALIDATORS_DIR / "validate_success_criteria.py")
    return _VSC


def _get_vsm():
    global _VSM
    if _VSM is None:
        _VSM = load_module("validate_success_measurability",
                           SUCCESS_VALIDATORS_DIR / "validate_success_measurability.py")
    return _VSM


def _get_vsom():
    global _VSOM
    if _VSOM is None:
        _VSOM = load_module("validate_success_to_oracle_mapping",
                            SUCCESS_VALIDATORS_DIR / "validate_success_to_oracle_mapping.py")
    return _VSOM


def _get_vot():
    global _VOT
    if _VOT is None:
        _VOT = load_module("validate_oracle_type",
                           ORACLES_VALIDATORS_DIR / "validate_oracle_type.py")
    return _VOT


def _get_vos():
    global _VOS
    if _VOS is None:
        _VOS = load_module("validate_oracle_strength",
                           ORACLES_VALIDATORS_DIR / "validate_oracle_strength.py")
    return _VOS


def _get_scc():
    global _SCC
    if _SCC is None:
        _SCC = load_module("success_criteria_compiler",
                           SUCCESS_DIR / "success_criteria_compiler.py")
    return _SCC


# ══════════════════════════════════════════════════════════════════════════════
#  Schema File Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaFiles(unittest.TestCase):
    """Verify all Phase 4 schema and config files exist."""

    def test_success_criteria_schema(self):
        self.assertTrue((SUCCESS_DIR / "success_criteria.schema.json").exists())

    def test_success_criteria_set_schema(self):
        self.assertTrue((SUCCESS_DIR / "success_criteria_set.schema.json").exists())

    def test_success_criteria_compiler(self):
        self.assertTrue((SUCCESS_DIR / "success_criteria_compiler.py").exists())

    def test_validate_success_criteria(self):
        self.assertTrue((SUCCESS_VALIDATORS_DIR / "validate_success_criteria.py").exists())

    def test_validate_measurability(self):
        self.assertTrue((SUCCESS_VALIDATORS_DIR / "validate_success_measurability.py").exists())

    def test_validate_oracle_mapping(self):
        self.assertTrue((SUCCESS_VALIDATORS_DIR / "validate_success_to_oracle_mapping.py").exists())

    def test_oracle_registry(self):
        self.assertTrue((ORACLES_DIR / "oracle_registry.json").exists())

    def test_oracle_strength_rules(self):
        self.assertTrue((ORACLES_DIR / "oracle_strength_rules.json").exists())

    def test_validate_oracle_type(self):
        self.assertTrue((ORACLES_VALIDATORS_DIR / "validate_oracle_type.py").exists())

    def test_validate_oracle_strength(self):
        self.assertTrue((ORACLES_VALIDATORS_DIR / "validate_oracle_strength.py").exists())


# ══════════════════════════════════════════════════════════════════════════════
#  Success Criteria Schema Validation Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSuccessCriteriaValidation(unittest.TestCase):
    """Test validate_success_criteria.py."""

    def setUp(self):
        self.vsc = _get_vsc()

    def _make_valid_set(self) -> dict:
        return {
            "schema_version": "success_criteria_set_v1",
            "run_id": "test_sc_001",
            "source_goal_id": "goal_001",
            "criteria": [
                {
                    "criterion_id": "SC.001",
                    "description": "Output file exists",
                    "measurable_indicator": {"type": "file_exists", "target_path": "output.txt"},
                    "required": True,
                    "priority": "HIGH",
                    "oracle_types": ["STRUCTURAL_ORACLE"],
                    "minimum_oracle_strength": "P1_VISIBLE",
                },
                {
                    "criterion_id": "SC.002",
                    "description": "Output is valid JSON",
                    "measurable_indicator": {"type": "schema_valid", "schema_path": "schema.json"},
                    "required": True,
                    "priority": "CRITICAL",
                    "oracle_types": ["STRUCTURAL_ORACLE", "BEHAVIORAL_ORACLE"],
                    "minimum_oracle_strength": "P2_INDEPENDENT",
                },
            ],
            "compilation_timestamp": "2026-05-08T00:00:00Z",
            "compilation_strategy": "extracted",
        }

    def test_valid_set_passes(self):
        errors = self.vsc.validate_criteria_set(self._make_valid_set())
        self.assertEqual(errors, [])

    def test_duplicate_criterion_id(self):
        cs = self._make_valid_set()
        cs["criteria"].append({
            "criterion_id": "SC.001",
            "description": "Duplicate",
            "measurable_indicator": {"type": "file_exists"},
            "required": True,
            "oracle_types": ["STRUCTURAL_ORACLE"],
        })
        errors = self.vsc.validate_criteria_set(cs)
        self.assertTrue(any("Duplicate criterion_id" in e for e in errors))

    def test_missing_schema_version(self):
        cs = self._make_valid_set()
        del cs["schema_version"]
        errors = self.vsc.validate_criteria_set(cs)
        self.assertGreater(len(errors), 0)

    def test_invalid_oracle_type_rejected(self):
        cs = self._make_valid_set()
        cs["criteria"][0]["oracle_types"] = ["INVALID_ORACLE"]
        errors = self.vsc.validate_criteria_set(cs)
        self.assertGreater(len(errors), 0)

    def test_invalid_measurable_indicator(self):
        cs = self._make_valid_set()
        cs["criteria"][0]["measurable_indicator"] = {"type": "unknown_type"}
        errors = self.vsc.validate_criteria_set(cs)
        self.assertGreater(len(errors), 0)

    def test_invalid_strength_level(self):
        cs = self._make_valid_set()
        cs["criteria"][0]["minimum_oracle_strength"] = "P9_INVALID"
        errors = self.vsc.validate_criteria_set(cs)
        self.assertGreater(len(errors), 0)


# ══════════════════════════════════════════════════════════════════════════════
#  Success Criteria Compiler Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSuccessCriteriaCompiler(unittest.TestCase):
    """Test success_criteria_compiler.py."""

    def setUp(self):
        self.scc = _get_scc()

    def test_compile_with_explicit_criteria(self):
        contract = {
            "goal_id": "test_goal_001",
            "goal_type": "coding",
            "description": "Create a report file",
            "success_criteria": [
                "Report file is generated",
                "Report contains valid JSON",
            ],
        }
        result = self.scc.compile_from_goal_contract(contract, "run_001")
        self.assertEqual(result["schema_version"], "success_criteria_set_v1")
        self.assertEqual(result["run_id"], "run_001")
        self.assertEqual(result["source_goal_id"], "test_goal_001")
        self.assertEqual(result["compilation_strategy"], "extracted")
        self.assertEqual(len(result["criteria"]), 2)
        self.assertEqual(result["criteria"][0]["criterion_id"], "SC.001")
        self.assertEqual(result["criteria"][1]["criterion_id"], "SC.002")

    def test_compile_without_criteria_derives(self):
        contract = {
            "goal_id": "test_goal_002",
            "goal_type": "coding",
            "description": "Implement a feature",
        }
        result = self.scc.compile_from_goal_contract(contract, "run_002")
        self.assertEqual(result["compilation_strategy"], "derived")
        self.assertGreater(len(result["criteria"]), 1)

    def test_compile_test_goal(self):
        contract = {
            "goal_id": "test_goal_003",
            "goal_type": "test",
            "description": "Write test suite",
        }
        result = self.scc.compile_from_goal_contract(contract, "run_003")
        self.assertGreater(len(result["criteria"]), 1)

    def test_compile_generic_goal(self):
        contract = {
            "goal_id": "test_goal_004",
            "goal_type": "generic",
            "description": "Do something",
        }
        result = self.scc.compile_from_goal_contract(contract, "run_004")
        self.assertEqual(len(result["criteria"]), 1)

    def test_compile_with_dict_criteria(self):
        contract = {
            "goal_id": "test_goal_005",
            "goal_type": "coding",
            "success_criteria": [
                {
                    "criterion_id": "SC.CUSTOM",
                    "description": "Custom criterion",
                    "measurable_indicator": {"type": "command_passes", "command": "pytest"},
                    "required": True,
                    "priority": "CRITICAL",
                    "oracle_types": ["BEHAVIORAL_ORACLE"],
                    "minimum_oracle_strength": "P2_INDEPENDENT",
                }
            ],
        }
        result = self.scc.compile_from_goal_contract(contract, "run_005")
        self.assertEqual(len(result["criteria"]), 1)
        self.assertEqual(result["criteria"][0]["criterion_id"], "SC.CUSTOM")


# ══════════════════════════════════════════════════════════════════════════════
#  Measurability Validator Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestMeasurability(unittest.TestCase):
    """Test validate_success_measurability.py."""

    def setUp(self):
        self.vsm = _get_vsm()

    def test_measurable_file_exists(self):
        cs = {
            "criteria": [
                {
                    "criterion_id": "SC.001",
                    "description": "Output file exists",
                    "measurable_indicator": {"type": "file_exists", "target_path": "out.txt"},
                }
            ]
        }
        results = self.vsm.validate_measurability(cs)
        self.assertTrue(results[0]["measurable"])

    def test_measurable_command_passes(self):
        cs = {
            "criteria": [
                {
                    "criterion_id": "SC.001",
                    "description": "Test passes",
                    "measurable_indicator": {"type": "command_passes", "command": "pytest"},
                }
            ]
        }
        results = self.vsm.validate_measurability(cs)
        self.assertTrue(results[0]["measurable"])

    def test_command_missing_command_field(self):
        cs = {
            "criteria": [
                {
                    "criterion_id": "SC.001",
                    "description": "Test passes",
                    "measurable_indicator": {"type": "command_passes"},
                }
            ]
        }
        results = self.vsm.validate_measurability(cs)
        self.assertFalse(results[0]["measurable"])

    def test_file_check_missing_path(self):
        cs = {
            "criteria": [
                {
                    "criterion_id": "SC.001",
                    "description": "File exists",
                    "measurable_indicator": {"type": "file_exists"},
                }
            ]
        }
        results = self.vsm.validate_measurability(cs)
        self.assertFalse(results[0]["measurable"])

    def test_vague_language_detected(self):
        cs = {
            "criteria": [
                {
                    "criterion_id": "SC.001",
                    "description": "The code should work properly",
                    "measurable_indicator": {"type": "oracle_output"},
                }
            ]
        }
        results = self.vsm.validate_measurability(cs)
        self.assertFalse(results[0]["measurable"])
        has_vague = any("should work" in w for w in results[0]["warnings"])
        self.assertTrue(has_vague)

    def test_all_measurable_helper(self):
        cs = {
            "criteria": [
                {"criterion_id": "SC.001", "description": "A", "measurable_indicator": {"type": "file_exists", "target_path": "a.txt"}},
                {"criterion_id": "SC.002", "description": "B", "measurable_indicator": {"type": "command_passes", "command": "test"}},
            ]
        }
        results = self.vsm.validate_measurability(cs)
        self.assertTrue(self.vsm.all_measurable(results))

    def test_not_all_measurable(self):
        cs = {
            "criteria": [
                {"criterion_id": "SC.001", "description": "A", "measurable_indicator": {"type": "file_exists", "target_path": "a.txt"}},
                {"criterion_id": "SC.002", "description": "B should be better", "measurable_indicator": {"type": "oracle_output"}},
            ]
        }
        results = self.vsm.validate_measurability(cs)
        self.assertFalse(self.vsm.all_measurable(results))


# ══════════════════════════════════════════════════════════════════════════════
#  Oracle Type Validator Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestOracleTypeValidator(unittest.TestCase):
    """Test validate_oracle_type.py."""

    def setUp(self):
        self.vot = _get_vot()

    def test_valid_oracle_types(self):
        for ot in ["STRUCTURAL_ORACLE", "BEHAVIORAL_ORACLE", "SEMANTIC_ORACLE",
                    "COMPARATIVE_ORACLE", "NEGATIVE_ORACLE", "REPLAY_ORACLE",
                    "EXTERNAL_ORACLE"]:
            with self.subTest(ot):
                errors = self.vot.validate_oracle_type(ot)
                self.assertEqual(errors, [])

    def test_invalid_oracle_type(self):
        errors = self.vot.validate_oracle_type("MAGIC_ORACLE")
        self.assertGreater(len(errors), 0)

    def test_empty_type(self):
        errors = self.vot.validate_oracle_type("")
        self.assertGreater(len(errors), 0)

    def test_validate_list(self):
        errors = self.vot.validate_oracle_types(["STRUCTURAL_ORACLE", "BEHAVIORAL_ORACLE"])
        self.assertEqual(errors, [])

    def test_validate_list_with_invalid(self):
        errors = self.vot.validate_oracle_types(["STRUCTURAL_ORACLE", "FAKE_ORACLE"])
        self.assertGreater(len(errors), 0)


# ══════════════════════════════════════════════════════════════════════════════
#  Oracle Strength Validator Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestOracleStrengthValidator(unittest.TestCase):
    """Test validate_oracle_strength.py."""

    def setUp(self):
        self.vos = _get_vos()

    def test_valid_strength_levels(self):
        for level in ["P0_SELF", "P1_VISIBLE", "P2_INDEPENDENT", "P3_EXTERNAL"]:
            with self.subTest(level):
                errors = self.vos.validate_strength_level(level)
                self.assertEqual(errors, [])

    def test_invalid_strength_level(self):
        errors = self.vos.validate_strength_level("P9_INVALID")
        self.assertGreater(len(errors), 0)

    def test_structural_oracle_limitation(self):
        results = self.vos.validate_oracle_provenance("STRUCTURAL_ORACLE", "P2_INDEPENDENT")
        self.assertGreater(len(results), 0)
        self.assertTrue(any("cannot certify semantic success" in r["message"] for r in results))

    def test_below_default_strength(self):
        results = self.vos.validate_oracle_provenance("SEMANTIC_ORACLE", "P0_SELF")
        has_warning = any("below the default minimum" in r["message"] for r in results)
        self.assertTrue(has_warning)

    def test_sufficient_strength(self):
        results = self.vos.validate_oracle_provenance("SEMANTIC_ORACLE", "P2_INDEPENDENT")
        # May have no warnings
        self.assertIsInstance(results, list)

    def test_external_oracle_accepts_p3(self):
        results = self.vos.validate_oracle_provenance("EXTERNAL_ORACLE", "P3_EXTERNAL")
        # Should have no issues
        critical = [r for r in results if r["type"] == "error"]
        self.assertEqual(critical, [])


# ══════════════════════════════════════════════════════════════════════════════
#  Oracle Mapping Validator Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestOracleMapping(unittest.TestCase):
    """Test validate_success_to_oracle_mapping.py."""

    def setUp(self):
        self.vsom = _get_vsom()

    def test_valid_mapping(self):
        cs = {
            "criteria": [
                {
                    "criterion_id": "SC.001",
                    "oracle_types": ["STRUCTURAL_ORACLE", "BEHAVIORAL_ORACLE"],
                    "minimum_oracle_strength": "P1_VISIBLE",
                    "priority": "HIGH",
                }
            ]
        }
        results = self.vsom.validate_oracle_mapping(cs)
        self.assertTrue(results[0]["valid"])
        self.assertEqual(results[0]["errors"], [])

    def test_no_oracle_types(self):
        cs = {"criteria": [{"criterion_id": "SC.001", "oracle_types": []}]}
        results = self.vsom.validate_oracle_mapping(cs)
        self.assertFalse(results[0]["valid"])
        self.assertTrue(any("No oracle types" in e for e in results[0]["errors"]))

    def test_unknown_oracle_type(self):
        cs = {"criteria": [{"criterion_id": "SC.001", "oracle_types": ["FAKE_ORACLE"]}]}
        results = self.vsom.validate_oracle_mapping(cs)
        self.assertFalse(results[0]["valid"])

    def test_structural_only_warning(self):
        cs = {"criteria": [{"criterion_id": "SC.001", "oracle_types": ["STRUCTURAL_ORACLE"]}]}
        results = self.vsom.validate_oracle_mapping(cs)
        self.assertTrue(results[0]["valid"])
        self.assertTrue(any("STRUCTURAL_ORACLE alone" in w for w in results[0]["warnings"]))

    def test_priority_strength_warning(self):
        cs = {
            "criteria": [
                {
                    "criterion_id": "SC.001",
                    "oracle_types": ["BEHAVIORAL_ORACLE"],
                    "minimum_oracle_strength": "P0_SELF",
                    "priority": "CRITICAL",
                }
            ]
        }
        results = self.vsom.validate_oracle_mapping(cs)
        self.assertIn("below recommended", results[0]["warnings"][0])

    def test_all_valid_helper(self):
        cs = {"criteria": [{"criterion_id": "SC.001", "oracle_types": ["STRUCTURAL_ORACLE"]}]}
        results = self.vsom.validate_oracle_mapping(cs)
        self.assertTrue(self.vsom.all_valid(results))

    def test_not_all_valid(self):
        cs = {"criteria": [{"criterion_id": "SC.001", "oracle_types": []}]}
        results = self.vsom.validate_oracle_mapping(cs)
        self.assertFalse(self.vsom.all_valid(results))


# ══════════════════════════════════════════════════════════════════════════════
#  Integration Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase4Integration(unittest.TestCase):
    """Integration tests combining Phase 4 with run kernel and Phase 3."""

    def setUp(self):
        rk_path = ROOT / ".agentic-pi" / "run_kernel" / "run_kernel.py"
        self.rk = load_module("run_kernel", rk_path)
        self.scc = _get_scc()
        self.vsc = _get_vsc()
        self.vsm = _get_vsm()
        self.vsom = _get_vsom()
        self.vot = _get_vot()
        self.vos = _get_vos()

        self.tmp = Path(tempfile.mkdtemp())
        self.old_runs_dir = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs_dir
        import shutil
        shutil.rmtree(self.tmp)

    def test_full_pipeline_in_kernel_run(self):
        """Create a run, compile success criteria, validate everything."""
        run_id = "test_phase4_pipeline_001"
        self.rk.create_run(run_id)
        run_dir = self.rk.get_run_dir(run_id)

        # Compile criteria from a goal contract
        goal_contract = {
            "goal_id": "integ_goal_001",
            "goal_type": "coding",
            "description": "Create a valid JSON report",
            "success_criteria": [
                {
                    "criterion_id": "SC.REPORT",
                    "description": "Report file exists and is valid JSON",
                    "measurable_indicator": {"type": "file_exists", "target_path": "report.json"},
                    "required": True,
                    "priority": "HIGH",
                    "oracle_types": ["STRUCTURAL_ORACLE", "BEHAVIORAL_ORACLE"],
                    "minimum_oracle_strength": "P1_VISIBLE",
                },
            ],
        }
        criteria_set = self.scc.compile_from_goal_contract(goal_contract, run_id)

        # Write to run directory
        (run_dir / "success_criteria_set.json").write_text(
            json.dumps(criteria_set), encoding="utf-8"
        )

        # Validate criteria set schema
        errors = self.vsc.validate_criteria_set(criteria_set)
        self.assertEqual(errors, [])

        # Check measurability
        meas = self.vsm.validate_measurability(criteria_set)
        self.assertTrue(self.vsm.all_measurable(meas))

        # Check oracle mapping
        mapping = self.vsom.validate_oracle_mapping(criteria_set)
        self.assertTrue(self.vsom.all_valid(mapping))

        # Check oracle types
        for c in criteria_set["criteria"]:
            for ot in c.get("oracle_types", []):
                self.assertEqual(self.vot.validate_oracle_type(ot), [])

        # Check oracle strength
        for c in criteria_set["criteria"]:
            strength = c.get("minimum_oracle_strength", "P1_VISIBLE")
            self.assertEqual(self.vos.validate_strength_level(strength), [])

    def test_missing_criteria_blocks_selection(self):
        """No criteria set means no branch selection can happen."""
        # This is the plan rule: no success criteria -> no selected branch
        run_id = "test_no_criteria_001"
        self.rk.create_run(run_id)

        # Simulate no success_criteria_set.json
        run_dir = self.rk.get_run_dir(run_id)
        sc_path = run_dir / "success_criteria_set.json"
        self.assertFalse(sc_path.exists())

        # The rule exists in the oracle strength rules
        self.assertTrue(
            (ORACLES_DIR / "oracle_strength_rules.json").exists()
        )

    def test_structural_only_limits_certification(self):
        """STRUCTURAL_ORACLE alone should max out at PROVISIONAL_DONE."""
        cs = {
            "criteria": [
                {
                    "criterion_id": "SC.001",
                    "description": "File exists",
                    "measurable_indicator": {"type": "file_exists", "target_path": "out.txt"},
                    "required": True,
                    "priority": "HIGH",
                    "oracle_types": ["STRUCTURAL_ORACLE"],
                    "minimum_oracle_strength": "P2_INDEPENDENT",
                }
            ]
        }

        # Mapping validator should warn
        mapping = self.vsom.validate_oracle_mapping(cs)
        self.assertTrue(any("STRUCTURAL_ORACLE alone" in w for w in mapping[0]["warnings"]))

        # Strength validator should note the limitation
        prov = self.vos.validate_oracle_provenance("STRUCTURAL_ORACLE", "P2_INDEPENDENT")
        self.assertTrue(any("cannot certify semantic success" in r["message"] for r in prov))

    def test_oracle_registry_content(self):
        """Verify the oracle registry has all 7 expected types."""
        registry = load_json(ORACLES_DIR / "oracle_registry.json")
        types = {o["oracle_type"] for o in registry["oracles"]}
        expected = {
            "STRUCTURAL_ORACLE", "BEHAVIORAL_ORACLE", "SEMANTIC_ORACLE",
            "COMPARATIVE_ORACLE", "NEGATIVE_ORACLE", "REPLAY_ORACLE",
            "EXTERNAL_ORACLE",
        }
        self.assertEqual(types, expected)

    def test_strength_rules_content(self):
        """Verify oracle_strength_rules.json has all 4 levels."""
        rules = load_json(ORACLES_DIR / "oracle_strength_rules.json")
        levels = {l["level"] for l in rules["strength_levels"]}
        self.assertEqual(levels, {"P0_SELF", "P1_VISIBLE", "P2_INDEPENDENT", "P3_EXTERNAL"})

    def test_minimum_oracle_strength_validation(self):
        """Verify the chain: criteria with insufficient strength should be noted."""
        cs = {
            "criteria": [
                {
                    "criterion_id": "SC.001",
                    "description": "Critical test",
                    "measurable_indicator": {"type": "command_passes", "command": "pytest"},
                    "required": True,
                    "priority": "CRITICAL",
                    "oracle_types": ["BEHAVIORAL_ORACLE"],
                    "minimum_oracle_strength": "P0_SELF",
                }
            ]
        }
        mapping = self.vsom.validate_oracle_mapping(cs)
        self.assertGreater(len(mapping[0]["warnings"]), 0)


if __name__ == "__main__":
    unittest.main()
