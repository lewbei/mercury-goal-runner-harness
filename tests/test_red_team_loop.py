import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
RED_TEAM_PATH = ROOT / ".agentic-pi" / "runtime" / "red_team_loop.py"
VALIDATE_SCHEMA = ROOT / ".agentic-pi" / "validators" / "validate_schema.py"
GOAL_SCHEMA = ROOT / ".agentic-pi" / "schemas" / "goal_contract.schema.json"
HARD_GOAL = ROOT / ".agentic-pi" / "benchmark" / "goals" / "hard_goal.json"


def load_red_team_loop():
    spec = importlib.util.spec_from_file_location("red_team_loop", RED_TEAM_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["red_team_loop"] = module
    spec.loader.exec_module(module)
    return module


class RedTeamLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.red_team_loop = load_red_team_loop()

    def test_legacy_goal_contract_schema_still_accepts_hard_artifact_tests(self):
        result = subprocess.run(
            [sys.executable, str(VALIDATE_SCHEMA), str(GOAL_SCHEMA), str(HARD_GOAL)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("SCHEMA_VALID", result.stdout)

    def test_canonical_red_team_case_inventory_covers_required_families(self):
        cases = self.red_team_loop.canonical_cases()
        self.assertGreaterEqual(len(cases), 20)
        families = {case.family for case in cases}
        for family in [
            "artifact",
            "planning",
            "verifier",
            "policy",
            "pi_report",
            "monitor",
            "memory",
            "command",
            "schema",
        ]:
            self.assertIn(family, families)

    def test_statistical_red_team_loop_meets_stopping_rule(self):
        result = self.red_team_loop.run_red_team(rounds=100, seed_runs=3)
        metrics = result["metrics"]
        self.assertEqual(metrics["case_count"], 300)
        self.assertEqual(metrics["false_certified_done_rate"], 0.0)
        self.assertEqual(metrics["monitor_miss_rate"], 0.0)
        self.assertEqual(metrics["policy_mismatch_escape_rate"], 0.0)
        self.assertEqual(metrics["regression_pass_rate"], 1.0)
        self.assertTrue(metrics["stopping_rule_met"])

    def test_cli_writes_metrics_and_uses_nonzero_exit_when_stopping_rule_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "red_team_metrics.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RED_TEAM_PATH),
                    "--rounds",
                    "20",
                    "--seed-runs",
                    "1",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(data["metrics"]["stopping_rule_met"])
            self.assertEqual(data["metrics"]["false_certified_done_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
