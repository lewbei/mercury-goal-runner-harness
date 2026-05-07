import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_DIR = ROOT / ".agentic-pi" / "diagnostics" / "provenance_gate"
RUN_ROOT = ROOT / ".agentic-runs"

EXPECTED_CASES = {
    "case_missing_verifier": {
        "status": "NOT_DONE",
        "verifier_artifact": None,
    },
    "case_p0_self_test": {
        "status": "PROVISIONAL_DONE",
        "verifier_artifact": "V.P0_SELF.json",
    },
    "case_p1_existing_test": {
        "status": "PROVISIONAL_DONE",
        "verifier_artifact": "V.P1_EXISTING.json",
    },
    "case_p2_independent_test": {
        "status": "CERTIFIED_DONE",
        "verifier_artifact": "V.P2_INDEPENDENT.json",
    },
}

REQUIRED_FIXTURE_FILES = [
    "goal_contract.json",
    "verifier_contract.json",
    "step_logs/001.json",
    "trace.jsonl",
    "artifacts/output.txt",
]


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


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


class ProvenanceGateDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.created_run_dirs = []

    def tearDown(self):
        for run_dir in self.created_run_dirs:
            if run_dir.exists():
                shutil.rmtree(run_dir)

    def case_dirs(self):
        return sorted(path for path in DIAGNOSTIC_DIR.glob("case_*") if path.is_dir())

    def copy_fixture_to_run(self, case_name: str) -> Path:
        source_dir = DIAGNOSTIC_DIR / case_name
        run_dir = RUN_ROOT / f"test_{case_name}"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        shutil.copytree(source_dir, run_dir)
        self.created_run_dirs.append(run_dir)
        return run_dir

    def certify(self, run_dir: Path):
        return run_python(".agentic-pi/validators/certify_run.py", str(run_dir))

    def test_diagnostic_case_inventory_is_exact(self):
        self.assertEqual(
            [path.name for path in self.case_dirs()],
            sorted(EXPECTED_CASES),
        )

    def test_diagnostic_fixtures_are_copy_ready_run_folders(self):
        for case_name, expected in EXPECTED_CASES.items():
            with self.subTest(case=case_name):
                case_dir = DIAGNOSTIC_DIR / case_name
                for rel_path in REQUIRED_FIXTURE_FILES:
                    self.assertTrue((case_dir / rel_path).exists(), rel_path)

                goal_contract = load_json(case_dir / "goal_contract.json")
                verifier_contract = load_json(case_dir / "verifier_contract.json")
                step_log = load_json(case_dir / "step_logs" / "001.json")
                expected_run_id = f"test_{case_name}"

                self.assertEqual(goal_contract["run_id"], expected_run_id)
                self.assertEqual(verifier_contract["run_id"], expected_run_id)
                self.assertEqual(step_log["run_id"], expected_run_id)
                self.assertEqual(goal_contract["final_outputs"], ["artifacts/output.txt"])
                self.assertEqual(verifier_contract["target_artifacts"], ["artifacts/output.txt"])

                verifier_artifact = expected["verifier_artifact"]
                verifier_dir = case_dir / "verifier_artifacts"
                if verifier_artifact is None:
                    self.assertFalse(verifier_dir.exists())
                else:
                    self.assertTrue((verifier_dir / verifier_artifact).exists())

    def test_diagnostic_cases_match_expected_final_statuses(self):
        for case_name, expected in EXPECTED_CASES.items():
            with self.subTest(case=case_name):
                run_dir = self.copy_fixture_to_run(case_name)
                result = self.certify(run_dir)

                final_status_path = run_dir / "final_status.md"
                certification_path = run_dir / "certification.json"
                self.assertTrue(final_status_path.exists(), result.stdout)
                self.assertTrue(certification_path.exists(), result.stdout)

                final_status = read_final_status(final_status_path)
                certification = load_json(certification_path)

                self.assertEqual(final_status, expected["status"], result.stdout)
                self.assertEqual(certification["status"], expected["status"], result.stdout)

                if expected["status"] == "NOT_DONE":
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                else:
                    self.assertEqual(result.returncode, 0, result.stdout)

    def test_v033_doc_locks_diagnostic_boundary(self):
        doc = (ROOT / "docs" / "V0_3_3_PROVENANCE_GATE_DIAGNOSTICS.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Self-generated or low-authority verifier evidence cannot certify DONE alone.", doc)
        self.assertIn("case_p0_self_test", doc)
        self.assertIn("case_p1_existing_test", doc)
        self.assertIn("case_p2_independent_test", doc)
        self.assertIn("case_missing_verifier", doc)
        self.assertIn("does not add", doc)
        self.assertIn("smell scanner", doc)
        self.assertIn("strength scorer", doc)


if __name__ == "__main__":
    unittest.main()
