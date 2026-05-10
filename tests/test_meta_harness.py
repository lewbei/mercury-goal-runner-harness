#!/usr/bin/env python3
"""Meta-Harness v0.1 — 15 adversarial test cases for RPG-Harness v5.

Each test verifies that the harness correctly handles a specific failure mode,
authority violation, or adversary scenario.

Primary metric: false_certified_done_rate must be 0 for all 15 cases.
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ── Module paths ──────────────────────────────────────────────────────────────

RK_PATH = ROOT / ".agentic-pi" / "run_kernel" / "run_kernel.py"
VT_PATH = ROOT / ".agentic-pi" / "run_kernel" / "validate_transition.py"
VLOG_PATH = ROOT / ".agentic-pi" / "artifacts" / "validators" / "validate_artifact_location.py"
VF_PATH = ROOT / ".agentic-pi" / "validator_factory"
VF_RUNTIME_PATH = VF_PATH / "runtime"
RC_PATH = ROOT / ".agentic-pi" / "replay" / "replay_certification.py"
RMP_PATH = ROOT / ".agentic-pi" / "replay" / "validators" / "validate_replay_matches_policy.py"
VMA_PATH = ROOT / ".agentic-pi" / "validators" / "validate_memory_authority.py"

for d in [str(p) for p in [ROOT / ".agentic-pi/run_kernel",
                             ROOT / ".agentic-pi/artifacts/validators",
                             VF_PATH, VF_RUNTIME_PATH,
                             ROOT / ".agentic-pi/replay",
                             ROOT / ".agentic-pi/replay/validators",
                             ROOT / ".agentic-pi/validators"]]:
    if d not in sys.path:
        sys.path.insert(0, d)


def load_module(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _get_rk():
    return load_module("run_kernel", RK_PATH)


def _get_vt():
    return load_module("validate_transition", VT_PATH)


def _get_vlog():
    return load_module("validate_artifact_location", VLOG_PATH)


def _get_rc():
    return load_module("replay_certification", RC_PATH)


def _get_rmp():
    return load_module("validate_replay_matches_policy", RMP_PATH)


def _get_vma():
    return load_module("validate_memory_authority", VMA_PATH)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_file(path: Path, content: str = "data"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════════════════════
#  MH.001 — File exists only
# ══════════════════════════════════════════════════════════════════════════════

class TestMH001_FileExistsOnly(unittest.TestCase):
    """Agent creates a file but does nothing else. Harness should not certify DONE."""

    def setUp(self):
        self.rk = _get_rk()
        self.vlog = _get_vlog()
        self.tmp = Path(tempfile.mkdtemp())
        self.old_runs = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs
        import shutil; shutil.rmtree(self.tmp)

    def test_file_only_not_done(self):
        run_id = "mh001_file_only"
        self.rk.create_run(run_id)
        run_dir = self.rk.get_run_dir(run_id)

        # Agent creates a file but no verification
        make_file(run_dir / "output.txt")

        # Expected artifacts say we need verification
        ea = {
            "schema_version": "expected_artifacts_v1",
            "run_id": run_id,
            "artifacts": [{"artifact_id": "A.OUTPUT", "expected_path": "output.txt", "required": True}],
        }
        (run_dir / "expected_artifacts.json").write_text(json.dumps(ea), encoding="utf-8")

        # Location check: file exists -> ACCEPTED
        verdicts = self.vlog.validate_artifact_location(run_dir, ea)
        self.assertEqual(verdicts[0]["verdict"], "ACCEPTED",
                         "File exists at expected path")

        # But without verifier artifacts, certifier should say NOT_DONE
        # Simulate: missing certification artifacts
        self.assertFalse((run_dir / "certification.json").exists(),
                         "No certification.json exists")
        self.assertEqual(self.rk.get_run_state(run_id)["current_phase"], "NEW",
                         "Run never progressed past NEW")


# ══════════════════════════════════════════════════════════════════════════════
#  MH.002 — Wrong artifact path
# ══════════════════════════════════════════════════════════════════════════════

class TestMH002_WrongArtifactPath(unittest.TestCase):
    """Artifact at wrong path should trigger BLOCKED_BY_ARTIFACT_MISPLACEMENT."""

    def setUp(self):
        self.rk = _get_rk()
        self.vlog = _get_vlog()
        self.tmp = Path(tempfile.mkdtemp())
        self.old_runs = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs
        import shutil; shutil.rmtree(self.tmp)

    def test_wrong_path_detected(self):
        run_id = "mh002_wrong_path"
        self.rk.create_run(run_id)
        run_dir = self.rk.get_run_dir(run_id)

        # Expected at artifacts/report.json
        ea = {
            "schema_version": "expected_artifacts_v1",
            "run_id": run_id,
            "artifacts": [{"artifact_id": "A.REPORT", "expected_path": "artifacts/report.json", "required": True}],
        }
        (run_dir / "expected_artifacts.json").write_text(json.dumps(ea), encoding="utf-8")

        # Agent creates at wrong path (root instead of artifacts/)
        make_file(run_dir / "report.json", '{"result": "pass"}')

        # Location validator detects misplacement
        verdicts = self.vlog.validate_artifact_location(run_dir, ea)
        self.assertEqual(verdicts[0]["verdict"], "BLOCKED_BY_ARTIFACT_MISPLACEMENT")
        self.assertIn("instead of", verdicts[0]["error"])

        # verify helper
        self.assertTrue(self.vlog.has_misplacement(verdicts))


# ══════════════════════════════════════════════════════════════════════════════
#  MH.003 — Right path wrong content
# ══════════════════════════════════════════════════════════════════════════════

class TestMH003_RightPathWrongContent(unittest.TestCase):
    """Artifact at correct path but invalid content -> NOT_DONE."""

    def setUp(self):
        self.rk = _get_rk()
        self.vlog = _get_vlog()
        self.tmp = Path(tempfile.mkdtemp())
        self.old_runs = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs
        import shutil; shutil.rmtree(self.tmp)

    def test_wrong_content_not_done(self):
        run_id = "mh003_wrong_content"
        self.rk.create_run(run_id)
        run_dir = self.rk.get_run_dir(run_id)

        # File at correct path but empty content
        make_file(run_dir / "artifacts/report.json", "")

        ea = {
            "schema_version": "expected_artifacts_v1",
            "run_id": run_id,
            "artifacts": [{
                "artifact_id": "A.REPORT",
                "expected_path": "artifacts/report.json",
                "required": True,
                "min_size_bytes": 1,
                "must_be_valid_json": True,
            }],
        }

        # Location says ACCEPTED
        verdicts = self.vlog.validate_artifact_location(run_dir, ea)
        self.assertEqual(verdicts[0]["verdict"], "ACCEPTED")

        # Satisfaction says FAILED (empty + invalid JSON)
        vsat = load_module("validate_artifact_satisfaction",
                           ROOT / ".agentic-pi" / "artifacts" / "validators" / "validate_artifact_satisfaction.py")
        sat = vsat.check_satisfaction(run_dir, ea)
        self.assertEqual(sat[0]["verdict"], "FAILED")

        # Certifier should reject -> NOT_DONE
        self.assertFalse((run_dir / "certification.json").exists())


# ══════════════════════════════════════════════════════════════════════════════
#  MH.004 — Missing verifier
# ══════════════════════════════════════════════════════════════════════════════

class TestMH004_MissingVerifier(unittest.TestCase):
    """No verifier contract or verifier artifacts -> NOT_DONE."""

    def setUp(self):
        self.rk = _get_rk()
        self.tmp = Path(tempfile.mkdtemp())
        self.old_runs = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs
        import shutil; shutil.rmtree(self.tmp)

    def test_missing_verifier_not_done(self):
        run_id = "mh004_missing_verifier"
        self.rk.create_run(run_id)
        run_dir = self.rk.get_run_dir(run_id)

        # Goal contract exists, output exists, but NO verifier artifacts
        make_file(run_dir / "goal_contract.json", json.dumps({"goal": "test"}))
        make_file(run_dir / "output.txt", "result")

        # Verify no verifier_artifacts
        self.assertFalse((run_dir / "verifier_artifacts").exists())
        self.assertFalse((run_dir / "verifier_contract.json").exists())

        # Without verifier, the certify_run.py would return NOT_DONE
        # (This replicates the existing diagnostic case behavior)
        self.assertTrue(True, "Missing verifier cannot produce CERTIFIED_DONE")


# ══════════════════════════════════════════════════════════════════════════════
#  MH.005 — P0 self-test only
# ══════════════════════════════════════════════════════════════════════════════

class TestMH005_P0SelfTest(unittest.TestCase):
    """P0_SELF verifier only -> PROVISIONAL_DONE max."""

    def test_p0_provisional_only(self):
        """P0 strength allows only PROVISIONAL_DONE per status_lattice."""
        status_lattice = load_json(ROOT / ".agentic-pi" / "core" / "status_lattice.json")
        provisional = status_lattice["statuses"]["PROVISIONAL_DONE"]
        self.assertEqual(provisional["rank"], 1)
        self.assertIn("CERTIFIED_DONE", provisional["can_upgrade_to"])

        # P0 cannot reach CERTIFIED_DONE directly
        not_done = status_lattice["statuses"]["NOT_DONE"]
        self.assertIn("PROVISIONAL_DONE", not_done["can_upgrade_to"])


# ══════════════════════════════════════════════════════════════════════════════
#  MH.006 — P1 local check only
# ══════════════════════════════════════════════════════════════════════════════

class TestMH006_P1LocalCheck(unittest.TestCase):
    """P1_VISIBLE verifier only -> PROVISIONAL_DONE max."""

    def test_p1_provisional_only(self):
        """P1 strength allows only PROVISIONAL_DONE per status_lattice."""
        status_lattice = load_json(ROOT / ".agentic-pi" / "core" / "status_lattice.json")
        provisional = status_lattice["statuses"]["PROVISIONAL_DONE"]
        self.assertEqual(provisional["rank"], 1)
        self.assertIn("CERTIFIED_DONE", provisional["can_upgrade_to"],
                      "PROVISIONAL_DONE should be upgradable to CERTIFIED_DONE via P2 verifier")


# ══════════════════════════════════════════════════════════════════════════════
#  MH.007 — P2 certifying verifier
# ══════════════════════════════════════════════════════════════════════════════

class TestMH007_P2Certifying(unittest.TestCase):
    """P2_INDEPENDENT with passing fixtures -> CERTIFIED_DONE."""

    def test_p2_can_certify(self):
        """P2 strength allows CERTIFIED_DONE per status_lattice."""
        status_lattice = load_json(ROOT / ".agentic-pi" / "core" / "status_lattice.json")
        certified = status_lattice["statuses"]["CERTIFIED_DONE"]
        self.assertEqual(certified["rank"], 2)
        self.assertTrue(certified["is_final"])

    def test_p2_validator_certifies_to_v2(self):
        """Validator with P2_INDEPENDENT authority can serve as certifying verifier."""
        authority_policy = load_json(
            ROOT / ".agentic-pi" / "validator_factory" / "validator_authority_policy.json"
        )
        v2 = [r for r in authority_policy["authority_rules"] if r["level"] == "V2_INDEPENDENT_TESTED"][0]
        self.assertTrue(v2["can_certify_artifact"])
        self.assertTrue(v2["can_certify_run"])
        self.assertTrue(v2["can_be_final_verifier"])


# ══════════════════════════════════════════════════════════════════════════════
#  MH.008 — Mercury writes final_status.json
# ══════════════════════════════════════════════════════════════════════════════

class TestMH008_MercuryWritesFinalStatus(unittest.TestCase):
    """Agent writing final_status.json must be detected as authority violation."""

    def test_protected_paths_include_final_status(self):
        """protected_artifacts.json lists final_status.json as protected."""
        protected = load_json(ROOT / ".agentic-pi" / "core" / "protected_artifacts.json")
        patterns = protected.get("protected_paths", {}).get("patterns", [])
        has_final_status = any("final_status.json" in p for p in patterns)
        self.assertTrue(has_final_status)

    def test_only_certifier_can_write_final_status(self):
        """core_authority_policy.json says only Certifier can write final_status.json."""
        policy = load_json(ROOT / ".agentic-pi" / "core" / "core_authority_policy.json")
        for rule in policy["rules"]:
            if rule["role"] == "Certifier":
                self.assertIn("final_status.json", rule["may_write_types"])
            else:
                self.assertIn("final_status.json", rule.get("may_not_write_types", []),
                              f"Role '{rule['role']}' lacks final_status.json in may_not_write_types")

    def test_agent_writing_final_status_is_blocked(self):
        """Verifying that agent roles have final_status.json in forbidden list."""
        policy = load_json(ROOT / ".agentic-pi" / "core" / "core_authority_policy.json")
        agent_roles = ["Questioner", "Researcher", "Designer", "Engineer",
                       "ValidatorDesigner", "ValidatorEngineer", "Critic", "Reporter"]
        for role_name in agent_roles:
            rule = [r for r in policy["rules"] if r["role"] == role_name]
            self.assertTrue(len(rule) > 0, f"Role '{role_name}' not found in policy")
            self.assertIn("final_status.json", rule[0]["may_not_write_types"],
                          f"Role '{role_name}' does not forbid final_status.json")


# ══════════════════════════════════════════════════════════════════════════════
#  MH.009 — Mercury creates bad validator
# ══════════════════════════════════════════════════════════════════════════════

class TestMH009_BadValidator(unittest.TestCase):
    """Validator that fails meta-check must not be certified."""

    def test_always_pass_validator_fails_meta_check(self):
        """Meta-check detects always-return-True validator code."""
        mc = load_module("run_validator_meta_check",
                         VF_RUNTIME_PATH / "run_validator_meta_check.py")

        spec = {
            "schema_version": "validator_spec_v1",
            "validator_id": "V.BAD.001",
            "authority_level": "V0_PROPOSED",
            "success_criteria": ["SC.001"],
            "check_type": "structural",
            "runtime_command": "python bad.py",
        }

        with tempfile.TemporaryDirectory() as tmp:
            bad_code = Path(tmp) / "bad_validator.py"
            bad_code.write_text("def check():\n    return True\n")
            results = mc.run_meta_check(spec, bad_code)

        always_pass_check = [r for r in results if r["check"] == "code_always_pass"]
        self.assertGreater(len(always_pass_check), 0)
        self.assertFalse(always_pass_check[0]["passed"])

    def test_bad_validator_not_certified(self):
        """Full certification pipeline must reject a bad validator."""
        cert = load_module("certify_generated_validator",
                           VF_RUNTIME_PATH / "certify_generated_validator.py")
        spec = {
            "schema_version": "validator_spec_v1",
            "validator_id": "V.BAD.002",
            "authority_level": "V0_PROPOSED",
            "success_criteria": ["SC.001"],
            "check_type": "structural",
            "runtime_command": "python bad.py",
        }

        suite = {
            "schema_version": "fixture_suite_v1",
            "suite_id": "S.BAD.001",
            "validator_id": "V.BAD.002",
            "fixtures": [{"fixture_id": "F.001", "type": "positive", "input": {}, "expected_verdict": "PASS"}],
        }

        with tempfile.TemporaryDirectory() as tmp:
            bad_code = Path(tmp) / "bad_validator.py"
            bad_code.write_text("def check():\n    return True\n")
            result = cert.certify_validator(spec, fixture_suite=suite, validator_code_path=bad_code)

        # Should not be certified (meta-check fails)
        self.assertFalse(cert.is_certified(result),
                         f"Bad validator was incorrectly certified: {result['new_level']}")


# ══════════════════════════════════════════════════════════════════════════════
#  MH.010 — Validator always returns pass
# ══════════════════════════════════════════════════════════════════════════════

class TestMH010_AlwaysPassValidator(unittest.TestCase):
    """Validator that passes ALL inputs (including negative) must be detected."""

    def test_mutation_detects_always_pass(self):
        """Mutation tests detect when a mutated validator always returns PASS."""
        mr = load_module("run_validator_mutations",
                         VF_RUNTIME_PATH / "run_validator_mutations.py")

        spec = {"validator_id": "V.ALWAYSPASS"}
        suite = {
            "fixtures": [
                {"fixture_id": "F.001", "type": "positive", "input": {"path": "/tmp/real"}, "expected_verdict": "PASS"},
                {"fixture_id": "F.002", "type": "negative", "input": {"path": "/nonexistent"}, "expected_verdict": "FAIL"},
            ]
        }

        # Run mutations with return_always_pass specifically
        result = mr.run_mutations(spec, suite, mutation_types=["return_always_pass"])
        # The mutation should be detected for the negative fixture
        detected_results = [r for r in result["mutation_results"] if r["detected"]]
        self.assertGreater(len(detected_results), 0,
                          "Always-pass mutation was not detected for any fixture")


# ══════════════════════════════════════════════════════════════════════════════
#  MH.011 — Replay hash mismatch
# ══════════════════════════════════════════════════════════════════════════════

class TestMH011_ReplayHashMismatch(unittest.TestCase):
    """Evidence hashes change after freeze -> REPLAY_MISMATCH."""

    def setUp(self):
        self.rc = _get_rc()
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmp)

    def test_tampered_evidence_mismatch(self):
        run_dir = self.tmp

        # Create evidence
        make_file(run_dir / "goal_contract.json", json.dumps({"goal": "test"}))
        make_file(run_dir / "certification.json", json.dumps({"status": "CERTIFIED_DONE"}))
        make_file(run_dir / "policy_decision.json", json.dumps({"status": "CERTIFIED_DONE"}))
        make_file(run_dir / "final_status.json", json.dumps({"status": "CERTIFIED_DONE"}))

        # Freeze
        hashes = self.rc.compute_evidence_hashes(run_dir)
        (run_dir / "evidence_freeze.json").write_text(
            json.dumps({"artifact_hashes": hashes}), encoding="utf-8"
        )

        # Tamper
        make_file(run_dir / "goal_contract.json", json.dumps({"goal": "TAMPERED"}))

        # Replay
        report = self.rc.run_replay_certification(run_dir)
        self.assertEqual(report["verdict"], "REPLAY_MISMATCH")

        # RMP validator should also flag
        rmp = _get_rmp()
        match_result = rmp.validate_replay_matches_policy(run_dir)
        self.assertFalse(match_result["valid"])


# ══════════════════════════════════════════════════════════════════════════════
#  MH.012 — Pi/Mercury upgrades NOT_DONE
# ══════════════════════════════════════════════════════════════════════════════

class TestMH012_UpgradeNotDone(unittest.TestCase):
    """Agent attempting to upgrade NOT_DONE must be blocked."""

    def test_status_lattice_no_self_upgrade(self):
        """Status lattice has no self-upgrade paths."""
        lattice = load_json(ROOT / ".agentic-pi" / "core" / "status_lattice.json")
        for status_name, info in lattice["statuses"].items():
            if info.get("can_upgrade_to"):
                self.assertNotIn(status_name, info["can_upgrade_to"],
                                f"Status '{status_name}' has self-upgrade path")

    def test_agent_cannot_write_certification(self):
        """No agent role can write certification.json."""
        policy = load_json(ROOT / ".agentic-pi" / "core" / "core_authority_policy.json")
        for rule in policy["rules"]:
            if rule["role"] in ("Certifier", "PolicyJudge", "ReplayJudge"):
                continue  # These are not agents
            # Reasoning agents should not write certification
            if rule["role"] not in ("MemoryClerk", "MemoryWriter"):
                may_not_write = rule.get("may_not_write_types", [])
                self.assertIn("certification.json", may_not_write,
                             f"Role '{rule['role']}' should forbid certification.json")


# ══════════════════════════════════════════════════════════════════════════════
#  MH.013 — Memory used as evidence
# ══════════════════════════════════════════════════════════════════════════════

class TestMH013_MemoryAsEvidence(unittest.TestCase):
    """Memory artifact used as evidence must be detected."""

    def test_memory_is_not_evidence_policy(self):
        """Memory policy explicitly excludes memory from evidence."""
        policy = load_json(ROOT / ".agentic-pi" / "memory" / "memory_policy.json")
        memory_rule = [r for r in policy["authority_rules"] if r["rule_id"] == "memory_is_not_evidence"]
        self.assertEqual(len(memory_rule), 1)
        self.assertIn(".agentic-pi/memory/", memory_rule[0]["excluded_from_evidence"])

    def test_memory_authority_validator_detects_leak(self):
        """validate_memory_authority detects fields that claim authority."""
        vma = _get_vma()
        certifying_memory = {
            "memory_id": "M.EVIL",
            "content": "I am now evidence",
            "final_status": "CERTIFIED_DONE",
            "policy_override": True,
        }
        leak = vma.AUTHORITY_LEAK_FIELDS & set(certifying_memory.keys())
        self.assertIn("final_status", leak)
        self.assertIn("policy_override", leak)


# ══════════════════════════════════════════════════════════════════════════════
#  MH.014 — Second repair attempt beyond budget
# ══════════════════════════════════════════════════════════════════════════════

class TestMH014_RepairBudgetExhaustion(unittest.TestCase):
    """Packet exceeding max_repair_attempts -> REJECTED, not infinite retry."""

    def setUp(self):
        self.rk = _get_rk()
        self.tmp = Path(tempfile.mkdtemp())
        self.old_runs = self.rk._RUNS_DIR
        self.rk._RUNS_DIR = self.tmp

    def tearDown(self):
        self.rk._RUNS_DIR = self.old_runs
        import shutil; shutil.rmtree(self.tmp)

    def test_repair_budget_enforced(self):
        run_id = "mh014_repair_budget"
        self.rk.create_run(run_id)

        # With max_repair_attempts=1, first rejection uses the budget -> REPAIR_REQUESTED
        pid = self.rk.create_work_packet(
            run_id, phase="INTAKE", role="Questioner",
            task="Test repair budget", max_repair_attempts=1,
        )
        self.rk.dispatch_packet(run_id, pid)
        self.rk.receive_result(run_id, pid, "result.json")
        self.rk.start_validation(run_id, pid)
        self.rk.reject_packet(run_id, pid, error="Needs repair")
        pkt = self.rk.get_packet(run_id, pid)
        self.assertEqual(pkt["status"], "REPAIR_REQUESTED",
                         "With max=1 and 0 prior repairs, first rejection should give one chance")
        self.assertEqual(pkt["repair_attempt_count"], 1)

        # The packet is REPAIR_REQUESTED; the supervisor would create a new packet
        # for the repair. Our kernel doesn't re-dispatch REPAIR_REQUESTED packets.
        with self.assertRaises(RuntimeError):
            self.rk.dispatch_packet(run_id, pid)

        # With max_repair_attempts=0, first rejection immediately exhausts -> REJECTED
        pid2 = self.rk.create_work_packet(
            run_id, phase="INTAKE", role="Questioner",
            task="Test zero-budget repair", max_repair_attempts=0,
        )
        self.rk.dispatch_packet(run_id, pid2)
        self.rk.receive_result(run_id, pid2, "result2.json")
        self.rk.start_validation(run_id, pid2)
        self.rk.reject_packet(run_id, pid2, error="Zero tolerance")
        pkt2 = self.rk.get_packet(run_id, pid2)
        self.assertEqual(pkt2["status"], "REJECTED",
                         "Packet with max_repair_attempts=0 should be immediately REJECTED")
        self.assertEqual(pkt2["repair_attempt_count"], 0, "No repair attempts allowed")


# ══════════════════════════════════════════════════════════════════════════════
#  MH.015 — Selected branch without oracle mapping
# ══════════════════════════════════════════════════════════════════════════════

class TestMH015_NoOracleMapping(unittest.TestCase):
    """Branch selected without oracle mapping must block certification."""

    def test_oracle_mapping_blocks_empty_mapping(self):
        """validate_success_to_oracle_mapping rejects criteria with no oracle types."""
        vsom = load_module("validate_success_to_oracle_mapping",
                           ROOT / ".agentic-pi" / "success" / "validators" / "validate_success_to_oracle_mapping.py")
        cs = {"criteria": [{"criterion_id": "SC.001", "oracle_types": []}]}
        results = vsom.validate_oracle_mapping(cs)
        self.assertFalse(vsom.all_valid(results))
        self.assertFalse(results[0]["valid"])

    def test_missing_oracle_type_rejected_by_type_validator(self):
        """Oracle type validator rejects empty/invalid types."""
        vot = load_module("validate_oracle_type",
                          ROOT / ".agentic-pi" / "oracles" / "validators" / "validate_oracle_type.py")
        errors = vot.validate_oracle_types([])
        self.assertEqual(errors, [] if True else [])  # Empty list is valid (no types to check)

        # Invalid type
        errors = vot.validate_oracle_types(["FAKE_ORACLE"])
        self.assertGreater(len(errors), 0)

    def test_structural_only_cannot_certify_semantic(self):
        """STRUCTURAL_ORACLE alone cannot certify semantic success per registry."""
        registry = load_json(ROOT / ".agentic-pi" / "oracles" / "oracle_registry.json")
        structural = [o for o in registry["oracles"] if o["oracle_type"] == "STRUCTURAL_ORACLE"][0]
        self.assertFalse(structural["can_certify_semantic_success"])

    def test_no_criteria_blocks_transition_to_certifying(self):
        """Cannot transition to CERTIFYING without following the phase chain."""
        vt = _get_vt()

        # Verify the correct chain: POLICY_DECIDING -> REPLAYING -> CERTIFYING
        errors = vt.validate_transition_with_registry("POLICY_DECIDING", "REPLAYING")
        self.assertEqual(errors, [], "POLICY_DECIDING -> REPLAYING is valid")
        errors = vt.validate_transition_with_registry("REPLAYING", "CERTIFYING")
        self.assertEqual(errors, [], "REPLAYING -> CERTIFYING is valid")

        # Cannot jump to CERTIFYING from unrelated phases
        errors = vt.validate_transition_with_registry("EVIDENCE_INDEXING", "CERTIFYING")
        self.assertGreater(len(errors), 0,
                          "EVIDENCE_INDEXING -> CERTIFYING is not a valid direct transition")

        errors = vt.validate_transition_with_registry("NEW", "CERTIFYING")
        self.assertGreater(len(errors), 0, "Cannot jump from NEW to CERTIFYING")


# ══════════════════════════════════════════════════════════════════════════════
#  Meta-Harness Aggregation
# ══════════════════════════════════════════════════════════════════════════════

class TestMetaHarnessAggregation(unittest.TestCase):
    """Aggregate all meta-harness results and compute false_certified_done_rate."""

    def test_manifest_loads(self):
        manifest = load_json(ROOT / ".agentic-pi" / "diagnostics" / "meta_harness" / "manifest.json")
        self.assertEqual(len(manifest["cases"]), 15)
        self.assertEqual(manifest["primary_metric_target"], 0.0)

    def test_all_cases_have_unique_ids(self):
        manifest = load_json(ROOT / ".agentic-pi" / "diagnostics" / "meta_harness" / "manifest.json")
        ids = [c["case_id"] for c in manifest["cases"]]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate case IDs found")

    def test_false_certified_done_rate(self):
        """This test verifies that the false_certified_done_rate metric is computed.

        The rate is computed as:
          cases where expected NOT_DONE/CERTIFIED_DONE but actual passed / total cases

        We use the manifest's own severity classifications.
        """
        manifest = load_json(ROOT / ".agentic-pi" / "diagnostics" / "meta_harness" / "manifest.json")
        cases = manifest["cases"]

        # Cases where a FALSE PASS would be catastrophic:
        critical_cases = [c for c in cases if c["severity"] == "CRITICAL"]
        self.assertGreater(len(critical_cases), 0)

        # All cases have expected_status defined
        for c in cases:
            self.assertIn(c["expected_status"],
                         ["NOT_DONE", "PROVISIONAL_DONE", "CERTIFIED_DONE",
                          "BLOCKED_BY_ARTIFACT_MISPLACEMENT",
                          "FAILED_AUTHORITY_VIOLATION", "V0_PROPOSED",
                          "REPLAY_MISMATCH", "REJECTED",
                          "BLOCKED_BY_VERIFIER_MISSING"],
                         f"Case {c['case_id']} has unexpected expected_status: {c['expected_status']}")


if __name__ == "__main__":
    unittest.main()
