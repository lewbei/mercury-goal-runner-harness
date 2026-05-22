import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / ".agentic-runs"
PROVENANCE_ROOT = ROOT / ".agentic-pi" / "diagnostics" / "provenance_gate"
EVAL_ROOT = ROOT / ".agentic-pi" / "diagnostics" / "evaluation" / "cases"
DOC = ROOT / "docs" / "CERTIFIER_GOLDEN_BEHAVIOR_LOCK_V1.md"
PROOF_MATRIX = ROOT / ".agentic-pi" / "proof_matrix" / "proof_matrix.json"


PROVENANCE_CASES = [
    (PROVENANCE_ROOT / "case_missing_verifier", "golden_missing_verifier", "NOT_DONE", "NOT_DONE"),
    (PROVENANCE_ROOT / "case_p0_self_test", "golden_p0_self_test", "PROVISIONAL_DONE", "PROVISIONAL_DONE"),
    (PROVENANCE_ROOT / "case_p1_existing_test", "golden_p1_existing_test", "PROVISIONAL_DONE", "PROVISIONAL_DONE"),
    (PROVENANCE_ROOT / "case_p2_independent_test", "golden_p2_independent", "CERTIFIED_DONE", "CERTIFIED_DONE"),
    (EVAL_ROOT / "p2_weak", "golden_p2_weak", "PROVISIONAL_DONE", "PROVISIONAL_DONE"),
]


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_markdown_status(path: Path) -> str:
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    return first_line.removeprefix("# Final Status: ").strip()


