import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / ".agentic-runs"
RUN_DIR = RUN_ROOT / "test_quarantine_memory"


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


def load_quarantine_module():
    module_path = ROOT / ".agentic-pi" / "runtime" / "quarantine_memory_writer.py"
    spec = importlib.util.spec_from_file_location("quarantine_memory_writer", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuarantineMemoryTests(unittest.TestCase):
    def setUp(self):
        if RUN_DIR.exists():
            shutil.rmtree(RUN_DIR)
        RUN_DIR.mkdir(parents=True)

    def tearDown(self):
        if RUN_DIR.exists():
            shutil.rmtree(RUN_DIR)

    def write_candidate(self, *extra):
        return run_python(
            ".agentic-pi/runtime/quarantine_memory_writer.py",
            str(RUN_DIR),
            *extra,
        )

    def validate_quarantine(self):
        return run_python(".agentic-pi/validators/validate_quarantine_memory.py", str(RUN_DIR))

    def test_quarantine_memory_not_retrieved_by_future_runs(self):
        result = self.write_candidate(
            "--source-run-id",
            "source_run_001",
            "--principle",
            "Do not use provisional verifier evidence as final authority.",
            "--evidence-refs",
            "policy_decision.json,certification.json",
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        candidates = read_jsonl(RUN_DIR / "memory" / "learning_candidates.jsonl")
        pending = read_jsonl(RUN_DIR / "memory" / "pending_memory_promotions.jsonl")
        self.assertEqual(candidates[-1]["source_run_id"], "source_run_001")
        self.assertFalse(candidates[-1]["durable"])
        self.assertFalse(candidates[-1]["retrievable_by_future_runs"])
        self.assertEqual(pending[-1]["memory_scope"], "quarantine")

        module = load_quarantine_module()
        self.assertEqual(module.retrieve_quarantine_candidates_for_future_run(RUN_DIR), [])
        self.assertEqual(self.validate_quarantine().returncode, 0)

    def test_quarantine_memory_requires_source_run_id(self):
        result = self.write_candidate(
            "--source-run-id",
            "",
            "--principle",
            "This candidate is missing source identity.",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source_run_id is required", result.stdout)

    def test_quarantine_validator_rejects_future_retrieval_flag(self):
        memory_dir = RUN_DIR / "memory"
        memory_dir.mkdir(parents=True)
        for name in [
            "learning_candidates.jsonl",
            "curator_delta_candidates.jsonl",
            "rejected_learning_candidates.jsonl",
            "pending_memory_promotions.jsonl",
        ]:
            (memory_dir / name).touch()
        bad_candidate = {
            "schema_version": "learning_candidate_v1",
            "run_id": RUN_DIR.name,
            "source_run_id": "source_run_001",
            "candidate_id": "candidate_bad",
            "created_at": "2026-05-08T00:00:00+00:00",
            "candidate_type": "run_local_lesson",
            "principle": "Bad candidate tries to become durable immediately.",
            "evidence_refs": [],
            "memory_scope": "quarantine",
            "durable": False,
            "retrievable_by_future_runs": True,
            "authority_level": "advisory_only",
            "final_status_authority": "certifier_only",
            "can_certify_done": False,
        }
        (memory_dir / "learning_candidates.jsonl").write_text(json.dumps(bad_candidate) + "\n", encoding="utf-8")

        validation = self.validate_quarantine()
        self.assertNotEqual(validation.returncode, 0)
        self.assertIn("cannot be retrieved by future runs", validation.stdout)


if __name__ == "__main__":
    unittest.main()
