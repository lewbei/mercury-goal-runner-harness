import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEXER = ROOT / ".agentic-pi" / "runtime" / "evidence_indexer.py"
FREEZER = ROOT / ".agentic-pi" / "runtime" / "evidence_freezer.py"
VALIDATE_INDEX = ROOT / ".agentic-pi" / "validators" / "validate_evidence_index.py"
VALIDATE_FREEZE = ROOT / ".agentic-pi" / "validators" / "validate_evidence_freeze.py"


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class EvidenceFreezeTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp())
        self.run_dir = self.tmp_root / "test_evidence_freeze_run"
        self.run_dir.mkdir()
        self.index_validator = load_module("validate_evidence_index_test", VALIDATE_INDEX)
        self.freeze_validator = load_module("validate_evidence_freeze_test", VALIDATE_FREEZE)
        self.create_run()

    def tearDown(self):
        shutil.rmtree(self.tmp_root)

    def create_run(self):
        (self.run_dir / "trace.jsonl").write_text('{"event":"worker_done"}\n', encoding="utf-8")
        write_json(
            self.run_dir / "step_logs" / "001.json",
            {
                "run_id": self.run_dir.name,
                "step_id": 1,
                "status": "PASSED",
                "action_taken": "create_file",
                "files_touched": ["artifacts/output.txt"],
                "commands_run": ["write artifacts/output.txt"],
                "evidence": ["artifacts/output.txt"],
                "pass_condition_satisfied": True,
                "remaining_work": [],
            },
        )
        (self.run_dir / "artifacts").mkdir(exist_ok=True)
        (self.run_dir / "artifacts" / "output.txt").write_text("artifact\n", encoding="utf-8")
        write_json(
            self.run_dir / "verifier_artifacts" / "V.P2_STRONG.json",
            {
                "artifact_id": "V.P2_STRONG",
                "target_artifact": "artifacts/output.txt",
                "kind": "command_test",
                "source": "independent_test",
                "created_at_phase": "external_preexisting",
                "author_agent": "independent-verifier",
                "author_model": "deterministic",
                "depends_on_solution": False,
                "same_worker_as_solution": False,
                "executes_code": True,
                "assertion_count": 2,
                "mock_ratio_percent": 0,
                "solution_exists_at_creation": False,
                "provenance_level": "P2",
                "authority": "certifying",
            },
        )
        write_json(
            self.run_dir / "verifier_smell_reports" / "V.P2_STRONG.json",
            {
                "artifact_id": "V.P2_STRONG",
                "smells": [],
                "disqualifying": False,
            },
        )
        write_json(
            self.run_dir / "verifier_strength_reports" / "V.P2_STRONG.json",
            {
                "artifact_id": "V.P2_STRONG",
                "strength_level": "certifying",
                "score": 100,
            },
        )
        write_json(
            self.run_dir / "policy_decision.json",
            {
                "run_id": self.run_dir.name,
                "status": "CERTIFIED_DONE",
                "reason": "P2 verifier artifact has certifying strength.",
                "required_verifier_level": "P2",
                "certifying_artifacts": ["V.P2_STRONG"],
                "provisional_artifacts": [],
                "rejected_artifacts": [],
                "policy_checks": ["verifier artifact exists", "strength level is certifying"],
                "generated_at": "2026-05-08T00:00:00+00:00",
            },
        )
        write_json(self.run_dir / "memory" / "run_journal.jsonl", {"not": "evidence"})

    def run_indexer(self):
        result = subprocess.run(
            [sys.executable, str(INDEXER), str(self.run_dir)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        return load_json(self.run_dir / "evidence_index.json")

    def run_freezer(self):
        result = subprocess.run(
            [sys.executable, str(FREEZER), str(self.run_dir)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        return load_json(self.run_dir / "evidence_freeze.json")

    def indexed_kinds(self):
        index = self.run_indexer()
        return {item["kind"] for item in index["items"]}

    def test_evidence_index_contains_trace(self):
        self.assertIn("TRACE", self.indexed_kinds())

    def test_evidence_index_contains_step_logs(self):
        self.assertIn("STEP_LOG", self.indexed_kinds())

    def test_evidence_index_contains_verifier_artifacts(self):
        self.assertIn("VERIFIER_ARTIFACT", self.indexed_kinds())

    def test_every_policy_claim_cites_evidence(self):
        self.run_indexer()
        ok, message = self.index_validator.validate_evidence_index(self.run_dir)
        self.assertTrue(ok, message)

        policy = load_json(self.run_dir / "policy_decision.json")
        policy["certifying_artifacts"] = ["V.MISSING"]
        write_json(self.run_dir / "policy_decision.json", policy)
        self.run_indexer()
        ok, message = self.index_validator.validate_evidence_index(self.run_dir)
        self.assertFalse(ok)
        self.assertIn("cites verifier artifacts not in frozen evidence", message)

    def test_memory_cannot_enter_evidence_index(self):
        index = self.run_indexer()
        indexed_paths = {item["path"] for item in index["items"]}
        self.assertNotIn("memory/run_journal.jsonl", indexed_paths)

        index["items"].append(
            {
                "evidence_id": "ev_bad_memory",
                "kind": "ARTIFACT",
                "path": "memory/run_journal.jsonl",
                "sha256": "0" * 64,
                "producer": "memory",
                "producer_command_id": "cmd_memory",
                "trust_level": "L2_EXECUTION_EVIDENCE",
                "created_before_freeze": True,
            }
        )
        write_json(self.run_dir / "evidence_index.json", index)
        ok, message = self.index_validator.validate_evidence_index(self.run_dir)
        self.assertFalse(ok)
        self.assertIn("memory file cannot enter evidence_index.json", message)

    def test_mutation_after_freeze_detected(self):
        self.run_indexer()
        self.run_freezer()
        (self.run_dir / "artifacts" / "output.txt").write_text("mutated\n", encoding="utf-8")
        ok, message = self.freeze_validator.validate_evidence_freeze(self.run_dir)
        self.assertFalse(ok)
        self.assertIn("mismatch", message)

    def test_missing_producer_blocks_certification(self):
        index = self.run_indexer()
        index["items"][0]["producer"] = ""
        write_json(self.run_dir / "evidence_index.json", index)
        ok, message = self.index_validator.validate_evidence_index(self.run_dir)
        self.assertFalse(ok)
        self.assertIn("missing producer", message)

    def test_hash_mismatch_blocks_certification(self):
        index = self.run_indexer()
        index["items"][0]["sha256"] = "0" * 64
        write_json(self.run_dir / "evidence_index.json", index)
        ok, message = self.index_validator.validate_evidence_index(self.run_dir)
        self.assertFalse(ok)
        self.assertIn("sha256 mismatch", message)

    def test_freeze_before_policy_rejected(self):
        (self.run_dir / "policy_decision.json").unlink()
        result = subprocess.run(
            [sys.executable, str(FREEZER), str(self.run_dir)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("policy_decision.json is required before evidence freeze", result.stdout)


if __name__ == "__main__":
    unittest.main()
