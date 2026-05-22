import ast
import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATORS_DIR = ROOT / ".agentic-pi" / "validators"
RUNTIME_DIR = ROOT / ".agentic-pi" / "runtime"
RUN_ROOT = ROOT / ".agentic-runs"
EVAL_ROOT = ROOT / ".agentic-pi" / "diagnostics" / "evaluation" / "cases"
DOC = ROOT / "docs" / "CERTIFIER_ARTIFACT_COMMAND_EXTRACTION_V1.md"
PROOF_MATRIX = ROOT / ".agentic-pi" / "proof_matrix" / "proof_matrix.json"


def load_module(name: str, path: Path):
    for module_dir in (VALIDATORS_DIR, RUNTIME_DIR):
        module_dir_text = str(module_dir)
        if module_dir_text not in sys.path:
            sys.path.insert(0, module_dir_text)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


class CertifierArtifactCommandExtractionTests(unittest.TestCase):
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
        for json_path in [
            run_dir / "goal_contract.json",
            run_dir / "verifier_contract.json",
            *sorted((run_dir / "step_logs").glob("*.json")),
            *sorted((run_dir / "verifier_artifacts").glob("*.json")),
        ]:
            if json_path.exists():
                obj = load_json(json_path)
                obj["run_id"] = run_id
                write_json(json_path, obj)
        return run_dir

    def ensure_validator_certified(self, run_dir: Path):
        verifier_dir = run_dir / "verifier_artifacts"
        if not (verifier_dir.is_dir() and any(verifier_dir.glob("*.json"))):
            return
        validator_result = run_python(".agentic-pi/validators/validator_factory.py", str(run_dir))
        self.assertEqual(validator_result.returncode, 0, validator_result.stdout)
        self.assertTrue((run_dir / "validator_certification.json").is_file(), validator_result.stdout)

    def test_certify_run_imports_command_helpers_but_keeps_verifier_logging(self):
        certify_run = load_module("certify_run_for_artifact_command_extraction", VALIDATORS_DIR / "certify_run.py")
        self.assertEqual(certify_run.split_artifact_command.__module__, "certifier_artifact_commands")
        self.assertEqual(certify_run.validate_artifact_command_allowlist.__module__, "certifier_artifact_commands")
        self.assertEqual(certify_run.run_artifact_command_test.__module__, "certifier_artifact_commands")
        self.assertEqual(certify_run.log_artifact_test_verifier.__module__, "certify_run_for_artifact_command_extraction")

    def test_moved_command_helpers_are_not_redefined_inside_certify_run(self):
        tree = ast.parse((VALIDATORS_DIR / "certify_run.py").read_text(encoding="utf-8"))
        defined_functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertFalse(
            defined_functions
            & {
                "split_artifact_command",
                "validate_artifact_command_allowlist",
                "run_artifact_command_test",
            }
        )
        self.assertIn("log_artifact_test_verifier", defined_functions)

    def test_artifact_command_module_accepts_safe_run_relative_python_script(self):
        run_dir = self.copy_case(EVAL_ROOT / "p2_strong", "golden_artcmd_safe_script")
        commands = load_module("certifier_artifact_commands_positive", VALIDATORS_DIR / "certifier_artifact_commands.py")
        case = load_json(run_dir / "case.json")
        passed = []
        failed = []

        ok = commands.run_artifact_command_test(run_dir, case["artifact_tests"][0], passed, failed)

        self.assertTrue(ok, failed)
        self.assertEqual(failed, [])
        self.assertIn("artifact_test OUTPUT_BEHAVIOR passed", passed)

    def test_artifact_command_module_preserves_allowlist_rejections(self):
        run_dir = self.copy_case(EVAL_ROOT / "p2_strong", "golden_artcmd_rejections")
        commands = load_module("certifier_artifact_commands_negative", VALIDATORS_DIR / "certifier_artifact_commands.py")
        unsafe_commands = [
            ("python artifacts/check_output.py && python artifacts/check_output.py", "shell"),
            ("python -c print(1)", "options"),
            ("python -m unittest", "options"),
            ("python ../outside.py", "escapes"),
            ("python artifacts/check_output.py final_status.json", "protected status artifact"),
            ("python verifier_artifacts/V.P2_STRONG.json", "protected"),
            ("node artifacts/check_output.py", "not allowlisted"),
        ]

        for cmd, reason_fragment in unsafe_commands:
            with self.subTest(cmd=cmd):
                parts = commands.split_artifact_command(cmd)
                allowed, normalized, reasons = commands.validate_artifact_command_allowlist(run_dir, cmd, parts)
                self.assertFalse(allowed)
                self.assertEqual(normalized, [])
                self.assertIn(reason_fragment, "\n".join(reasons))

    def test_unsafe_artifact_command_still_blocks_certifier_run(self):
        run_dir = self.copy_case(EVAL_ROOT / "p2_strong", "golden_artcmd_blocks_certifier")
        self.ensure_validator_certified(run_dir)
        goal = load_json(run_dir / "goal_contract.json")
        goal["artifact_tests"] = [
            {
                "test_id": "SHELL_CHAIN",
                "type": "command",
                "cmd": "python artifacts/check_output.py && python artifacts/check_output.py",
                "expect_exit_code": 0,
            }
        ]
        write_json(run_dir / "goal_contract.json", goal)

        result = run_python(".agentic-pi/validators/certify_run.py", str(run_dir))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        certification = load_json(run_dir / "certification.json")
        final_status = load_json(run_dir / "final_status.json")
        self.assertEqual(certification["status"], "NOT_DONE", result.stdout)
        self.assertEqual(final_status["status"], "NOT_DONE", result.stdout)
        self.assertIn("command rejected by allowlist", "\n".join(certification["failed_checks"]))

    def test_doc_and_proof_matrix_track_extraction_boundary(self):
        doc = DOC.read_text(encoding="utf-8")
        for phrase in [
            "behavior-preserving helper extraction",
            "certifier_artifact_commands.py",
            "log_artifact_test_verifier",
            "does not move",
            "python <run-relative-script.py> [safe args]",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, doc)

        matrix = PROOF_MATRIX.read_text(encoding="utf-8")
        self.assertIn('"claim_id": "certifier_artifact_command_extraction"', matrix)
        self.assertIn("tests/test_certifier_artifact_command_extraction.py", matrix)
        self.assertIn("artifact command-test helper extraction", matrix)


if __name__ == "__main__":
    unittest.main()
