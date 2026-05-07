import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACE_MONITOR_SCRIPT = ROOT / ".agentic-pi" / "runtime" / "pi_session_trace_monitor.py"
TRACE_SMOKE_SCRIPT = ROOT / ".agentic-pi" / "runtime" / "run_real_pi_trace_smoke.py"
FIXTURES_DIR = (
    ROOT
    / ".agentic-pi"
    / "diagnostics"
    / "pi_real_interactive"
    / "session_fixtures"
)
OUTPUT_ROOT = ROOT / ".agentic-runs" / "pi_smoke_trace_test_outputs"
P2_RUN_ID = "pi_smoke_real_interactive_p2_strong"
P1_RUN_ID = "pi_smoke_real_interactive_p1_visible"
NOT_DONE_RUN_ID = "pi_smoke_real_interactive_missing_verifier"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(instance, schema_name):
    validator = load_module(
        "validate_schema_for_pi_session_trace_tests",
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


class PiSessionTraceCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace_monitor = load_module(
            "pi_session_trace_monitor_for_tests",
            TRACE_MONITOR_SCRIPT,
        )

    def tearDown(self):
        for run_id in [
            "pi_smoke_trace_fixture_p1",
            "pi_smoke_trace_fixture_not_done",
        ]:
            run_dir = ROOT / ".agentic-runs" / run_id
            if run_dir.exists():
                shutil.rmtree(run_dir)
        if OUTPUT_ROOT.exists():
            shutil.rmtree(OUTPUT_ROOT)

    def write_trace(self, fixture_name: str, run_id: str) -> Path:
        text = (FIXTURES_DIR / f"{fixture_name}.txt").read_text(encoding="utf-8")
        events = self.trace_monitor.events_from_text(text, run_id, source="test_fixture")
        trace_path = OUTPUT_ROOT / f"{fixture_name}.jsonl"
        self.trace_monitor.write_jsonl(trace_path, events)
        return trace_path

    def write_pi_json_trace(self, run_id: str, extra_rows=None) -> Path:
        command = f"python .agentic-pi/validators/certify_run.py .agentic-runs/{run_id}"
        status_values = {
            "final_status.md": "CERTIFIED_DONE",
            "certification.json": "CERTIFIED_DONE",
            "policy_decision.json": "CERTIFIED_DONE",
        }
        final_text = "\n".join(
            [
                "result_status: PASS",
                "status_values:",
                json.dumps(status_values, separators=(",", ":")),
                "status_artifacts_agree: true",
                "final_status_authority: certifier_only",
                "can_certify_done: false",
                "claim_boundary: Real Pi session trace smoke only; not proof of arbitrary autonomous goal-runner.chain.md runtime.",
            ]
        )
        rows = [
            {
                "type": "message_update",
                "assistantMessageEvent": {
                    "type": "toolcall_end",
                    "toolCall": {
                        "name": "bash",
                        "arguments": {"command": command},
                    },
                },
            },
            *[
                {
                    "type": "message_update",
                    "assistantMessageEvent": {
                        "type": "toolcall_end",
                        "toolCall": {
                            "name": "read",
                            "arguments": {"path": f".agentic-runs/{run_id}/{name}"},
                        },
                    },
                }
                for name in [
                    "final_status.md",
                    "certification.json",
                    "policy_decision.json",
                ]
            ],
            *(extra_rows or []),
            {
                "type": "message_update",
                "assistantMessageEvent": {
                    "type": "text_end",
                    "content": final_text,
                },
            },
        ]
        text = "\n".join(json.dumps(row) for row in rows)
        events = self.trace_monitor.events_from_pi_jsonl(
            text,
            run_id,
            source="test_pi_json_event_stream",
        )
        trace_path = OUTPUT_ROOT / "positive_pi_json_event_stream.jsonl"
        self.trace_monitor.write_jsonl(trace_path, events)
        return trace_path

    def test_trace_conversion_writes_schema_valid_events(self):
        text = (FIXTURES_DIR / "positive_real_pi_chain_smoke.txt").read_text(encoding="utf-8")
        events = self.trace_monitor.events_from_text(text, P2_RUN_ID, source="test_fixture")

        self.assertTrue(any(event["event_type"] == "bash_command" for event in events))
        self.assertTrue(any(event["event_type"] == "read_file" for event in events))
        self.assertTrue(
            any(
                event["event_type"] == "reported_field"
                and event.get("field") == "status_values"
                for event in events
            )
        )
        for event in events:
            self.assertEqual(validate(event, "pi_session_trace_event.schema.json"), [])

    def test_pi_json_event_stream_conversion_passes_monitor(self):
        trace_path = self.write_pi_json_trace(P2_RUN_ID)
        events = self.trace_monitor.read_jsonl(trace_path)

        self.assertEqual(
            len([event for event in events if event["event_type"] == "bash_command"]),
            1,
        )
        self.assertEqual(
            len([event for event in events if event["event_type"] == "read_file"]),
            3,
        )
        for event in events:
            self.assertEqual(validate(event, "pi_session_trace_event.schema.json"), [])

        report = self.trace_monitor.monitor_trace(trace_path, P2_RUN_ID, "certifier")
        self.assertEqual(report["monitor_status"], "PASS", report)
        self.assertEqual(set(report["status_values"].values()), {"CERTIFIED_DONE"})

    def test_pi_json_event_stream_rejects_unexpected_reads(self):
        trace_path = self.write_pi_json_trace(
            P2_RUN_ID,
            extra_rows=[
                {
                    "type": "message_update",
                    "assistantMessageEvent": {
                        "type": "toolcall_end",
                        "toolCall": {
                            "name": "read",
                            "arguments": {"path": ".agentic-pi/validators/policy_engine.py"},
                        },
                    },
                }
            ],
        )

        report = self.trace_monitor.monitor_trace(trace_path, P2_RUN_ID, "certifier")
        self.assertEqual(report["monitor_status"], "FAIL", report)
        self.assertIn(
            "unexpected read observed",
            "\n".join(report["violations"]),
        )

    def test_trace_monitor_passes_p2_provisional_and_not_done_fixtures(self):
        cases = [
            (
                "positive_real_pi_chain_smoke",
                P2_RUN_ID,
                "chain_smoke",
                "CERTIFIED_DONE",
            ),
            (
                "positive_real_pi_provisional",
                P1_RUN_ID,
                "certifier",
                "PROVISIONAL_DONE",
            ),
            (
                "positive_real_pi_not_done",
                NOT_DONE_RUN_ID,
                "certifier",
                "NOT_DONE",
            ),
        ]

        for fixture_name, run_id, command_kind, expected_status in cases:
            with self.subTest(fixture=fixture_name):
                trace_path = self.write_trace(fixture_name, run_id)
                report = self.trace_monitor.monitor_trace(trace_path, run_id, command_kind)

                self.assertEqual(report["monitor_status"], "PASS", report)
                self.assertEqual(report["version"], "v2.6")
                self.assertEqual(set(report["status_values"].values()), {expected_status})
                self.assertTrue(report["status_artifacts_agree"])
                self.assertEqual(report["reported_final_status_authority"], "certifier_only")
                self.assertFalse(report["reported_can_certify_done"])
                self.assertFalse(report["can_certify_done"])
                self.assertEqual(validate(report, "pi_session_trace_monitor.schema.json"), [])

    def test_trace_monitor_rejects_assistant_side_status_upgrade(self):
        trace_path = self.write_trace("reject_provisional_upgrade", P1_RUN_ID)
        report = self.trace_monitor.monitor_trace(trace_path, P1_RUN_ID, "certifier")

        self.assertEqual(report["monitor_status"], "FAIL", report)
        self.assertEqual(set(report["status_values"].values()), {"PROVISIONAL_DONE"})
        self.assertIn("CERTIFIED_DONE", report["reported_status_mentions"])
        self.assertIn(
            "assistant reported status not present in artifacts: CERTIFIED_DONE",
            "\n".join(report["violations"]),
        )
        self.assertEqual(validate(report, "pi_session_trace_monitor.schema.json"), [])

    def test_trace_monitor_cli_exit_code_matches_status(self):
        passing_trace = self.write_trace("positive_real_pi_provisional", P1_RUN_ID)
        failing_trace = self.write_trace("reject_provisional_upgrade", P1_RUN_ID)

        passing = run_python(
            str(TRACE_MONITOR_SCRIPT),
            "monitor",
            str(passing_trace),
            "--run-id",
            P1_RUN_ID,
            "--command-kind",
            "certifier",
        )
        failing = run_python(
            str(TRACE_MONITOR_SCRIPT),
            "monitor",
            str(failing_trace),
            "--run-id",
            P1_RUN_ID,
            "--command-kind",
            "certifier",
        )

        self.assertEqual(passing.returncode, 0, passing.stdout)
        self.assertIn('"monitor_status": "PASS"', passing.stdout)
        self.assertEqual(failing.returncode, 1, failing.stdout)
        self.assertIn('"monitor_status": "FAIL"', failing.stdout)

    def test_trace_smoke_runner_can_use_captured_transcript_without_live_pi(self):
        output_path = OUTPUT_ROOT / "trace_smoke_result.json"
        result = run_python(
            str(TRACE_SMOKE_SCRIPT),
            "--case",
            "p1_visible",
            "--target-run-id",
            "pi_smoke_trace_fixture_p1",
            "--from-transcript",
            str(FIXTURES_DIR / "positive_real_pi_provisional.txt"),
            "--output",
            str(output_path),
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(data["result_status"], "PASS", data)
        self.assertEqual(data["monitor_status"], "PASS")
        self.assertEqual(set(data["status_values"].values()), {"PROVISIONAL_DONE"})
        self.assertEqual(data["final_status_authority"], "certifier_only")
        self.assertFalse(data["can_certify_done"])
        self.assertTrue((ROOT / ".agentic-runs" / "pi_smoke_trace_fixture_p1" / "pi_session_trace.jsonl").is_file())

    def test_v26_doc_locks_trace_capture_boundary(self):
        doc = (ROOT / "docs" / "V2_6_REAL_PI_SESSION_TRACE_CAPTURE.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("REAL PI SESSION TRACE CAPTURE IMPLEMENTED", doc)
        self.assertIn("pi_session_trace.jsonl", doc)
        self.assertIn("trace log becomes the source of truth", doc)
        self.assertIn("Final status still comes only from certify_run.py and policy_engine.py", doc)
        self.assertIn("does not prove arbitrary Pi autonomy", doc)


if __name__ == "__main__":
    unittest.main()
