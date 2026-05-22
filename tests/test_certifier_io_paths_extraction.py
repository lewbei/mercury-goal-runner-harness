import ast
import hashlib
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
PROVENANCE_ROOT = ROOT / ".agentic-pi" / "diagnostics" / "provenance_gate"
DOC = ROOT / "docs" / "CERTIFIER_IO_PATHS_EXTRACTION_V1.md"
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


class CertifierIoPathsExtractionTests(unittest.TestCase):
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

    def test_certify_run_imports_io_and_path_helpers(self):
        certify_run = load_module("certify_run_for_io_path_extraction_test", VALIDATORS_DIR / "certify_run.py")
        self.assertEqual(certify_run.load_json.__module__, "certifier_io")
        self.assertEqual(certify_run.sha256_file.__module__, "certifier_io")
        self.assertEqual(certify_run.write_json.__module__, "certifier_io")
        self.assertEqual(certify_run.load_local_module.__module__, "certifier_io")
        self.assertEqual(certify_run.validate_with_schema.__module__, "certifier_io")
        self.assertEqual(certify_run.resolve_run_path.__module__, "certifier_paths")
        self.assertEqual(certify_run.run_relative.__module__, "certifier_paths")
        self.assertEqual(certify_run.find_output.__module__, "certifier_paths")
        self.assertEqual(certify_run.non_empty_string_list.__module__, "certifier_paths")
        self.assertIn("final_status.json", certify_run.PROTECTED_NAMES)
        self.assertIn("verifier_artifacts/", certify_run.PROTECTED_PREFIXES)

    def test_moved_helpers_are_not_redefined_inside_certify_run(self):
        tree = ast.parse((VALIDATORS_DIR / "certify_run.py").read_text(encoding="utf-8"))
        defined_functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        moved_functions = {
            "load_json",
            "sha256_file",
            "write_json",
            "load_local_module",
            "schema_path",
            "validate_with_schema",
            "resolve_run_path",
            "run_relative",
            "output_candidates",
            "find_output",
            "non_empty_string_list",
        }
        self.assertFalse(defined_functions & moved_functions)

    def test_io_helpers_preserve_json_hash_and_schema_behavior(self):
        io_helpers = load_module("certifier_io_for_extraction_test", VALIDATORS_DIR / "certifier_io.py")
        run_dir = RUN_ROOT / "test_certifier_io_helper_extraction"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)
        self.created_run_dirs.append(run_dir)
        sample = {"message": "hello", "unicode": "Mercury π"}
        sample_path = run_dir / "sample.json"

        io_helpers.write_json(sample_path, sample)

        self.assertEqual(io_helpers.load_json(sample_path), sample)
        expected_hash = hashlib.sha256(sample_path.read_bytes()).hexdigest()
        self.assertEqual(io_helpers.sha256_file(sample_path), expected_hash)
        self.assertEqual(io_helpers.schema_path("final_status.schema.json").name, "final_status.schema.json")
        failed = []
        io_helpers.validate_with_schema({"schema_version": "bad"}, "final_status.schema.json", "sample", failed)
        self.assertTrue(any(item.startswith("sample schema validation failed:") for item in failed))

    def test_path_helpers_preserve_run_local_resolution_and_protected_constants(self):
        path_helpers = load_module("certifier_paths_for_extraction_test", VALIDATORS_DIR / "certifier_paths.py")
        run_dir = RUN_ROOT / "test_certifier_path_helper_extraction"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        artifact_dir = run_dir / "artifacts"
        artifact_dir.mkdir(parents=True)
        output_path = artifact_dir / "output.txt"
        output_path.write_text("ok\n", encoding="utf-8")
        self.created_run_dirs.append(run_dir)

        resolved = path_helpers.resolve_run_path(run_dir, "artifacts/output.txt")
        self.assertEqual(resolved, output_path.resolve())
        self.assertEqual(path_helpers.run_relative(run_dir, resolved), "artifacts/output.txt")
        self.assertEqual(path_helpers.find_output(run_dir, "artifacts/output.txt"), output_path.resolve())
        self.assertIsNone(path_helpers.find_output(run_dir, "artifacts/missing.txt"))
        self.assertTrue(path_helpers.non_empty_string_list(["artifacts/output.txt"]))
        self.assertFalse(path_helpers.non_empty_string_list([""]))
        self.assertIn("policy_decision.json", path_helpers.PROTECTED_NAMES)
        self.assertIn("verifier_strength_reports/", path_helpers.PROTECTED_PREFIXES)
        with self.assertRaisesRegex(ValueError, "path escapes run folder"):
            path_helpers.resolve_run_path(run_dir, "../outside.txt")
        with self.assertRaisesRegex(ValueError, "absolute path is not allowed"):
            path_helpers.resolve_run_path(run_dir, str(ROOT.resolve()))

    def test_certifier_still_runs_with_extracted_helpers(self):
        run_dir = self.copy_case(
            PROVENANCE_ROOT / "case_missing_verifier",
            "golden_io_paths_missing_verifier",
        )

        result = run_python(".agentic-pi/validators/certify_run.py", str(run_dir))

        self.assertNotEqual(result.returncode, 0, result.stdout)
        final_status = load_json(run_dir / "final_status.json")
        certification = load_json(run_dir / "certification.json")
        policy = load_json(run_dir / "policy_decision.json")
        self.assertEqual(policy["status"], "NOT_DONE")
        self.assertEqual(certification["status"], "NOT_DONE")
        self.assertEqual(final_status["status"], "NOT_DONE")
        self.assertEqual(final_status["status_source"], "certification.json")

    def test_doc_and_proof_matrix_track_extraction_boundary(self):
        doc = DOC.read_text(encoding="utf-8")
        for phrase in [
            "behavior-preserving helper extraction",
            "certifier_io.py",
            "certifier_paths.py",
            "does not change the policy/certifier authority chain",
            "Golden behavior tests remain",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, doc)

        matrix = PROOF_MATRIX.read_text(encoding="utf-8")
        self.assertIn('"claim_id": "certifier_io_paths_extraction"', matrix)
        self.assertIn("tests/test_certifier_io_paths_extraction.py", matrix)
        self.assertIn("pure IO and run-path helper extraction", matrix)


if __name__ == "__main__":
    unittest.main()
