#!/usr/bin/env python3
"""Unittest tests for RPG-Harness v5 Phase 3: Artifact Routing.

Tests cover:
- expected_artifacts.schema.json validation
- artifact_contract.schema.json validation
- validate_expected_artifacts.py (schema + internal consistency)
- validate_artifact_location.py (location checking, misplacement, missing)
- validate_no_fallback_artifacts.py (fallback detection)
- validate_artifact_satisfaction.py (content satisfaction)
- Integration with run kernel
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = ROOT / ".agentic-pi" / "artifacts"
VALIDATORS_DIR = ARTIFACTS_DIR / "validators"

if str(VALIDATORS_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR))
if str(ARTIFACTS_DIR) not in sys.path:
    sys.path.insert(0, str(ARTIFACTS_DIR))


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_module(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_VALIDATE_EA = None
_VALIDATE_LOC = None
_VALIDATE_FALLBACK = None
_VALIDATE_SAT = None
_ARTIFACT_PLACEMENT = None


def _get_vea():
    global _VALIDATE_EA
    if _VALIDATE_EA is None:
        _VALIDATE_EA = load_module("validate_expected_artifacts",
                                   VALIDATORS_DIR / "validate_expected_artifacts.py")
    return _VALIDATE_EA


def _get_vloc():
    global _VALIDATE_LOC
    if _VALIDATE_LOC is None:
        _VALIDATE_LOC = load_module("validate_artifact_location",
                                     VALIDATORS_DIR / "validate_artifact_location.py")
    return _VALIDATE_LOC


def _get_vfallback():
    global _VALIDATE_FALLBACK
    if _VALIDATE_FALLBACK is None:
        _VALIDATE_FALLBACK = load_module("validate_no_fallback_artifacts",
                                          VALIDATORS_DIR / "validate_no_fallback_artifacts.py")
    return _VALIDATE_FALLBACK


def _get_vsat():
    global _VALIDATE_SAT
    if _VALIDATE_SAT is None:
        _VALIDATE_SAT = load_module("validate_artifact_satisfaction",
                                     VALIDATORS_DIR / "validate_artifact_satisfaction.py")
    return _VALIDATE_SAT


# ══════════════════════════════════════════════════════════════════════════════
#  Schema File Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaFiles(unittest.TestCase):
    """Verify all Phase 3 schema and policy files exist."""

    def test_expected_artifacts_schema(self):
        self.assertTrue((ARTIFACTS_DIR / "expected_artifacts.schema.json").exists())

    def test_artifact_contract_schema(self):
        self.assertTrue((ARTIFACTS_DIR / "artifact_contract.schema.json").exists())

    def test_artifact_placement_policy(self):
        self.assertTrue((ARTIFACTS_DIR / "artifact_placement_policy.json").exists())

    def test_validate_expected_artifacts(self):
        self.assertTrue((VALIDATORS_DIR / "validate_expected_artifacts.py").exists())

    def test_validate_artifact_location(self):
        self.assertTrue((VALIDATORS_DIR / "validate_artifact_location.py").exists())

    def test_validate_no_fallback_artifacts(self):
        self.assertTrue((VALIDATORS_DIR / "validate_no_fallback_artifacts.py").exists())

    def test_validate_artifact_satisfaction(self):
        self.assertTrue((VALIDATORS_DIR / "validate_artifact_satisfaction.py").exists())


# ══════════════════════════════════════════════════════════════════════════════
#  Schema Validation Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestExpectedArtifactsValidation(unittest.TestCase):
    """Test validate_expected_artifacts.py."""

    def setUp(self):
        self.vea = _get_vea()

    def _make_valid_ea(self, **overrides) -> dict:
        ea = {
            "schema_version": "expected_artifacts_v1",
            "run_id": "test_001",
            "artifacts": [
                {
                    "artifact_id": "A.REPORT",
                    "expected_path": "artifacts/report.json",
                    "required": True,
                    "allowed_writers": ["Engineer"],
                    "forbidden_writers": ["Reporter"],
                },
                {
                    "artifact_id": "A.TEST",
                    "expected_path": "artifacts/test_output.txt",
                    "required": False,
                },
            ],
        }
        ea.update(overrides)
        return ea

    def test_valid_passes(self):
        errors = self.vea.validate_expected_artifacts(self._make_valid_ea())
        self.assertEqual(errors, [])

    def test_missing_schema_version(self):
        ea = self._make_valid_ea()
        del ea["schema_version"]
        errors = self.vea.validate_expected_artifacts(ea)
        self.assertGreater(len(errors), 0)

    def test_duplicate_artifact_id(self):
        ea = self._make_valid_ea()
        ea["artifacts"].append({
            "artifact_id": "A.REPORT",
            "expected_path": "other.json",
            "required": False,
        })
        errors = self.vea.validate_expected_artifacts(ea)
        self.assertTrue(any("Duplicate artifact_id" in e for e in errors))

    def test_duplicate_expected_path(self):
        ea = self._make_valid_ea()
        ea["artifacts"].append({
            "artifact_id": "A.DUP",
            "expected_path": "artifacts/report.json",
            "required": False,
        })
        errors = self.vea.validate_expected_artifacts(ea)
        self.assertTrue(any("Duplicate expected_path" in e for e in errors))

    def test_overlapping_writers(self):
        ea = self._make_valid_ea()
        ea["artifacts"][0]["allowed_writers"] = ["Engineer", "Critic"]
        ea["artifacts"][0]["forbidden_writers"] = ["Critic"]
        errors = self.vea.validate_expected_artifacts(ea)
        self.assertTrue(any("overlap" in e for e in errors))

    def test_wrong_schema_version_rejected(self):
        ea = self._make_valid_ea(schema_version="wrong_version")
        errors = self.vea.validate_expected_artifacts(ea)
        self.assertGreater(len(errors), 0)

    def test_empty_artifacts_list(self):
        ea = self._make_valid_ea(artifacts=[])
        errors = self.vea.validate_expected_artifacts(ea)
        # Empty list is schema-valid but will be caught by location validator later
        self.assertEqual(errors, [])


# ══════════════════════════════════════════════════════════════════════════════
#  Location Validator Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestArtifactLocation(unittest.TestCase):
    """Test validate_artifact_location.py."""

    def setUp(self):
        self.vloc = _get_vloc()
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def _make_ea(self, artifacts: list) -> dict:
        return {
            "schema_version": "expected_artifacts_v1",
            "run_id": "test_loc_001",
            "artifacts": artifacts,
        }

    def _write_ea(self, ea: dict):
        (self.tmp / "expected_artifacts.json").write_text(
            json.dumps(ea), encoding="utf-8"
        )

    def _make_file(self, path: str, content: str = "data"):
        full = self.tmp / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    def test_no_expected_artifacts_file(self):
        verdicts = self.vloc.validate_artifact_location(self.tmp)
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(verdicts[0]["verdict"], "NOT_DONE")
        self.assertIn("not found", verdicts[0]["error"])

    def test_empty_artifacts_list(self):
        ea = self._make_ea([])
        self._write_ea(ea)
        verdicts = self.vloc.validate_artifact_location(self.tmp)
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(verdicts[0]["verdict"], "NOT_DONE")

    def test_all_accepted(self):
        ea = self._make_ea([
            {"artifact_id": "A.REPORT", "expected_path": "artifacts/report.json", "required": True},
            {"artifact_id": "A.TEST", "expected_path": "output.txt", "required": False},
        ])
        self._write_ea(ea)
        self._make_file("artifacts/report.json")
        self._make_file("output.txt")
        verdicts = self.vloc.validate_artifact_location(self.tmp, ea)
        self.assertTrue(self.vloc.all_accepted(verdicts))
        for v in verdicts:
            self.assertEqual(v["verdict"], "ACCEPTED")

    def test_misplaced_artifact(self):
        ea = self._make_ea([
            {"artifact_id": "A.REPORT", "expected_path": "artifacts/report.json", "required": True},
        ])
        self._write_ea(ea)
        # Artifact at wrong path (root instead of artifacts/)
        self._make_file("report.json")
        verdicts = self.vloc.validate_artifact_location(self.tmp, ea)
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(verdicts[0]["verdict"], "BLOCKED_BY_ARTIFACT_MISPLACEMENT")
        self.assertIn("instead of", verdicts[0]["error"])
        self.assertTrue(self.vloc.has_misplacement(verdicts))

    def test_missing_required(self):
        ea = self._make_ea([
            {"artifact_id": "A.REPORT", "expected_path": "artifacts/report.json", "required": True},
        ])
        self._write_ea(ea)
        # No files at all
        verdicts = self.vloc.validate_artifact_location(self.tmp, ea)
        self.assertEqual(verdicts[0]["verdict"], "NOT_DONE")
        self.assertTrue(self.vloc.has_missing_required(verdicts))
        self.assertFalse(self.vloc.all_accepted(verdicts))

    def test_optional_artifact_missing(self):
        ea = self._make_ea([
            {"artifact_id": "A.OPT", "expected_path": "optional.txt", "required": False},
        ])
        self._write_ea(ea)
        verdicts = self.vloc.validate_artifact_location(self.tmp, ea)
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(verdicts[0]["verdict"], "ACCEPTED")
        self.assertIsNone(verdicts[0]["actual_path"])

    def test_mixed_verdicts(self):
        ea = self._make_ea([
            {"artifact_id": "A.CORRECT", "expected_path": "good.txt", "required": True},
            {"artifact_id": "A.WRONG", "expected_path": "artifacts/wrong.txt", "required": True},
            {"artifact_id": "A.MISSING", "expected_path": "missing.txt", "required": True},
            {"artifact_id": "A.OPT", "expected_path": "optional.txt", "required": False},
        ])
        self._write_ea(ea)
        self._make_file("good.txt")
        self._make_file("wrong.txt")  # at root, not artifacts/
        verdicts = self.vloc.validate_artifact_location(self.tmp, ea)
        verdict_map = {v["artifact_id"]: v["verdict"] for v in verdicts}
        self.assertEqual(verdict_map["A.CORRECT"], "ACCEPTED")
        self.assertEqual(verdict_map["A.WRONG"], "BLOCKED_BY_ARTIFACT_MISPLACEMENT")
        self.assertEqual(verdict_map["A.MISSING"], "NOT_DONE")
        self.assertEqual(verdict_map["A.OPT"], "ACCEPTED")

    def test_scan_artifacts(self):
        self._make_file("a.txt")
        self._make_file("sub/b.txt")
        found = self.vloc.scan_artifacts(self.tmp)
        paths = [f["rel_path"] for f in found]
        self.assertIn("a.txt", paths)
        self.assertIn("sub/b.txt", paths)

    def test_scan_nonexistent_dir(self):
        found = self.vloc.scan_artifacts(self.tmp / "nonexistent")
        self.assertEqual(found, [])

    def test_helper_functions(self):
        self.assertTrue(self.vloc.has_misplacement([
            {"verdict": "BLOCKED_BY_ARTIFACT_MISPLACEMENT"}
        ]))
        self.assertFalse(self.vloc.has_misplacement([
            {"verdict": "ACCEPTED"}
        ]))
        self.assertTrue(self.vloc.has_missing_required([
            {"verdict": "NOT_DONE"}
        ]))
        self.assertFalse(self.vloc.has_missing_required([
            {"verdict": "ACCEPTED"}
        ]))
        self.assertTrue(self.vloc.all_accepted([
            {"verdict": "ACCEPTED"},
            {"verdict": "ACCEPTED"},
        ]))
        self.assertFalse(self.vloc.all_accepted([
            {"verdict": "ACCEPTED"},
            {"verdict": "NOT_DONE"},
        ]))


# ══════════════════════════════════════════════════════════════════════════════
#  Fallback Checker Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestNoFallbackArtifacts(unittest.TestCase):
    """Test validate_no_fallback_artifacts.py."""

    def setUp(self):
        self.vfb = _get_vfallback()
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def _make_ea(self, artifacts: list) -> dict:
        return {
            "schema_version": "expected_artifacts_v1",
            "run_id": "test_fb_001",
            "artifacts": artifacts,
        }

    def _make_file(self, path: str):
        full = self.tmp / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("data", encoding="utf-8")

    def test_no_fallback_no_warnings(self):
        """Artifact at correct path only -> no warnings."""
        ea = self._make_ea([
            {"artifact_id": "A.REPORT", "expected_path": "artifacts/report.json", "required": True},
        ])
        self._make_file("artifacts/report.json")
        warnings = self.vfb.check_no_fallback_artifacts(self.tmp, ea)
        self.assertEqual(warnings, [])

    def test_fallback_detected(self):
        """Expected at subdir but also at root -> warning."""
        ea = self._make_ea([
            {"artifact_id": "A.REPORT", "expected_path": "artifacts/report.json", "required": True},
        ])
        self._make_file("artifacts/report.json")
        self._make_file("report.json")
        warnings = self.vfb.check_no_fallback_artifacts(self.tmp, ea)
        self.assertGreater(len(warnings), 0)
        self.assertIn("A.REPORT", warnings[0]["artifact_id"])

    def test_root_expected_has_no_fallback(self):
        """Artifact expected at root has no fallback path -> no warnings."""
        ea = self._make_ea([
            {"artifact_id": "A.ROOT", "expected_path": "report.json", "required": True},
        ])
        self._make_file("report.json")
        warnings = self.vfb.check_no_fallback_artifacts(self.tmp, ea)
        self.assertEqual(warnings, [])

    def test_no_ea_file_no_warnings(self):
        warnings = self.vfb.check_no_fallback_artifacts(self.tmp)
        self.assertEqual(warnings, [])

    def test_empty_artifacts_no_warnings(self):
        ea = self._make_ea([])
        warnings = self.vfb.check_no_fallback_artifacts(self.tmp, ea)
        self.assertEqual(warnings, [])

    def test_fallback_detected_deep_path(self):
        """Deep nested expected path with an ancestor-level fallback."""
        ea = self._make_ea([
            {"artifact_id": "A.DEEP", "expected_path": "deep/nested/artifacts/data.json", "required": True},
        ])
        self._make_file("deep/nested/artifacts/data.json")
        self._make_file("data.json")  # root-level fallback
        warnings = self.vfb.check_no_fallback_artifacts(self.tmp, ea)
        self.assertGreater(len(warnings), 0)


# ══════════════════════════════════════════════════════════════════════════════
#  Satisfaction Checker Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestArtifactSatisfaction(unittest.TestCase):
    """Test validate_artifact_satisfaction.py."""

    def setUp(self):
        self.vsat = _get_vsat()
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def _make_ea(self, artifacts: list) -> dict:
        return {
            "schema_version": "expected_artifacts_v1",
            "run_id": "test_sat_001",
            "artifacts": artifacts,
        }

    def _make_file(self, path: str, content: str = "data"):
        full = self.tmp / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    def test_file_exists_satisfied(self):
        ea = self._make_ea([
            {"artifact_id": "A.EXISTS", "expected_path": "exists.txt", "required": True},
        ])
        self._make_file("exists.txt")
        results = self.vsat.check_satisfaction(self.tmp, ea)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["verdict"], "SATISFIED")
        self.assertEqual(results[0]["checks"][0]["check"], "file_exists")
        self.assertTrue(results[0]["checks"][0]["passed"])

    def test_file_missing_fails(self):
        ea = self._make_ea([
            {"artifact_id": "A.MISSING", "expected_path": "missing.txt", "required": True},
        ])
        results = self.vsat.check_satisfaction(self.tmp, ea)
        self.assertEqual(results[0]["verdict"], "FAILED")

    def test_min_size_passes(self):
        ea = self._make_ea([
            {"artifact_id": "A.SIZE", "expected_path": "size.txt", "required": True, "min_size_bytes": 3},
        ])
        self._make_file("size.txt", "hello")
        results = self.vsat.check_satisfaction(self.tmp, ea)
        self.assertEqual(results[0]["verdict"], "SATISFIED")

    def test_min_size_fails(self):
        ea = self._make_ea([
            {"artifact_id": "A.SIZE", "expected_path": "size.txt", "required": True, "min_size_bytes": 100},
        ])
        self._make_file("size.txt", "small")
        results = self.vsat.check_satisfaction(self.tmp, ea)
        self.assertEqual(results[0]["verdict"], "FAILED")
        self.assertFalse(results[0]["checks"][1]["passed"])

    def test_max_size_passes(self):
        ea = self._make_ea([
            {"artifact_id": "A.MAX", "expected_path": "max.txt", "required": True, "max_size_bytes": 100},
        ])
        self._make_file("max.txt", "small")
        results = self.vsat.check_satisfaction(self.tmp, ea)
        self.assertEqual(results[0]["verdict"], "SATISFIED")

    def test_max_size_fails(self):
        ea = self._make_ea([
            {"artifact_id": "A.MAX", "expected_path": "max.txt", "required": True, "max_size_bytes": 3},
        ])
        self._make_file("max.txt", "too long content")
        results = self.vsat.check_satisfaction(self.tmp, ea)
        self.assertEqual(results[0]["verdict"], "FAILED")

    def test_valid_json_passes(self):
        ea = self._make_ea([
            {"artifact_id": "A.JSON", "expected_path": "data.json", "required": True, "must_be_valid_json": True},
        ])
        self._make_file("data.json", '{"key": "value"}')
        results = self.vsat.check_satisfaction(self.tmp, ea)
        self.assertEqual(results[0]["verdict"], "SATISFIED")

    def test_invalid_json_fails(self):
        ea = self._make_ea([
            {"artifact_id": "A.JSON", "expected_path": "data.json", "required": True, "must_be_valid_json": True},
        ])
        self._make_file("data.json", "not valid json")
        results = self.vsat.check_satisfaction(self.tmp, ea)
        self.assertEqual(results[0]["verdict"], "FAILED")
        invalid_check = [c for c in results[0]["checks"] if c["check"] == "valid_json"]
        self.assertTrue(any(not c["passed"] for c in invalid_check))

    def test_multiple_checks(self):
        """Multiple satisfaction criteria on one artifact."""
        ea = self._make_ea([
            {
                "artifact_id": "A.MULTI",
                "expected_path": "multi.json",
                "required": True,
                "min_size_bytes": 5,
                "max_size_bytes": 100,
                "must_be_valid_json": True,
                "min_satisfaction": {"must_not_be_empty": True},
            },
        ])
        self._make_file("multi.json", '{"a":1}')
        results = self.vsat.check_satisfaction(self.tmp, ea)
        self.assertEqual(results[0]["verdict"], "SATISFIED")
        self.assertEqual(len(results[0]["checks"]), 5)  # exists + min + max + json + not_empty

    def test_not_empty_fails(self):
        ea = self._make_ea([
            {
                "artifact_id": "A.EMPTY",
                "expected_path": "empty.txt",
                "required": True,
                "min_satisfaction": {"must_not_be_empty": True},
            },
        ])
        self._make_file("empty.txt", "")
        results = self.vsat.check_satisfaction(self.tmp, ea)
        self.assertEqual(results[0]["verdict"], "FAILED")

    def test_no_ea_file_empty_results(self):
        results = self.vsat.check_satisfaction(self.tmp)
        self.assertEqual(results, [])


# ══════════════════════════════════════════════════════════════════════════════
#  Integration Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestArtifactRoutingIntegration(unittest.TestCase):
    """Integration tests combining artifact routing with the run kernel."""

    def setUp(self):
        # Load run kernel
        rk_path = ROOT / ".agentic-pi" / "run_kernel" / "run_kernel.py"
        self.rk = load_module("run_kernel", rk_path)

        self.vea = _get_vea()
        self.vloc = _get_vloc()
        self.vfb = _get_vfallback()
        self.vsat = _get_vsat()

        self.tmp = Path(tempfile.mkdtemp())
        self.old_runs_dir = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs_dir
        import shutil
        shutil.rmtree(self.tmp)

    def _make_file(self, run_dir: Path, path: str, content: str = "data"):
        full = run_dir / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    def test_kernel_create_and_validate_artifacts(self):
        """Create a run via kernel, write expected artifacts, validate."""
        run_id = "test_kernel_artifacts_001"
        self.rk.create_run(run_id)
        run_dir = self.rk.get_run_dir(run_id)

        # Write expected_artifacts.json
        ea = {
            "schema_version": "expected_artifacts_v1",
            "run_id": run_id,
            "artifacts": [
                {"artifact_id": "A.REPORT", "expected_path": "work_results/report.json", "required": True},
            ],
        }
        (run_dir / "expected_artifacts.json").write_text(json.dumps(ea), encoding="utf-8")

        # Validate without files -> NOT_DONE
        verdicts = self.vloc.validate_artifact_location(run_dir)
        self.assertEqual(verdicts[0]["verdict"], "NOT_DONE")

        # Create the file at correct path
        self._make_file(run_dir, "work_results/report.json", '{"result": "pass"}')

        # Validate again -> ACCEPTED
        verdicts = self.vloc.validate_artifact_location(run_dir)
        self.assertEqual(verdicts[0]["verdict"], "ACCEPTED")

    def test_misplacement_detected_in_run(self):
        """Artifact at wrong path triggers BLOCKED_BY_ARTIFACT_MISPLACEMENT."""
        run_id = "test_misplacement_001"
        self.rk.create_run(run_id)
        run_dir = self.rk.get_run_dir(run_id)

        ea = {
            "schema_version": "expected_artifacts_v1",
            "run_id": run_id,
            "artifacts": [
                {"artifact_id": "A.REPORT", "expected_path": "artifacts/report.json", "required": True},
            ],
        }
        (run_dir / "expected_artifacts.json").write_text(json.dumps(ea), encoding="utf-8")

        # File at wrong path
        self._make_file(run_dir, "report.json", "{}")

        verdicts = self.vloc.validate_artifact_location(run_dir)
        self.assertEqual(verdicts[0]["verdict"], "BLOCKED_BY_ARTIFACT_MISPLACEMENT")
        self.assertTrue(self.vloc.has_misplacement(verdicts))

        # Verify fallback detection also catches this
        warnings = self.vfb.check_no_fallback_artifacts(run_dir)
        self.assertGreater(len(warnings), 0)

    def test_full_artifact_validation_pipeline(self):
        """Run all three validators in sequence: location, fallback, satisfaction."""
        run_id = "test_full_pipeline_001"
        self.rk.create_run(run_id)
        run_dir = self.rk.get_run_dir(run_id)

        ea = {
            "schema_version": "expected_artifacts_v1",
            "run_id": run_id,
            "artifacts": [
                {
                    "artifact_id": "A.JSON",
                    "expected_path": "artifacts/data.json",
                    "required": True,
                    "min_size_bytes": 5,
                    "must_be_valid_json": True,
                },
            ],
        }
        (run_dir / "expected_artifacts.json").write_text(json.dumps(ea), encoding="utf-8")

        # Create artifact at correct path with valid content
        self._make_file(run_dir, "artifacts/data.json", '{"key": "value"}')

        # Location check
        loc = self.vloc.validate_artifact_location(run_dir)
        self.assertTrue(self.vloc.all_accepted(loc))

        # Fallback check
        fb = self.vfb.check_no_fallback_artifacts(run_dir)
        self.assertEqual(fb, [])

        # Satisfaction check
        sat = self.vsat.check_satisfaction(run_dir)
        self.assertEqual(sat[0]["verdict"], "SATISFIED")

    def test_artifact_contract_schema_validity(self):
        """Verify the artifact_contract.schema.json is valid JSON Schema."""
        schema = load_json(ARTIFACTS_DIR / "artifact_contract.schema.json")
        self.assertEqual(schema["title"], "artifact_contract_v1")
        required = schema.get("required", [])
        self.assertIn("contract_id", required)
        self.assertIn("work_packet_id", required)
        self.assertIn("expected_path", required)
        self.assertIn("allowed_writers", required)
        self.assertIn("forbidden_writers", required)

    def test_artifact_placement_policy_validity(self):
        """Verify artifact_placement_policy.json loads and has key rules."""
        policy = load_json(ARTIFACTS_DIR / "artifact_placement_policy.json")
        self.assertEqual(policy["schema_version"], "artifact_placement_policy_v1")
        rules = policy.get("rules", [])
        rule_ids = [r["id"] for r in rules]
        self.assertIn("expected_path_required", rule_ids)
        self.assertIn("no_fallback_artifacts", rule_ids)
        self.assertIn("no_orphan_authority_artifacts", rule_ids)
        self.assertIn("required_artifacts_must_be_present", rule_ids)

        # Verify protected names
        protected_rule = [r for r in rules if r["id"] == "no_orphan_authority_artifacts"][0]
        self.assertIn("final_status.json", protected_rule["protected_names"])
        self.assertIn("certification.json", protected_rule["protected_names"])


if __name__ == "__main__":
    unittest.main()
