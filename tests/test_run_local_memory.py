import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / ".agentic-runs"
RUN_DIR = RUN_ROOT / "test_run_local_memory"


def run_python(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class RunLocalMemoryTests(unittest.TestCase):
    def setUp(self):
        if RUN_DIR.exists():
            shutil.rmtree(RUN_DIR)
        RUN_DIR.mkdir(parents=True)

    def tearDown(self):
        if RUN_DIR.exists():
            shutil.rmtree(RUN_DIR)

    def append_memory(self, phase: str, message: str, *extra):
        return run_python(
            ".agentic-pi/runtime/run_memory_clerk.py",
            str(RUN_DIR),
            "--phase",
            phase,
            "--message",
            message,
            *extra,
        )

    def validate_memory(self):
        return run_python(".agentic-pi/validators/validate_run_local_memory.py", str(RUN_DIR))

    def test_run_local_memory_appends_during_planning(self):
        result = self.append_memory("planning", "Plan seed needs verifier path before local steps.")

        self.assertEqual(result.returncode, 0, result.stdout)
        journal = read_jsonl(RUN_DIR / "memory" / "run_journal.jsonl")
        phase_notes = read_jsonl(RUN_DIR / "memory" / "phase_observations.jsonl")
        self.assertEqual(journal[-1]["phase"], "planning")
        self.assertEqual(phase_notes[-1]["memory_scope"], "run_local")
        self.assertFalse(phase_notes[-1]["can_certify_done"])
        self.assertTrue(phase_notes[-1]["excluded_from_evidence_index"])
        self.assertEqual(self.validate_memory().returncode, 0)

    def test_run_local_memory_appends_during_execution(self):
        result = self.append_memory("execution", "Worker produced artifact candidate.", "--target-file", "artifacts/output.txt")

        self.assertEqual(result.returncode, 0, result.stdout)
        entries = read_jsonl(RUN_DIR / "memory" / "phase_observations.jsonl")
        self.assertEqual(entries[-1]["phase"], "execution")
        self.assertEqual(entries[-1]["target_file"], "artifacts/output.txt")
        self.assertEqual(entries[-1]["authority_level"], "advisory_only")
        self.assertEqual(self.validate_memory().returncode, 0)

    def test_run_local_memory_appends_after_verifier_failure(self):
        result = self.append_memory("verifier_failure", "Verifier evidence was missing, so repair may need a verifier artifact.")

        self.assertEqual(result.returncode, 0, result.stdout)
        failures = read_jsonl(RUN_DIR / "memory" / "failure_observations.jsonl")
        self.assertEqual(failures[-1]["phase"], "verifier_failure")
        self.assertIn("Verifier evidence", failures[-1]["message"])
        self.assertEqual(failures[-1]["final_status_authority"], "certifier_only")
        self.assertEqual(self.validate_memory().returncode, 0)

    def test_run_local_memory_cannot_write_authority_artifacts(self):
        result = self.append_memory(
            "repair",
            "Try to update status",
            "--target-file",
            "final_status.json",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RUN_MEMORY_REJECTED", result.stdout)
        self.assertFalse((RUN_DIR / "final_status.json").exists())
        self.assertFalse((RUN_DIR / "memory" / "final_status.json").exists())

    def test_run_local_memory_cannot_enter_evidence_index(self):
        result = self.append_memory("planning", "Memory should stay advisory.")
        self.assertEqual(result.returncode, 0, result.stdout)
        (RUN_DIR / "evidence_index.json").write_text(
            json.dumps(
                {
                    "schema_version": "evidence_index_v1",
                    "run_id": RUN_DIR.name,
                    "frozen": True,
                    "freeze_id": "freeze_0001",
                    "items": [
                        {
                            "evidence_id": "ev_memory_bad",
                            "kind": "TRACE",
                            "path": "memory/run_journal.jsonl",
                            "sha256": "0" * 64,
                            "producer": "run_memory_clerk",
                            "producer_command_id": "cmd_memory",
                            "trust_level": "L2_EXECUTION_EVIDENCE",
                            "created_before_freeze": True,
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        validation = self.validate_memory()
        self.assertNotEqual(validation.returncode, 0)
        self.assertIn("listed in evidence_index.json", validation.stdout)


if __name__ == "__main__":
    unittest.main()
