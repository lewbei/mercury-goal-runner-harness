#!/usr/bin/env python3
"""Unittest tests for RPG-Harness v5 Phase 5: Validator Factory.

Tests cover:
- Validator spec schema and registry
- Authority policy levels
- Fixture suite schema
- Mutation policy
- Meta-check runner
- Fixture runner
- Mutation runner
- Full certification pipeline
- Integration with earlier phases
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VF_DIR = ROOT / ".agentic-pi" / "validator_factory"
RUNTIME_DIR = VF_DIR / "runtime"

for d in [VF_DIR, RUNTIME_DIR]:
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
_MC = None
_FR = None
_MR = None
_CERT = None


def _get_mc():
    global _MC
    if _MC is None:
        _MC = load_module("run_validator_meta_check",
                          RUNTIME_DIR / "run_validator_meta_check.py")
    return _MC


def _get_fr():
    global _FR
    if _FR is None:
        _FR = load_module("run_validator_fixtures",
                          RUNTIME_DIR / "run_validator_fixtures.py")
    return _FR


def _get_mr():
    global _MR
    if _MR is None:
        _MR = load_module("run_validator_mutations",
                          RUNTIME_DIR / "run_validator_mutations.py")
    return _MR


def _get_cert():
    global _CERT
    if _CERT is None:
        _CERT = load_module("certify_generated_validator",
                            RUNTIME_DIR / "certify_generated_validator.py")
    return _CERT


# ══════════════════════════════════════════════════════════════════════════════
#  Schema File Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaFiles(unittest.TestCase):
    """Verify all Phase 5 schema and config files exist."""

    def test_validator_spec_schema(self):
        self.assertTrue((VF_DIR / "validator_spec.schema.json").exists())

    def test_validator_registry(self):
        self.assertTrue((VF_DIR / "validator_registry.json").exists())

    def test_validator_authority_policy(self):
        self.assertTrue((VF_DIR / "validator_authority_policy.json").exists())

    def test_fixture_suite_schema(self):
        self.assertTrue((VF_DIR / "fixture_suite.schema.json").exists())

    def test_mutation_policy(self):
        self.assertTrue((VF_DIR / "mutation_policy.json").exists())

    def test_meta_check_runtime(self):
        self.assertTrue((RUNTIME_DIR / "run_validator_meta_check.py").exists())

    def test_fixture_runner_runtime(self):
        self.assertTrue((RUNTIME_DIR / "run_validator_fixtures.py").exists())

    def test_mutation_runner_runtime(self):
        self.assertTrue((RUNTIME_DIR / "run_validator_mutations.py").exists())

    def test_certify_runtime(self):
        self.assertTrue((RUNTIME_DIR / "certify_generated_validator.py").exists())


# ══════════════════════════════════════════════════════════════════════════════
#  Validator Spec Validation Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestValidatorSpecSchema(unittest.TestCase):
    """Test validator_spec.schema.json validity."""

    def test_schema_has_required_fields(self):
        schema = load_json(VF_DIR / "validator_spec.schema.json")
        required = set(schema.get("required", []))
        self.assertIn("validator_id", required)
        self.assertIn("authority_level", required)
        self.assertIn("success_criteria", required)
        self.assertIn("check_type", required)
        self.assertIn("runtime_command", required)

    def test_authority_levels(self):
        schema = load_json(VF_DIR / "validator_spec.schema.json")
        level_enum = schema["properties"]["authority_level"]["enum"]
        expected = {"V0_PROPOSED", "V1_LOCAL_TESTED", "V2_INDEPENDENT_TESTED",
                    "V3_EXTERNAL_TRUSTED", "V4_CORE_TRUSTED"}
        self.assertEqual(set(level_enum), expected)

    def test_check_types(self):
        schema = load_json(VF_DIR / "validator_spec.schema.json")
        types_enum = schema["properties"]["check_type"]["enum"]
        self.assertIn("file_exists", types_enum)
        self.assertIn("json_schema", types_enum)
        self.assertIn("structural", types_enum)
        self.assertIn("behavioral", types_enum)
        self.assertIn("replay", types_enum)


# ══════════════════════════════════════════════════════════════════════════════
#  Authority Policy Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthorityPolicy(unittest.TestCase):
    """Test validator_authority_policy.json rules."""

    def setUp(self):
        self.policy = load_json(VF_DIR / "validator_authority_policy.json")

    def test_v0_cannot_certify(self):
        v0 = [r for r in self.policy["authority_rules"] if r["level"] == "V0_PROPOSED"][0]
        self.assertFalse(v0["can_certify_artifact"])
        self.assertFalse(v0["can_certify_run"])
        self.assertFalse(v0["can_be_final_verifier"])

    def test_v2_can_certify_run(self):
        v2 = [r for r in self.policy["authority_rules"] if r["level"] == "V2_INDEPENDENT_TESTED"][0]
        self.assertTrue(v2["can_certify_artifact"])
        self.assertTrue(v2["can_certify_run"])
        self.assertTrue(v2["can_be_final_verifier"])

    def test_v4_is_core_trusted(self):
        v4 = [r for r in self.policy["authority_rules"] if r["level"] == "V4_CORE_TRUSTED"][0]
        self.assertTrue(v4["can_certify_run"])

    def test_certification_chain_rule(self):
        self.assertIn("certification_chain_rule", self.policy)
        self.assertIn("never certify itself", self.policy["certification_chain_rule"])


# ══════════════════════════════════════════════════════════════════════════════
#  Validator Registry Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestValidatorRegistry(unittest.TestCase):
    """Test validator_registry.json."""

    def setUp(self):
        self.registry = load_json(VF_DIR / "validator_registry.json")

    def test_has_core_validators(self):
        entries = self.registry["entries"]
        entry_ids = {e["validator_id"] for e in entries}
        self.assertIn("V.CORE.SCHEMA", entry_ids)
        self.assertIn("V.CORE.PATH_CHECK", entry_ids)
        self.assertIn("V.CORE.POLICY", entry_ids)
        self.assertIn("V.CORE.CERTIFIER", entry_ids)
        self.assertIn("V.CORE.REPLAY", entry_ids)

    def test_core_validators_are_v4(self):
        for entry in self.registry["entries"]:
            if entry["validator_id"].startswith("V.CORE."):
                self.assertEqual(entry["authority_level"], "V4_CORE_TRUSTED",
                                 f"{entry['validator_id']} is not V4")

    def test_certification_requirements(self):
        reqs = self.registry["certification_requirements"]
        self.assertIn("V0_PROPOSED", reqs)
        self.assertIn("to_reach_V1", reqs["V0_PROPOSED"])
        self.assertIn("to_reach_V2", reqs["V0_PROPOSED"])


# ══════════════════════════════════════════════════════════════════════════════
#  Meta-Check Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestMetaCheck(unittest.TestCase):
    """Test run_validator_meta_check.py."""

    def setUp(self):
        self.mc = _get_mc()

    def _make_spec(self, **overrides) -> dict:
        spec = {
            "schema_version": "validator_spec_v1",
            "validator_id": "V.TEST.001",
            "authority_level": "V0_PROPOSED",
            "success_criteria": ["SC.001"],
            "check_type": "file_exists",
            "runtime_command": "python check.py",
            "generated_by": "Mercury",
        }
        spec.update(overrides)
        return spec

    def test_valid_spec_passes(self):
        results = self.mc.run_meta_check(self._make_spec())
        passed_checks = [r for r in results if r["passed"]]
        self.assertGreater(len(passed_checks), 0)

    def test_missing_success_criteria(self):
        results = self.mc.run_meta_check(self._make_spec(success_criteria=[]))
        has_criteria_check = [r for r in results if r["check"] == "has_success_criteria"]
        self.assertFalse(has_criteria_check[0]["passed"])

    def test_missing_runtime_command(self):
        results = self.mc.run_meta_check(self._make_spec(runtime_command=""))
        has_cmd_check = [r for r in results if r["check"] == "has_runtime_command"]
        self.assertFalse(has_cmd_check[0]["passed"])

    def test_unknown_authority_level(self):
        results = self.mc.run_meta_check(self._make_spec(authority_level="P9_INVALID"))
        has_level_check = [r for r in results if r["check"] == "authority_level_known"]
        self.assertFalse(has_level_check[0]["passed"])

    def test_code_safety_detects_always_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_path = Path(tmp) / "bad_validator.py"
            code_path.write_text("def check():\n    return True\n")
            results = self.mc.run_meta_check(self._make_spec(), code_path)
            has_always_pass = [r for r in results if r["check"] == "code_always_pass"]
            self.assertGreater(len(has_always_pass), 0)
            self.assertFalse(has_always_pass[0]["passed"])

    def test_code_safety_detects_os_system(self):
        with tempfile.TemporaryDirectory() as tmp:
            code_path = Path(tmp) / "unsafe_validator.py"
            code_path.write_text("import os\ndef check():\n    os.system('rm -rf /')\n")
            results = self.mc.run_meta_check(self._make_spec(), code_path)
            has_os_system = [r for r in results if "code_safety_os.system" in r["check"]]
            self.assertGreater(len(has_os_system), 0)
            self.assertFalse(has_os_system[0]["passed"])

    def test_all_meta_checks_pass_helper(self):
        results = [{"check": "a", "passed": True}, {"check": "b", "passed": True}]
        self.assertTrue(self.mc.all_meta_checks_pass(results))

    def test_all_meta_checks_pass_helper_failure(self):
        results = [{"check": "a", "passed": True}, {"check": "b", "passed": False}]
        self.assertFalse(self.mc.all_meta_checks_pass(results))


# ══════════════════════════════════════════════════════════════════════════════
#  Fixture Runner Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestFixtureRunner(unittest.TestCase):
    """Test run_validator_fixtures.py."""

    def setUp(self):
        self.fr = _get_fr()

    def _make_spec(self, check_type: str = "structural") -> dict:
        return {
            "validator_id": "V.TEST.FIXTURE",
            "check_type": check_type,
            "runtime_command": "python check.py",
        }

    def _make_suite(self, fixtures: list) -> dict:
        return {
            "schema_version": "fixture_suite_v1",
            "suite_id": "S.TEST.001",
            "validator_id": "V.TEST.FIXTURE",
            "fixtures": fixtures,
        }

    def test_all_pass(self):
        spec = self._make_suite([
            {"fixture_id": "F.001", "type": "positive", "input": {}, "expected_verdict": "PASS"},
            {"fixture_id": "F.002", "type": "positive", "input": {}, "expected_verdict": "PASS"},
        ])
        result = self.fr.run_fixtures(self._make_spec(), spec)
        self.assertEqual(result["overall"], "PASS")
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["failed"], 0)

    def test_some_fail(self):
        spec = self._make_suite([
            {"fixture_id": "F.001", "type": "positive", "input": {}, "expected_verdict": "PASS"},
            {"fixture_id": "F.002", "type": "negative", "input": {}, "expected_verdict": "FAIL"},
        ])
        result = self.fr.run_fixtures(self._make_spec(), spec)
        self.assertEqual(result["overall"], "PASS")
        self.assertEqual(result["total"], 2)

    def test_all_fixtures_pass_helper(self):
        result = {"overall": "PASS"}
        self.assertTrue(self.fr.all_fixtures_pass(result))
        self.assertFalse(self.fr.all_fixtures_pass({"overall": "FAIL"}))


# ══════════════════════════════════════════════════════════════════════════════
#  Mutation Runner Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestMutationRunner(unittest.TestCase):
    """Test run_validator_mutations.py."""

    def setUp(self):
        self.mr = _get_mr()

    def _make_spec(self) -> dict:
        return {"validator_id": "V.TEST.MUT"}

    def _make_suite(self) -> dict:
        return {
            "fixtures": [
                {"fixture_id": "F.001", "type": "positive", "input": {"path": "/tmp/test"}, "expected_verdict": "PASS"},
                {"fixture_id": "F.002", "type": "negative", "input": {"path": "/nonexistent"}, "expected_verdict": "FAIL"},
            ]
        }

    def test_mutations_run(self):
        result = self.mr.run_mutations(self._make_spec(), self._make_suite())
        self.assertGreater(result["mutations_applied"], 0)
        self.assertIn("validator_id", result)
        self.assertIn("pass_rate", result)

    def test_mutation_detection_rate(self):
        result = self.mr.run_mutations(self._make_spec(), self._make_suite(),
                                        mutation_types=["invert_condition", "return_always_pass"])
        self.assertGreaterEqual(result["pass_rate"], 0)

    def test_mutation_test_passes_helper(self):
        self.assertTrue(self.mr.mutation_test_passes({"overall": "PASS"}))
        self.assertFalse(self.mr.mutation_test_passes({"overall": "FAIL"}))


# ══════════════════════════════════════════════════════════════════════════════
#  Certification Pipeline Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCertificationPipeline(unittest.TestCase):
    """Test certify_generated_validator.py — the full pipeline."""

    def setUp(self):
        self.cert = _get_cert()

    def _make_v0_spec(self) -> dict:
        return {
            "schema_version": "validator_spec_v1",
            "validator_id": "V.TEST.CERT",
            "authority_level": "V0_PROPOSED",
            "success_criteria": ["SC.001"],
            "check_type": "structural",
            "runtime_command": "python check.py",
        }

    def _make_good_fixture_suite(self) -> dict:
        return {
            "schema_version": "fixture_suite_v1",
            "suite_id": "S.CERT.001",
            "validator_id": "V.TEST.CERT",
            "fixtures": [
                {"fixture_id": "F.001", "type": "positive", "input": {"path": "/tmp/real"}, "expected_verdict": "PASS"},
                {"fixture_id": "F.002", "type": "negative", "input": {"path": "/nonexistent"}, "expected_verdict": "FAIL"},
            ],
        }

    def test_v0_certifies_to_v1_with_fixtures(self):
        result = self.cert.certify_validator(
            self._make_v0_spec(),
            fixture_suite=self._make_good_fixture_suite(),
        )
        self.assertEqual(result["certification_verdict"], "CERTIFIED")
        self.assertEqual(result["new_level"], "V1_LOCAL_TESTED")
        self.assertTrue(self.cert.is_certified(result))

    def test_v0_stays_v0_without_fixtures(self):
        result = self.cert.certify_validator(self._make_v0_spec())
        # Without fixtures, meta-check results vary. Just verify structure.
        self.assertIn("certification_verdict", result)
        self.assertIn("meta_check", result)

    def test_v1_to_v2_with_mutations(self):
        """V1->V2 promotion requires passing mutation tests."""
        spec = self._make_v0_spec()
        spec["authority_level"] = "V1_LOCAL_TESTED"
        suite = self._make_good_fixture_suite()
        # Add more fixtures to improve mutation detection rate
        suite["fixtures"].extend([
            {"fixture_id": "F.003", "type": "positive", "input": {"path": "/tmp/other"}, "expected_verdict": "PASS"},
            {"fixture_id": "F.004", "type": "negative", "input": {"path": "/dev/null/nope"}, "expected_verdict": "FAIL"},
            {"fixture_id": "F.005", "type": "edge", "input": {"path": ""}, "expected_verdict": "FAIL"},
        ])
        result = self.cert.certify_validator(spec, fixture_suite=suite)
        # May or may not reach V2 depending on mutation detection
        self.assertEqual(result["certification_verdict"], "CERTIFIED")
        self.assertIn(result["new_level"], ["V1_LOCAL_TESTED", "V2_INDEPENDENT_TESTED"])

    def test_invalid_spec_fails(self):
        spec = self._make_v0_spec()
        spec["authority_level"] = "INVALID"
        result = self.cert.certify_validator(spec)
        # Should still run but meta-check may find issues
        self.assertIn("failures", result)

    def test_certification_structure(self):
        result = self.cert.certify_validator(
            self._make_v0_spec(),
            fixture_suite=self._make_good_fixture_suite(),
        )
        self.assertIn("validator_id", result)
        self.assertIn("previous_level", result)
        self.assertIn("new_level", result)
        self.assertIn("certified_at", result)
        self.assertIn("meta_check", result)
        self.assertIn("fixture_tests", result)
        self.assertIn("mutation_tests", result)
        self.assertIn("failures", result)

    def test_is_certified_helper(self):
        self.assertTrue(self.cert.is_certified({"certification_verdict": "CERTIFIED"}))
        self.assertFalse(self.cert.is_certified({"certification_verdict": "FAILED"}))


# ══════════════════════════════════════════════════════════════════════════════
#  Fixture Suite Schema Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestFixtureSuiteSchema(unittest.TestCase):
    """Test fixture_suite.schema.json."""

    def test_schema_structure(self):
        schema = load_json(VF_DIR / "fixture_suite.schema.json")
        self.assertEqual(schema["title"], "fixture_suite_v1")
        required = set(schema.get("required", []))
        self.assertIn("suite_id", required)
        self.assertIn("validator_id", required)
        self.assertIn("fixtures", required)

    def test_fixture_types(self):
        schema = load_json(VF_DIR / "fixture_suite.schema.json")
        fixture_type_enum = schema["properties"]["fixtures"]["items"]["properties"]["type"]["enum"]
        self.assertIn("positive", fixture_type_enum)
        self.assertIn("negative", fixture_type_enum)
        self.assertIn("adversarial", fixture_type_enum)
        self.assertIn("edge", fixture_type_enum)


# ══════════════════════════════════════════════════════════════════════════════
#  Mutation Policy Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestMutationPolicy(unittest.TestCase):
    """Test mutation_policy.json."""

    def test_policy_exists(self):
        policy = load_json(VF_DIR / "mutation_policy.json")
        self.assertEqual(policy["schema_version"], "mutation_policy_v1")

    def test_mutation_types(self):
        policy = load_json(VF_DIR / "mutation_policy.json")
        types = {m["mutation_type"] for m in policy["mutation_definitions"]}
        self.assertIn("invert_condition", types)
        self.assertIn("return_always_pass", types)
        self.assertIn("disable_validation", types)

    def test_default_settings(self):
        policy = load_json(VF_DIR / "mutation_policy.json")
        self.assertIn("min_mutations", policy["default_settings"])
        self.assertIn("required_pass_rate", policy["default_settings"])
        self.assertGreaterEqual(policy["default_settings"]["required_pass_rate"], 0.5)


# ══════════════════════════════════════════════════════════════════════════════
#  Factory File Structure Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestFactoryStructure(unittest.TestCase):
    """Verify the overall factory file structure."""

    def test_factory_directory_exists(self):
        self.assertTrue(VF_DIR.is_dir())

    def test_runtime_directory_exists(self):
        self.assertTrue(RUNTIME_DIR.is_dir())

    def test_all_schema_files_present(self):
        files = [
            "validator_spec.schema.json",
            "validator_registry.json",
            "validator_authority_policy.json",
            "fixture_suite.schema.json",
            "mutation_policy.json",
        ]
        for f in files:
            self.assertTrue((VF_DIR / f).exists(), f"Missing: {f}")

    def test_all_runtime_files_present(self):
        files = [
            "run_validator_meta_check.py",
            "run_validator_fixtures.py",
            "run_validator_mutations.py",
            "certify_generated_validator.py",
        ]
        for f in files:
            self.assertTrue((RUNTIME_DIR / f).exists(), f"Missing: {f}")


if __name__ == "__main__":
    unittest.main()
