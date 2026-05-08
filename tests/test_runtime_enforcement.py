import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".agentic-pi" / "runtime"
RUN_ID = "pi_smoke_runtime_enforcement_test"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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


class RuntimeEnforcementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway = load_module("command_gateway_for_tests", RUNTIME / "command_gateway.py")
        cls.guard = load_module("protected_file_guard_for_tests", RUNTIME / "protected_file_guard.py")
        cls.runner = load_module("run_enforced_pi_smoke_for_tests", RUNTIME / "run_enforced_pi_smoke.py")
        cls.validator = load_module(
            "validate_schema_for_runtime_enforcement_tests",
            ROOT / ".agentic-pi" / "validators" / "validate_schema.py",
        )

    def tearDown(self):
        run_root = ROOT / ".agentic-runs"
        for path in run_root.glob("pi_smoke_runtime_enforcement*"):
            if path.is_dir():
                shutil.rmtree(path)
        output_root = run_root / "runtime_enforcement_outputs"
        if output_root.exists():
            shutil.rmtree(output_root)

    def validate_schema(self, instance, schema_name):
        schema = self.validator.load_json(ROOT / ".agentic-pi" / "schemas" / schema_name)
        return self.validator.validate(instance, schema)

    def test_command_gateway_allows_only_exact_certifier_command(self):
        allowed = self.gateway.classify_command(
            "python .agentic-pi/validators/certify_run.py .agentic-runs/pi_smoke_runtime_enforcement_test",
            RUN_ID,
        )
        blocked = self.gateway.classify_command(
            "python .agentic-pi/validators/certify_run.py .agentic-runs/pi_smoke_runtime_enforcement_test --repair",
            RUN_ID,
        )

        self.assertEqual(allowed["decision"], "ALLOW", allowed)
        self.assertEqual(allowed["command_kind"], "certifier")
        self.assertEqual(blocked["decision"], "BLOCK", blocked)

    def test_command_gateway_blocks_protected_write_and_path_escape(self):
        protected = self.gateway.classify_command(
            f"Set-Content -Path .agentic-runs/{RUN_ID}/final_status.md -Value CERTIFIED_DONE",
            RUN_ID,
        )
        escaped = self.gateway.classify_command(
            f"Set-Content -Path .agentic-runs/{RUN_ID}/../escape.txt -Value bad",
            RUN_ID,
        )

        self.assertEqual(protected["decision"], "BLOCK", protected)
        self.assertIn("manual protected status or verifier write command", "\n".join(protected["violations"]))
        self.assertEqual(escaped["decision"], "BLOCK", escaped)
        self.assertIn("path escape", "\n".join(escaped["violations"]))

    def test_protected_file_guard_detects_unauthorized_status_change(self):
        result = self.runner.run_enforced_smoke("safe_certifier", RUN_ID, clean=True)
        self.assertEqual(result["result_status"], "PASS", result)
        run_dir = ROOT / ".agentic-runs" / RUN_ID
        before = self.guard.snapshot_protected_files(run_dir)
        (run_dir / "final_status.md").write_text("CERTIFIED_DONE\n", encoding="utf-8")
        after = self.guard.snapshot_protected_files(run_dir)

        report = self.guard.protected_change_report(before, after, allowed_writer="none")

        self.assertTrue(report["unauthorized_change"], report)
        self.assertIn("final_status.md", report["changed_paths"])

    def test_safe_certifier_run_is_accepted_from_certifier_artifacts_only(self):
        result = self.runner.run_enforced_smoke("safe_certifier", RUN_ID, clean=True)

        self.assertEqual(result["result_status"], "PASS", result)
        self.assertEqual(result["monitor_status"], "PASS", result)
        self.assertEqual(result["accepted_status"], "CERTIFIED_DONE")
        self.assertEqual(set(result["status_values"].values()), {"CERTIFIED_DONE"})
        self.assertTrue(result["status_artifacts_agree"])
        self.assertEqual(result["final_status_authority"], "certifier_only")
        self.assertFalse(result["can_certify_done"])
        self.assertEqual(self.validate_schema(result, "runtime_enforcement_result.schema.json"), [])

    def test_negative_runtime_scenarios_become_monitor_fail_not_accepted_certification(self):
        scenarios = [
            "manual_final_status_write",
            "manual_certification_write",
            "manual_policy_decision_write",
            "verifier_artifact_edit",
            "duplicate_certifier_command",
            "unapproved_bash",
            "path_escape",
            "unsafe_delete",
        ]

        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                run_id = f"{RUN_ID}_{scenario}"
                result = self.runner.run_enforced_smoke(scenario, run_id, clean=True)

                self.assertEqual(result["result_status"], "PASS", result)
                self.assertEqual(result["monitor_status"], "MONITOR_FAIL", result)
                self.assertEqual(result["accepted_status"], "MONITOR_FAIL", result)
                self.assertFalse(result["can_certify_done"])
                self.assertTrue(result["violations"], result)
                self.assertEqual(self.validate_schema(result, "runtime_enforcement_result.schema.json"), [])

    def test_cli_writes_schema_valid_runtime_enforcement_result(self):
        result = run_python(
            ".agentic-pi/runtime/run_enforced_pi_smoke.py",
            "--scenario",
            "safe_certifier",
            "--target-run-id",
            RUN_ID,
            "--clean",
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        output_path = ROOT / ".agentic-runs" / "runtime_enforcement_outputs" / "safe_certifier_result.json"
        self.assertTrue(output_path.is_file())
        payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
        self.assertEqual(payload["result_status"], "PASS")
        self.assertEqual(payload["accepted_status"], "CERTIFIED_DONE")
        self.assertEqual(self.validate_schema(payload, "runtime_enforcement_result.schema.json"), [])

    def test_v32_doc_locks_runtime_enforcement_boundary(self):
        doc = (ROOT / "docs" / "V3_2_RUNTIME_ENFORCEMENT_PROOF.md").read_text(encoding="utf-8")

        self.assertIn("RUNTIME ENFORCEMENT PROOF IMPLEMENTED", doc)
        self.assertIn("unsafe Pi/Mercury-shaped commands are blocked or downgraded to MONITOR_FAIL", doc)
        self.assertIn("Final status still comes only from certify_run.py and policy_engine.py", doc)
        self.assertIn("does not prove arbitrary prompts", doc)


if __name__ == "__main__":
    unittest.main()

