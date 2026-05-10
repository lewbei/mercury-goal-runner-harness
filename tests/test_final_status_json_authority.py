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


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def read_markdown_status(path: Path) -> str:
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    return first_line.removeprefix("# Final Status: ").strip()


class FinalStatusJsonAuthorityTests(unittest.TestCase):
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

    def certify(self, run_dir: Path):
        return run_python(".agentic-pi/validators/certify_run.py", str(run_dir))

    def validate_schema(self, instance: dict, schema_name: str):
        validator = load_module(
            "validate_schema_for_final_status_tests",
            ROOT / ".agentic-pi" / "validators" / "validate_schema.py",
        )
        schema = validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
        return validator.validate(instance, schema)

    def test_final_status_json_written_by_certifier(self):
        run_dir = self.copy_case(
            PROVENANCE_ROOT / "case_p2_independent_test",
            "test_final_status_json_written",
        )

        result = self.certify(run_dir)

        self.assertEqual(result.returncode, 0, result.stdout)
        final_status = load_json(run_dir / "final_status.json")
        certification = load_json(run_dir / "certification.json")
        self.assertEqual(final_status["schema_version"], "final_status_v1")
        self.assertEqual(final_status["status"], "CERTIFIED_DONE")
        self.assertEqual(final_status["status"], certification["status"])
        self.assertEqual(final_status["final_status_authority"], "certifier_only")
        self.assertFalse(final_status["can_certify_done"])
        self.assertEqual(self.validate_schema(final_status, "final_status.schema.json"), [])

    def test_final_status_md_rendered_from_json(self):
        run_dir = self.copy_case(
            PROVENANCE_ROOT / "case_p2_independent_test",
            "test_final_status_md_rendered",
        )

        result = self.certify(run_dir)

        self.assertEqual(result.returncode, 0, result.stdout)
        final_status = load_json(run_dir / "final_status.json")
        markdown = (run_dir / "final_status.md").read_text(encoding="utf-8")
        self.assertEqual(read_markdown_status(run_dir / "final_status.md"), final_status["status"])
        self.assertIn("final_status_authority: certifier_only", markdown)
        self.assertIn("can_certify_done: false", markdown)
        self.assertIn("## Passed checks", markdown)
        self.assertIn("## Failed checks", markdown)
        self.assertIn("## Artifact hashes", markdown)

    def test_markdown_cannot_upgrade_json_authority(self):
        run_dir = self.copy_case(
            PROVENANCE_ROOT / "case_missing_verifier",
            "test_markdown_cannot_upgrade_json",
        )

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
            "validate_final_status_for_authority_tests",
            ROOT / ".agentic-pi" / "validators" / "validate_final_status.py",
        )
        self.assertEqual(final_status_validator.authoritative_status(run_dir), "NOT_DONE")
        self.assertEqual(load_json(run_dir / "final_status.json")["status"], "NOT_DONE")
        self.assertEqual(read_markdown_status(run_dir / "final_status.md"), "CERTIFIED_DONE")

    def test_certification_and_final_status_json_agree(self):
        run_dir = self.copy_case(
            PROVENANCE_ROOT / "case_p1_existing_test",
            "test_certification_and_final_status_agree",
        )

        result = self.certify(run_dir)

        self.assertEqual(result.returncode, 0, result.stdout)
        final_status = load_json(run_dir / "final_status.json")
        certification = load_json(run_dir / "certification.json")
        self.assertEqual(final_status["status"], "PROVISIONAL_DONE")
        self.assertEqual(final_status["status"], certification["status"])

    def test_policy_certification_final_status_chain_consistent(self):
        run_dir = self.copy_case(
            PROVENANCE_ROOT / "case_p2_independent_test",
            "test_policy_certification_final_status_chain",
        )

        result = self.certify(run_dir)

        self.assertEqual(result.returncode, 0, result.stdout)
        final_status = load_json(run_dir / "final_status.json")
        certification = load_json(run_dir / "certification.json")
        policy = load_json(run_dir / "policy_decision.json")
        self.assertEqual(policy["status"], "CERTIFIED_DONE")
        self.assertEqual(final_status["status"], policy["status"])
        self.assertEqual(final_status["status"], certification["status"])
        self.assertEqual(final_status["status_source"], "policy_decision.json")
        self.assertEqual(final_status["policy_decision_path"], "policy_decision.json")
        self.assertEqual(final_status["certification_path"], "certification.json")

    def test_legacy_done_pass_done_fail_still_supported(self):
        pass_dir = self.copy_case(
            EVAL_ROOT / "p2_strong",
            "test_legacy_final_status_done_pass",
        )
        pass_dir.joinpath("verifier_contract.json").unlink()
        pass_result = self.certify(pass_dir)

        self.assertEqual(pass_result.returncode, 0, pass_result.stdout)
        pass_status = load_json(pass_dir / "final_status.json")
        pass_certification = load_json(pass_dir / "certification.json")
        self.assertEqual(pass_status["status"], "DONE_PASS")
        self.assertEqual(pass_status["status"], pass_certification["status"])
        self.assertEqual(pass_status["status_source"], "certification.json")

        fail_dir = self.copy_case(
            PROVENANCE_ROOT / "case_p2_independent_test",
            "test_legacy_final_status_done_fail",
        )
        fail_dir.joinpath("verifier_contract.json").unlink()
        fail_dir.joinpath("artifacts", "output.txt").unlink()
        fail_result = self.certify(fail_dir)

        self.assertNotEqual(fail_result.returncode, 0, fail_result.stdout)
        fail_status = load_json(fail_dir / "final_status.json")
        fail_certification = load_json(fail_dir / "certification.json")
        self.assertEqual(fail_status["status"], "DONE_FAIL")
        self.assertEqual(fail_status["status"], fail_certification["status"])
        self.assertEqual(fail_status["status_source"], "certification.json")


if __name__ == "__main__":
    unittest.main()
