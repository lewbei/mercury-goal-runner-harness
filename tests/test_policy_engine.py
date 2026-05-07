import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_DIR = ROOT / ".agentic-pi" / "diagnostics" / "provenance_gate"
RUN_ROOT = ROOT / ".agentic-runs"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def validate(instance, schema_name):
    validator = load_module(
        "validate_schema_for_policy_tests",
        ROOT / ".agentic-pi" / "validators" / "validate_schema.py",
    )
    schema = validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
    return validator.validate(instance, schema)


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def read_final_status(path: Path) -> str:
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    return first_line.removeprefix("# Final Status: ").strip()


class PolicyEngineTests(unittest.TestCase):
    def setUp(self):
        self.created_run_dirs = []

    def tearDown(self):
        for run_dir in self.created_run_dirs:
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def copy_case(self, case_name: str, run_id: str = None) -> Path:
        run_id = run_id or f"test_{case_name}"
        source_dir = DIAGNOSTIC_DIR / case_name
        run_dir = RUN_ROOT / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        shutil.copytree(source_dir, run_dir)
        self.created_run_dirs.append(run_dir)
        if run_id != f"test_{case_name}":
            self.rewrite_run_id(run_dir, run_id)
        return run_dir

    def rewrite_run_id(self, run_dir: Path, run_id: str):
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

    def certify(self, run_dir: Path):
        return run_python(".agentic-pi/validators/certify_run.py", str(run_dir))

    def assert_certification_status(self, run_dir: Path, expected_status: str, result):
        final_status = read_final_status(run_dir / "final_status.md")
        certification = load_json(run_dir / "certification.json")
        decision = load_json(run_dir / "policy_decision.json")

        self.assertEqual(final_status, expected_status, result.stdout)
        self.assertEqual(certification["status"], expected_status, result.stdout)
        self.assertEqual(decision["status"], expected_status, result.stdout)
        self.assertEqual(validate(decision, "policy_decision.schema.json"), [])

    def test_p0_cannot_certify(self):
        run_dir = self.copy_case("case_p0_self_test")

        result = self.certify(run_dir)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_certification_status(run_dir, "PROVISIONAL_DONE", result)
        decision = load_json(run_dir / "policy_decision.json")
        self.assertIn("P0 cannot certify DONE alone", decision["reason"])
        self.assertEqual(decision["certifying_artifacts"], [])
        self.assertEqual(decision["provisional_artifacts"], ["V.P0_SELF"])

    def test_p1_cannot_certify_alone(self):
        run_dir = self.copy_case("case_p1_existing_test")

        result = self.certify(run_dir)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_certification_status(run_dir, "PROVISIONAL_DONE", result)
        decision = load_json(run_dir / "policy_decision.json")
        self.assertIn("P1 is provisional by default", decision["reason"])
        self.assertEqual(decision["certifying_artifacts"], [])
        self.assertEqual(decision["provisional_artifacts"], ["V.P1_EXISTING"])

    def test_p2_strong_certifies(self):
        run_dir = self.copy_case("case_p2_independent_test")

        result = self.certify(run_dir)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_certification_status(run_dir, "CERTIFIED_DONE", result)
        decision = load_json(run_dir / "policy_decision.json")
        self.assertIn("P2", decision["reason"])
        self.assertIn("certifying strength", decision["reason"])
        self.assertEqual(decision["certifying_artifacts"], ["V.P2_INDEPENDENT"])

    def test_missing_verifier_blocks(self):
        run_dir = self.copy_case("case_missing_verifier")

        result = self.certify(run_dir)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assert_certification_status(run_dir, "NOT_DONE", result)
        decision = load_json(run_dir / "policy_decision.json")
        self.assertIn("No verifier artifacts found", decision["reason"])

    def test_p2_weak_strength_does_not_certify(self):
        run_dir = self.copy_case("case_p2_independent_test", "test_policy_p2_weak")
        old_artifact_path = run_dir / "verifier_artifacts" / "V.P2_INDEPENDENT.json"
        artifact = load_json(old_artifact_path)
        artifact["artifact_id"] = "V.P2_WEAK"
        artifact["assertion_count"] = 0
        weak_artifact_path = run_dir / "verifier_artifacts" / "V.P2_WEAK.json"
        write_json(weak_artifact_path, artifact)
        old_artifact_path.unlink()

        result = self.certify(run_dir)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_certification_status(run_dir, "PROVISIONAL_DONE", result)
        decision = load_json(run_dir / "policy_decision.json")
        self.assertNotEqual(decision["status"], "CERTIFIED_DONE")
        self.assertIn("verifier strength is insufficient", decision["reason"])
        self.assertEqual(decision["certifying_artifacts"], [])
        self.assertEqual(decision["provisional_artifacts"], ["V.P2_WEAK"])

    def test_self_generated_only_conflicts_with_required_p2(self):
        run_dir = self.copy_case(
            "case_p2_independent_test",
            "test_policy_self_generated_only_conflict",
        )
        contract_path = run_dir / "verifier_contract.json"
        contract = load_json(contract_path)
        contract["allow_self_generated_only"] = True
        write_json(contract_path, contract)

        result = self.certify(run_dir)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assert_certification_status(run_dir, "NOT_DONE", result)
        decision = load_json(run_dir / "policy_decision.json")
        self.assertIn("allow_self_generated_only must be false", decision["reason"])

    def test_policy_decision_schema_rejects_unknown_field(self):
        run_dir = self.copy_case("case_p2_independent_test")
        result = self.certify(run_dir)
        self.assertEqual(result.returncode, 0, result.stdout)

        decision = load_json(run_dir / "policy_decision.json")
        decision["unexpected"] = True
        errors = validate(decision, "policy_decision.schema.json")

        self.assertTrue(any("unexpected field unexpected" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
