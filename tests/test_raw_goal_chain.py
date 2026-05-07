import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / ".agentic-runs"


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


class RawGoalChainTests(unittest.TestCase):
    def tearDown(self):
        for run_dir in RUN_ROOT.glob("pi_smoke_raw_goal_*"):
            shutil.rmtree(run_dir)

    def run_case(self, suffix: str, mode: str, expected_status: str):
        run_id = f"pi_smoke_raw_goal_{suffix}"
        run_dir = RUN_ROOT / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)

        compile_result = run_python(
            ".agentic-pi/runtime/pi_cli.py",
            "goal-compile",
            run_id,
            "--goal",
            "Create README.md explaining the harness",
            "--mode",
            mode,
        )
        self.assertEqual(compile_result.returncode, 0, compile_result.stdout)
        self.assertEqual(load_json(run_dir / "goal_contract.json")["run_id"], run_id)

        run_result = run_python(
            ".agentic-pi/runtime/pi_cli.py",
            "goal-run",
            run_id,
            "--skip-memory-update",
        )
        if expected_status in {"NOT_DONE", "DONE_FAIL"}:
            self.assertNotEqual(run_result.returncode, 0, run_result.stdout)
        else:
            self.assertEqual(run_result.returncode, 0, run_result.stdout)

        certification = load_json(run_dir / "certification.json")
        self.assertEqual(certification["status"], expected_status)
        self.assertTrue((run_dir / "README.md").is_file())
        return run_dir

    def test_raw_simple_legacy_reaches_done_pass(self):
        run_dir = self.run_case("legacy", "legacy", "DONE_PASS")

        status = run_python(".agentic-pi/runtime/pi_cli.py", "goal-status", run_dir.name, "--fail-on-missing")
        self.assertEqual(status.returncode, 0, status.stdout)
        self.assertIn("SKIPPED_LEGACY", status.stdout)

    def test_raw_p2_provenance_reaches_certified_done(self):
        run_dir = self.run_case("p2", "p2", "CERTIFIED_DONE")

        policy = load_json(run_dir / "policy_decision.json")
        self.assertEqual(policy["status"], "CERTIFIED_DONE")
        self.assertEqual(policy["certifying_artifacts"], ["V.RAW_GOAL_P2"])

    def test_raw_missing_verifier_is_not_done(self):
        run_dir = self.run_case("missing_verifier", "missing_verifier", "NOT_DONE")

        policy = load_json(run_dir / "policy_decision.json")
        self.assertEqual(policy["status"], "NOT_DONE")
        self.assertFalse(policy["certifying_artifacts"])

    def test_v11_doc_locks_raw_goal_boundary(self):
        doc = (ROOT / "docs" / "V1_1_RAW_GOAL_CHAIN_PROOF.md").read_text(encoding="utf-8")

        self.assertIn("RAW GOAL CHAIN PROOF IMPLEMENTED", doc)
        self.assertIn("raw goal -> goal_contract.json -> full harness run -> certifier status", doc)
        self.assertIn("general natural-language goal compilation", doc)
        self.assertIn("certify_run.py` / `policy_engine.py` decide final status", doc)


if __name__ == "__main__":
    unittest.main()