class CertifierGoldenBehaviorLockTests(unittest.TestCase):
    def setUp(self):
        self.created_run_dirs = []

    def tearDown(self):
        for run_dir in self.created_run_dirs:
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def copy_case(self, source_dir: Path, run_id: str) -> Path:
        run_dir = RUN_ROOT / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        shutil.copytree(source_dir, run_dir)
        self.created_run_dirs.append(run_dir)
        self.rewrite_run_id(run_dir, run_id)
        return run_dir

    def rewrite_run_id(self, run_dir: Path, run_id: str):
        json_paths = [
            run_dir / "goal_contract.json",
            run_dir / "verifier_contract.json",
            *sorted((run_dir / "step_logs").glob("*.json")),
            *sorted((run_dir / "verifier_artifacts").glob("*.json")),
        ]
        for json_path in json_paths:
            if json_path.exists():
                obj = load_json(json_path)
                obj["run_id"] = run_id
                write_json(json_path, obj)

    def ensure_validator_certified(self, run_dir: Path):
        verifier_dir = run_dir / "verifier_artifacts"
        if not (run_dir / "verifier_contract.json").is_file():
            return
        if not (verifier_dir.is_dir() and any(verifier_dir.glob("*.json"))):
            return
        validator_result = run_python(".agentic-pi/validators/validator_factory.py", str(run_dir))
        self.assertEqual(validator_result.returncode, 0, validator_result.stdout)
        self.assertTrue((run_dir / "validator_certification.json").is_file(), validator_result.stdout)

    def certify(self, run_dir: Path, certify_validator: bool = True):
        if certify_validator:
            self.ensure_validator_certified(run_dir)
        return run_python(".agentic-pi/validators/certify_run.py", str(run_dir))

    def test_provenance_status_matrix_is_locked(self):
        for source_dir, run_id, expected_status, expected_policy_status in PROVENANCE_CASES:
            with self.subTest(case=source_dir.name):
                run_dir = self.copy_case(source_dir, run_id)
                result = self.certify(run_dir)

                final_status = load_json(run_dir / "final_status.json")
                certification = load_json(run_dir / "certification.json")
                policy = load_json(run_dir / "policy_decision.json")

                self.assertEqual(final_status["status"], expected_status, result.stdout)
                self.assertEqual(certification["status"], expected_status, result.stdout)
                self.assertEqual(policy["status"], expected_policy_status, result.stdout)
                self.assertEqual(final_status["final_status_authority"], "certifier_only")
                self.assertFalse(final_status["can_certify_done"])
                self.assertEqual(final_status["certification_path"], "certification.json")
                self.assertEqual(final_status["policy_decision_path"], "policy_decision.json")
                if expected_status == "NOT_DONE":
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertEqual(final_status["status_source"], "certification.json")
                else:
                    self.assertEqual(result.returncode, 0, result.stdout)
                    self.assertEqual(final_status["status_source"], "policy_decision.json")

    def test_late_replay_gate_downgrades_after_policy_certified_done(self):
        run_dir = self.copy_case(
            PROVENANCE_ROOT / "case_p2_independent_test",
            "golden_replay_gate_downgrade",
        )
        write_json(
            run_dir / "replay_report.json",
            {
                "verdict": "REPLAY_MISMATCH",
                "checks": {
                    "artifact_hash": {
                        "passed": False,
                        "detail": "golden lock forced mismatch",
                    }
                },
            },
        )

        result = self.certify(run_dir)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        policy = load_json(run_dir / "policy_decision.json")
        certification = load_json(run_dir / "certification.json")
        final_status = load_json(run_dir / "final_status.json")
        self.assertEqual(policy["status"], "CERTIFIED_DONE", result.stdout)
        self.assertEqual(certification["status"], "NOT_DONE", result.stdout)
        self.assertEqual(final_status["status"], "NOT_DONE", result.stdout)
        self.assertEqual(final_status["status_source"], "certification.json")
        self.assertIn("REPLAY_MISMATCH", "\n".join(certification["failed_checks"]))

    def test_artifact_command_allowlist_golden_rejections(self):
        run_dir = self.copy_case(EVAL_ROOT / "p2_strong", "golden_allowlist_surface")
        certifier = load_module(
            "certify_run_for_golden_allowlist",
            ROOT / ".agentic-pi" / "validators" / "certify_run.py",
        )
        positive_cmd = "python artifacts/check_output.py"
        positive_parts = certifier.split_artifact_command(positive_cmd)
        allowed, normalized, reasons = certifier.validate_artifact_command_allowlist(
            run_dir, positive_cmd, positive_parts
        )
        self.assertTrue(allowed, reasons)
        self.assertEqual(normalized[0], sys.executable)

        unsafe_commands = [
            ("python artifacts/check_output.py && python artifacts/check_output.py", "shell"),
            ("python -c print(1)", "options"),
            ("python -m unittest", "options"),
            ("python ../outside.py", "escapes"),
            ("python artifacts/check_output.py final_status.json", "protected status artifact"),
            ("node artifacts/check_output.py", "not allowlisted"),
        ]
        for cmd, reason_fragment in unsafe_commands:
            with self.subTest(cmd=cmd):
                parts = certifier.split_artifact_command(cmd)
                allowed, normalized, reasons = certifier.validate_artifact_command_allowlist(run_dir, cmd, parts)
                self.assertFalse(allowed)
                self.assertEqual(normalized, [])
                self.assertIn(reason_fragment, "\n".join(reasons))

    def test_worker_touched_protected_paths_block_certification(self):
        run_dir = self.copy_case(
            PROVENANCE_ROOT / "case_p2_independent_test",
            "golden_worker_touched_protected_paths",
        )
        self.ensure_validator_certified(run_dir)
        step_path = run_dir / "step_logs" / "001.json"
        step = load_json(step_path)
        step["files_touched"] = [
            *step["files_touched"],
            "final_status.json",
            "verifier_artifacts/V.P2_INDEPENDENT.json",
        ]
        write_json(step_path, step)

        result = self.certify(run_dir, certify_validator=False)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        final_status = load_json(run_dir / "final_status.json")
        certification = load_json(run_dir / "certification.json")
        failures = "\n".join(certification["failed_checks"])
        self.assertEqual(final_status["status"], "NOT_DONE", result.stdout)
        self.assertIn("reports Worker touched protected file", failures)
        self.assertIn("reports Worker touched protected provenance path", failures)

    def test_legacy_compatibility_status_mapping_is_locked(self):
        pass_dir = self.copy_case(EVAL_ROOT / "p2_strong", "golden_legacy_pass")
        (pass_dir / "verifier_contract.json").unlink()
        pass_result = self.certify(pass_dir)
        pass_status = load_json(pass_dir / "final_status.json")
        pass_certification = load_json(pass_dir / "certification.json")
        self.assertEqual(pass_result.returncode, 0, pass_result.stdout)
        self.assertEqual(pass_status["status"], "DONE_PASS")
        self.assertEqual(pass_certification["status"], "DONE_PASS")
        self.assertEqual(pass_status["status_source"], "certification.json")
        self.assertFalse((pass_dir / "policy_decision.json").exists())

        fail_dir = self.copy_case(PROVENANCE_ROOT / "case_p2_independent_test", "golden_legacy_fail")
        (fail_dir / "verifier_contract.json").unlink()
        (fail_dir / "artifacts" / "output.txt").unlink()
        fail_result = self.certify(fail_dir)
        fail_status = load_json(fail_dir / "final_status.json")
        fail_certification = load_json(fail_dir / "certification.json")
        self.assertNotEqual(fail_result.returncode, 0, fail_result.stdout)
        self.assertEqual(fail_status["status"], "DONE_FAIL")
        self.assertEqual(fail_certification["status"], "DONE_FAIL")
        self.assertEqual(fail_status["status_source"], "certification.json")
        self.assertFalse((fail_dir / "policy_decision.json").exists())

    def test_markdown_cannot_upgrade_json_authority(self):
        run_dir = self.copy_case(PROVENANCE_ROOT / "case_missing_verifier", "golden_markdown_non_authority")
        result = self.certify(run_dir)
        self.assertNotEqual(result.returncode, 0, result.stdout)

        markdown_path = run_dir / "final_status.md"
        markdown_path.write_text(
            markdown_path.read_text(encoding="utf-8").replace(
                "# Final Status: NOT_DONE",
                "# Final Status: CERTIFIED_DONE",
            ),
            encoding="utf-8",
        )

        final_status_validator = load_module(
            "validate_final_status_for_golden_lock",
            ROOT / ".agentic-pi" / "validators" / "validate_final_status.py",
        )
        self.assertEqual(final_status_validator.authoritative_status(run_dir), "NOT_DONE")
        self.assertEqual(load_json(run_dir / "final_status.json")["status"], "NOT_DONE")
        self.assertEqual(read_markdown_status(run_dir / "final_status.md"), "CERTIFIED_DONE")

    def test_doc_and_proof_matrix_track_golden_lock_boundary(self):
        doc = DOC.read_text(encoding="utf-8")
        required_doc_phrases = [
            "pre-refactor behavior lock",
            "does not modularize `certify_run.py`",
            "P2 weak verifier evidence -> PROVISIONAL_DONE",
            "policy says CERTIFIED_DONE but replay gate fails -> final NOT_DONE from certification.json",
            "final_status.md cannot upgrade final_status.json authority",
            "bounded regression evidence",
        ]
        for phrase in required_doc_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, doc)

        matrix = PROOF_MATRIX.read_text(encoding="utf-8")
        self.assertIn('"claim_id": "certifier_golden_behavior_lock"', matrix)
        self.assertIn("tests/test_certifier_golden_behavior_lock.py", matrix)
        self.assertIn("bounded deterministic certifier behavior", matrix)


if __name__ == "__main__":
    unittest.main()
