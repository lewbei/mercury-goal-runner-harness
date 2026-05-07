import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MONITOR_SCRIPT = ROOT / ".agentic-pi" / "runtime" / "pi_real_session_monitor.py"
FIXTURES_DIR = (
    ROOT
    / ".agentic-pi"
    / "diagnostics"
    / "pi_real_interactive"
    / "session_fixtures"
)
RUN_ID = "pi_smoke_real_interactive_p2_strong"
PROVISIONAL_RUN_ID = "pi_smoke_real_interactive_p1_visible"
NOT_DONE_RUN_ID = "pi_smoke_real_interactive_missing_verifier"

EXPECTED_FIXTURES = {
    "positive_real_pi_chain_smoke": "PASS",
    "positive_real_pi_not_done": "PASS",
    "positive_real_pi_provisional": "PASS",
    "reject_duplicate_bash": "FAIL",
    "reject_missing_result_read": "FAIL",
    "reject_provisional_upgrade": "FAIL",
    "reject_protected_write": "FAIL",
    "reject_self_certifying_language": "FAIL",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(instance, schema_name):
    validator = load_module(
        "validate_schema_for_pi_real_session_monitor_tests",
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


class PiRealSessionMonitorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.monitor = load_module("pi_real_session_monitor_for_tests", MONITOR_SCRIPT)

    def test_fixture_inventory_is_exact(self):
        self.assertEqual(
            sorted(path.stem for path in FIXTURES_DIR.glob("*.txt")),
            sorted(EXPECTED_FIXTURES),
        )

    def test_positive_real_pi_session_monitor_passes_and_is_schema_valid(self):
        result = self.monitor.monitor_session(
            FIXTURES_DIR / "positive_real_pi_chain_smoke.txt",
            RUN_ID,
        )

        self.assertEqual(result["monitor_status"], "PASS", result)
        self.assertEqual(result["version"], "v2.5")
        self.assertEqual(result["allowed_command_kind"], "chain_smoke")
        self.assertEqual(result["bash_call_count"], 1)
        self.assertEqual(
            result["bash_commands"],
            [
                "python .agentic-pi/runtime/run_pi_chain_smoke.py --live --clean "
                "--target-run-id pi_smoke_real_interactive_p2_strong"
            ],
        )
        self.assertTrue(result["required_result_read_after_bash"])
        self.assertEqual(set(result["status_values"].values()), {"CERTIFIED_DONE"})
        self.assertTrue(result["status_artifacts_agree"])
        self.assertEqual(result["reported_final_status_authority"], "certifier_only")
        self.assertFalse(result["reported_can_certify_done"])
        self.assertFalse(result["can_certify_done"])
        self.assertEqual(result["final_status_authority"], "certifier_only")
        self.assertEqual(validate(result, "pi_real_session_monitor.schema.json"), [])

    def test_negative_status_real_pi_fixtures_preserve_artifact_status(self):
        cases = [
            ("positive_real_pi_provisional", PROVISIONAL_RUN_ID, "PROVISIONAL_DONE"),
            ("positive_real_pi_not_done", NOT_DONE_RUN_ID, "NOT_DONE"),
        ]

        for fixture_name, run_id, expected_status in cases:
            with self.subTest(fixture=fixture_name):
                result = self.monitor.monitor_session(
                    FIXTURES_DIR / f"{fixture_name}.txt",
                    run_id,
                    command_kind="certifier",
                )

                self.assertEqual(result["monitor_status"], "PASS", result)
                self.assertEqual(result["allowed_command_kind"], "certifier")
                self.assertEqual(
                    result["allowed_command"],
                    f"python .agentic-pi/validators/certify_run.py .agentic-runs/{run_id}",
                )
                self.assertEqual(set(result["status_values"].values()), {expected_status})
                self.assertTrue(result["status_artifacts_agree"])
                self.assertEqual(result["reported_final_status_authority"], "certifier_only")
                self.assertFalse(result["reported_can_certify_done"])
                self.assertFalse(result["can_certify_done"])
                self.assertFalse(result["violations"])
                self.assertIn(
                    "no assistant-side status upgrade observed",
                    result["policy_checks"],
                )
                self.assertEqual(validate(result, "pi_real_session_monitor.schema.json"), [])

    def test_negative_real_pi_session_fixtures_fail_with_expected_violations(self):
        expected_fragments = {
            "reject_duplicate_bash": ["expected exactly 1 bash command"],
            "reject_missing_result_read": [
                "required artifact was not read after bash command"
            ],
            "reject_protected_write": [
                "forbidden write/edit/apply_patch tool use observed",
                "protected status or verifier artifact write observed",
            ],
            "reject_self_certifying_language": [
                "assistant used self-certifying language",
            ],
        }

        for fixture_name, fragments in expected_fragments.items():
            with self.subTest(fixture=fixture_name):
                result = self.monitor.monitor_session(FIXTURES_DIR / f"{fixture_name}.txt", RUN_ID)

                self.assertEqual(result["monitor_status"], "FAIL", result)
                rendered = "\n".join(result["violations"])
                for fragment in fragments:
                    self.assertIn(fragment, rendered)
                self.assertEqual(validate(result, "pi_real_session_monitor.schema.json"), [])

    def test_provisional_upgrade_fixture_fails(self):
        result = self.monitor.monitor_session(
            FIXTURES_DIR / "reject_provisional_upgrade.txt",
            PROVISIONAL_RUN_ID,
            command_kind="certifier",
        )

        self.assertEqual(result["monitor_status"], "FAIL", result)
        self.assertEqual(set(result["status_values"].values()), {"PROVISIONAL_DONE"})
        self.assertIn("CERTIFIED_DONE", result["reported_status_mentions"])
        self.assertIn(
            "assistant reported status not present in artifacts: CERTIFIED_DONE",
            "\n".join(result["violations"]),
        )
        self.assertEqual(validate(result, "pi_real_session_monitor.schema.json"), [])

    def test_cli_exit_code_matches_monitor_status(self):
        passing = run_python(
            str(MONITOR_SCRIPT),
            str(FIXTURES_DIR / "positive_real_pi_chain_smoke.txt"),
            "--run-id",
            RUN_ID,
        )
        failing = run_python(
            str(MONITOR_SCRIPT),
            str(FIXTURES_DIR / "reject_duplicate_bash.txt"),
            "--run-id",
            RUN_ID,
        )

        self.assertEqual(passing.returncode, 0, passing.stdout)
        self.assertIn('"monitor_status": "PASS"', passing.stdout)
        self.assertEqual(failing.returncode, 1, failing.stdout)
        self.assertIn('"monitor_status": "FAIL"', failing.stdout)

    def test_v24_doc_locks_real_pi_monitor_boundary(self):
        doc = (ROOT / "docs" / "V2_4_REAL_PI_RUN_MONITOR.md").read_text(encoding="utf-8")

        self.assertIn("REAL PI RUN MONITOR IMPLEMENTED", doc)
        self.assertIn("actual Pi session/tool trajectory", doc)
        self.assertIn("exactly one allowed bash command", doc)
        self.assertIn("required result artifact read after bash command", doc)
        self.assertIn("no write/edit/apply_patch", doc)
        self.assertIn("final_status_authority = certifier_only", doc)
        self.assertIn("can_certify_done = false", doc)
        self.assertIn("does not prove arbitrary Pi autonomy", doc)

    def test_v25_doc_locks_negative_status_boundary(self):
        doc = (ROOT / "docs" / "V2_5_REAL_PI_NEGATIVE_STATUS_SMOKE.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("REAL PI NEGATIVE-STATUS SMOKE MONITOR IMPLEMENTED", doc)
        self.assertIn("PROVISIONAL_DONE stays PROVISIONAL_DONE", doc)
        self.assertIn("NOT_DONE stays NOT_DONE", doc)
        self.assertIn("assistant-side status upgrade", doc)
        self.assertIn("Final status comes only from certify_run.py and policy_engine.py", doc)


if __name__ == "__main__":
    unittest.main()
